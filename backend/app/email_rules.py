"""Luật phát hiện email lừa đảo. Chạy trước Gemini, giống run_heuristics cho trang web."""
import re
import unicodedata
from urllib.parse import urlsplit

from .domains import registrable_domain
from .heuristics import BRANDS, Tally, _is_official, _tokens, run_heuristics, verdict_of
from .schemas import AnalyzeRequest, AnalyzeResponse, EmailRequest

EMAIL_RE = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
DOMAIN_IN_TEXT = re.compile(r"\b((?:[a-z0-9-]+\.)+[a-z]{2,})\b")

# Lời lẽ hối thúc / đe dọa (đã bỏ dấu tiếng Việt trước khi so).
URGENCY = [
    "khan cap", "ngay lap tuc", "bi khoa", "tam khoa", "vo hieu hoa", "trong 24 gio",
    "trong vong 24", "het han", "canh bao", "dinh chi", "urgent", "immediately",
    "suspended", "locked", "expire", "within 24 hours", "final notice", "unusual activity",
]
# Đòi thông tin nhạy cảm hoặc tiền.
SENSITIVE = [
    "mat khau", "ma otp", "otp", "so the", "cvv", "ma pin", "chuyen khoan", "the cao",
    "password", "verify your account", "confirm your identity", "credit card",
    "bank account", "gift card", "wire transfer",
]
# Mồi nhử trúng thưởng.
PRIZE = ["trung thuong", "qua tang", "nhan thuong", "tri an khach hang", "you have won",
         "congratulations", "lottery", "prize", "free iphone"]


def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower()).replace("đ", "d")
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _domain_of(address: str) -> str:
    m = EMAIL_RE.search(address.lower())
    return m.group(1) if m else ""


_base = registrable_domain  # mail.paypal.com -> paypal.com, x.com.vn -> x.com.vn


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def run_email_rules(req: EmailRequest) -> AnalyzeResponse:
    t = Tally()
    sender_domain = _domain_of(req.sender)
    display_name = req.sender.split("<")[0]

    # 1. Tên hiển thị mạo danh thương hiệu nhưng gửi từ tên miền khác.
    name_tokens = set(_tokens(_strip_accents(display_name).replace(" ", "-")))
    for brand, official in BRANDS.items():
        if any(t.startswith(brand) for t in name_tokens) and sender_domain \
                and not _is_official(sender_domain, official):
            t.add(0.4, f"Người gửi xưng là '{brand}' nhưng gửi từ tên miền {sender_domain}.")
            break

    # 2. Reply-To khác người gửi: trả lời sẽ đi tới kẻ gian.
    reply_domain = _domain_of(req.reply_to)
    if reply_domain and sender_domain and _base(reply_domain) != _base(sender_domain):
        t.add(0.2, f"Địa chỉ trả lời ({reply_domain}) khác tên miền người gửi.")

    # 3. Link: chữ hiển thị một tên miền nhưng thực ra trỏ tới tên miền khác,
    #    hoặc bản thân link trông như trang lừa đảo.
    mismatch = risky = None
    for link in req.links:
        href_host = _host(link.href)
        if not href_host:
            continue
        shown = DOMAIN_IN_TEXT.search(link.text.lower())
        if mismatch is None and shown and _base(shown.group(1)) != _base(href_host):
            mismatch = (shown.group(1), href_host)
        if risky is None:
            r = run_heuristics(AnalyzeRequest(
                url=link.href, hostname=href_host,
                protocol=(urlsplit(link.href).scheme or "http") + ":",
            ))
            if r.verdict != "safe":
                risky = (href_host, r)
    if mismatch:
        t.add(0.4, f"Link hiển thị '{mismatch[0]}' nhưng thực ra dẫn tới {mismatch[1]}.")
    if risky:
        t.add(0.3 if risky[1].verdict == "phishing" else 0.15, f"Email chứa link đáng ngờ: {risky[0]}.")

    # 4. Nội dung: hối thúc, đòi thông tin nhạy cảm, mồi trúng thưởng.
    text = _strip_accents(f"{req.subject}\n{req.body}")
    if any(w in text for w in URGENCY):
        t.add(0.15, "Nội dung hối thúc hoặc đe dọa (khóa tài khoản, hết hạn...).")
    if any(w in text for w in SENSITIVE):
        t.add(0.15, "Email đề cập mật khẩu, OTP, thẻ hoặc chuyển tiền.")
    if any(w in text for w in PRIZE):
        t.add(0.15, "Email hứa hẹn quà tặng hoặc trúng thưởng.")

    score = t.score
    verdict = verdict_of(score)
    return AnalyzeResponse(verdict=verdict, score=score, reasons=t.reasons, source="email",
                           breakdown=t.signals)
