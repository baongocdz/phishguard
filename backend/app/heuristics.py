import re

from .domains import is_ip
from .schemas import AnalyzeRequest, AnalyzeResponse

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
    "facebook": ["facebook.com", "fb.com"],
    "instagram": ["instagram.com"],
    "netflix": ["netflix.com"],
    "amazon": ["amazon.com"],
    "github": ["github.com", "github.io"],
    "binance": ["binance.com"],
    "zalo": ["zalo.me", "zaloapp.com"],
    "shopee": ["shopee.vn"],
    "lazada": ["lazada.vn"],
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

# Đổi chữ số giả chữ cái về chữ (faceb00k -> facebook, paypa1 -> paypal).
LEET = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t"})


def _tokens(host: str) -> list[str]:
    """Tách tên miền theo '.' và '-', đổi chữ số giả chữ cái về chữ."""
    return [t.translate(LEET) for t in re.split(r"[.-]", host) if t]


def _is_official(host: str, domains: list[str]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def run_heuristics(req: AnalyzeRequest) -> AnalyzeResponse:
    """Bản Python của luật ở Extension. Luật chưa chắc chắn thì service.py
    hỏi thêm Gemini."""
    reasons: list[str] = []
    score = 0.0
    host = req.hostname.lower().rstrip(".")

    if req.protocol != "https:":
        score += 0.2
        reasons.append("Trang không dùng HTTPS.")
    if is_ip(host):
        score += 0.4
        reasons.append("Địa chỉ trang là IP thay vì tên miền.")
    if "@" in req.url:
        score += 0.3
        reasons.append("URL chứa ký tự '@' (có thể che giấu tên miền thật).")
    if len(host) > 40 or host.count("-") >= 3:
        score += 0.2
        reasons.append("Tên miền quá dài hoặc có nhiều dấu gạch ngang.")
    if "xn--" in host:
        score += 0.3
        reasons.append("Tên miền dùng punycode (có thể giả mạo ký tự).")
    if req.has_password_field and req.protocol != "https:":
        score += 0.4
        reasons.append("Có ô nhập mật khẩu trên kết nối không an toàn.")

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
            score += 0.4
            reasons.append(f"Tên miền chứa tên thương hiệu '{brand}' nhưng không phải tên miền chính thức.")
        if host.rsplit(".", 1)[-1] in SUSPICIOUS_TLDS:
            score += 0.2
            reasons.append("Đuôi tên miền thường bị dùng cho trang lừa đảo.")
        if any(w in t for t in tokens for w in LURE_WORDS):
            score += 0.2
            reasons.append("Tên miền chứa từ ngữ dụ đăng nhập/xác minh.")

    score = min(1.0, round(score, 2))
    verdict = "phishing" if score >= 0.6 else "suspicious" if score >= 0.3 else "safe"
    return AnalyzeResponse(verdict=verdict, score=score, reasons=reasons, source="heuristic")
