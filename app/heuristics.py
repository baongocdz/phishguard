from .domains import is_ip
from .schemas import AnalyzeRequest, AnalyzeResponse


def run_heuristics(req: AnalyzeRequest) -> AnalyzeResponse:
    """Bản Python của luật ở Extension. Tuần 6: gọi Gemini ở bước này khi
    điểm nằm trong vùng không chắc chắn (vd 0.2-0.7)."""
    reasons: list[str] = []
    score = 0.0
    host = req.hostname.lower()

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

    score = min(1.0, round(score, 2))
    verdict = "phishing" if score >= 0.6 else "suspicious" if score >= 0.3 else "safe"
    return AnalyzeResponse(verdict=verdict, score=score, reasons=reasons, source="heuristic")
