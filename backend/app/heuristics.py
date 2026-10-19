import re
import unicodedata

from .domains import is_ip, is_lan_host
from .schemas import AnalyzeRequest, AnalyzeResponse, Signal


def verdict_of(score: float) -> str:
    return "phishing" if score >= 0.6 else "suspicious" if score >= 0.3 else "safe"


class Tally:
    """Cộng điểm và ghi lại từng tín hiệu để giải thích kết quả."""

    def __init__(self, layer: str = "rule"):
        self.layer = layer
        self.signals: list[Signal] = []

    def add(self, points: float, reason: str) -> None:
        self.signals.append(Signal(layer=self.layer, label=reason, points=round(points, 2)))

    @property
    def reasons(self) -> list[str]:
        return [s.label for s in self.signals]

    @property
    def score(self) -> float:
        return min(1.0, round(sum(s.points for s in self.signals), 2))

# Từ khóa thương hiệu -> các tên miền chính thức. Tên miền chứa từ khóa nhưng
# không thuộc tên miền chính thức thì nhiều khả năng là giả mạo.
# Giữ đồng bộ với BRANDS trong extension/src/analyzer.ts.
BRANDS: dict[str, list[str]] = {
    "paypal": ["paypal.com"],
    "apple": ["apple.com", "icloud.com"],
    "icloud": ["icloud.com", "apple.com"],
    "microsoft": ["microsoft.com", "microsoftonline.com", "live.com", "office.com"],
    "office365": ["office365.com", "office.com", "microsoft.com"],
    "outlook": ["outlook.com", "live.com", "office.com", "office365.com"],
    "google": ["google.com", "google.com.vn", "googleusercontent.com", "googleblog.com"],
    "gmail": ["gmail.com", "google.com"],
    "facebook": ["facebook.com", "fb.com", "facebook.net", "fbcdn.net"],
    "instagram": ["instagram.com"],
    "netflix": ["netflix.com"],
    "amazon": ["amazon.com", "amazonaws.com", "amazon.co.jp", "amazon.de"],
    "github": ["github.com", "github.io"],
    "binance": ["binance.com"],
    "zalo": ["zalo.me", "zaloapp.com"],
    "shopee": ["shopee.vn"],
    "lazada": ["lazada.vn", "lazada.co.th", "lazada.com.my", "lazada.sg", "lazada.co.id", "lazada.com.ph"],
    "vietcombank": ["vietcombank.com.vn"],
    "techcombank": ["techcombank.com", "techcombank.com.vn"],
    "vietinbank": ["vietinbank.vn"],
    "agribank": ["agribank.com.vn"],
    "bidv": ["bidv.com.vn"],
    "mbbank": ["mbbank.com.vn"],
    "tpbank": ["tpb.vn", "tpbank.vn"],
    "sacombank": ["sacombank.com.vn"],
    "momo": ["momo.vn"],
}

# Đuôi tên miền rẻ/miễn phí, thường bị dùng cho trang lừa đảo.
SUSPICIOUS_TLDS = {
    "top", "xyz", "click", "icu", "buzz", "cyou", "rest", "monster", "sbs", "cfd",
    "quest", "tk", "ml", "ga", "cf", "gq", "zip", "mov",
}

# Từ ngữ dụ người dùng đăng nhập/xác minh, xuất hiện ngay trong tên miền.
LURE_WORDS = [
    "login", "signin", "verify", "secure", "security", "account", "update",
    "confirm", "recover", "unlock", "xacminh", "xacthuc", "dangnhap", "baomat",
    "khoataikhoan",
]

# Trang cờ bạc / cá cược trực tuyến (bất hợp pháp ở VN, hay lừa nạp tiền) — đích của quảng cáo trên
# web phim lậu (vd "NET88 - Nhà cái uy tín, Thể thao, Casino, Nổ hũ, Tài xỉu"). So trên chữ đã bỏ dấu.
# Chỉ dùng từ quảng cáo của nhà cái; không dùng "đánh bạc" để bài báo về triệt phá cờ bạc không bị bắt.
GAMBLING_WORDS = {  # chữ đã bỏ dấu -> chữ hiển thị trong lý do
    "nha cai": "nhà cái", "ca cuoc": "cá cược", "ca do": "cá độ", "casino": "casino", "no hu": "nổ hũ",
    "tai xiu": "tài xỉu", "game bai": "game bài", "ban ca": "bắn cá", "xoc dia": "xóc đĩa", "lo de": "lô đề",
    "baccarat": "baccarat", "roulette": "roulette", "sportsbook": "sportsbook", "slot game": "slot game",
}
GAMBLING_RE = re.compile(r"\b(" + "|".join(GAMBLING_WORDS) + r")\b")


def strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower()).replace("đ", "d")
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def gambling_words(title: str, text: str) -> tuple[set[str], set[str]]:
    """Từ khóa cờ bạc khác nhau trong tiêu đề, và trong cả tiêu đề + nội dung."""
    in_title = set(GAMBLING_RE.findall(strip_accents(title)))
    return in_title, in_title | set(GAMBLING_RE.findall(strip_accents(text)))


# Đổi chữ số giả chữ cái về chữ (faceb00k -> facebook, paypa1 -> paypal).
LEET = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t"})


def _tokens(host: str) -> list[str]:
    """Tách tên miền theo '.' và '-', đổi chữ số giả chữ cái về chữ."""
    return [t.translate(LEET) for t in re.split(r"[.-]", host) if t]


# Cặp ký tự trông giống một chữ khác: vietcornbank -> vietcombank, vvebsite -> website.
HOMOGLYPHS = [("rn", "m"), ("vv", "w")]


def _edit_distance(a: str, b: str, limit: int) -> int:
    """Khoảng cách Levenshtein, dừng sớm khi vượt limit (trả limit + 1)."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def lookalike_brand(host: str, tokens: list[str]) -> str | None:
    """Thương hiệu mà tên miền "na ná" (không chứa đúng tên, nhưng gần giống)."""
    for b, official in BRANDS.items():
        if len(b) < 6 or _is_official(host, official):
            continue  # tên ngắn (zalo, bidv...) so gần đúng dễ nhầm, bỏ qua
        limit = 2 if len(b) >= 9 else 1
        for t in tokens:
            fixed = t
            for fake, real in HOMOGLYPHS:
                fixed = fixed.replace(fake, real)
            if fixed != t and fixed.startswith(b):
                return b
            if t != b and _edit_distance(t, b, limit) <= limit:
                return b
    return None


def _is_official(host: str, domains: list[str]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def run_heuristics(req: AnalyzeRequest) -> AnalyzeResponse:
    """Bản Python của luật ở Extension. Luật chưa chắc chắn thì service.py
    hỏi thêm Gemini."""
    t = Tally()
    host = req.hostname.lower().rstrip(".")
    if is_lan_host(host):
        t.add(0.0, "Thiết bị trong mạng nội bộ (modem, máy in, NAS...) — không xét lừa đảo.")
        return AnalyzeResponse(verdict="safe", score=0.0, reasons=t.reasons, source="heuristic",
                               breakdown=t.signals)

    if req.protocol != "https:":
        t.add(0.2, "Trang không dùng HTTPS.")
    if is_ip(host):
        t.add(0.4, "Địa chỉ trang là IP thay vì tên miền.")
    if "@" in req.url:
        t.add(0.3, "URL chứa ký tự '@' (có thể che giấu tên miền thật).")
    if len(host) > 40 or host.count("-") >= 3:
        t.add(0.2, "Tên miền quá dài hoặc có nhiều dấu gạch ngang.")
    if "xn--" in host:
        t.add(0.3, "Tên miền dùng punycode (có thể giả mạo ký tự).")
    if req.has_password_field and req.protocol != "https:":
        t.add(0.4, "Có ô nhập mật khẩu trên kết nối không an toàn.")

    if not is_ip(host):
        tokens = _tokens(host)
        # Chỉ khớp khi thương hiệu đứng đầu một cụm: "paypal-verify", "paypalhelp"
        # khớp, còn "pineapple" thì không bị coi là "apple".
        brand = next(
            (b for b, official in BRANDS.items()
             if any(t.startswith(b) for t in tokens) and not _is_official(host, official)),
            None,
        )
        if brand:
            t.add(0.4, f"Tên miền chứa tên thương hiệu '{brand}' nhưng không phải tên miền chính thức.")
        elif lookalike := lookalike_brand(host, tokens):
            t.add(0.4, f"Tên miền na ná thương hiệu '{lookalike}' (dùng ký tự gần giống để đánh lừa).")
        if host.rsplit(".", 1)[-1] in SUSPICIOUS_TLDS:
            t.add(0.2, "Đuôi tên miền thường bị dùng cho trang lừa đảo.")
        if any(w in t for t in tokens for w in LURE_WORDS):
            t.add(0.2, "Tên miền chứa từ ngữ dụ đăng nhập/xác minh.")

    # Nội dung: trang cờ bạc (≥ 2 từ khóa trong tiêu đề, hoặc ≥ 3 trong tiêu đề + chữ trên trang).
    in_title, in_page = gambling_words(req.title, req.text_snippet)
    if len(in_title) >= 2 or len(in_page) >= 3:
        t.add(0.35, "Trang cờ bạc / cá cược trực tuyến (bất hợp pháp tại Việt Nam, hay lừa nạp tiền): "
                    + ", ".join(GAMBLING_WORDS[w] for w in sorted(in_page)[:4]) + ".")

    score = t.score
    verdict = verdict_of(score)
    return AnalyzeResponse(verdict=verdict, score=score, reasons=t.reasons, source="heuristic",
                           breakdown=t.signals)
