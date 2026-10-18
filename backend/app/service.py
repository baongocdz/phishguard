from datetime import datetime, timezone

from . import gemini_client
from .config import settings
from .domains import cache_key, candidate_domains
from .gemini_client import GeminiOutput
from .heuristics import run_heuristics
from .schemas import AnalyzeRequest, AnalyzeResponse

SEVERITY = {"safe": 0, "suspicious": 1, "phishing": 2}


def should_call_gemini(req: AnalyzeRequest, heuristic: AnalyzeResponse) -> bool:
    """Chỉ hỏi Gemini khi cần, để tiết kiệm hạn mức và độ trễ:
    - phải có API key;
    - luật chưa kết luận chắc chắn là phishing (điểm < 0.6);
    - trang có form/ô mật khẩu hoặc đã có dấu hiệu nghi ngờ từ luật."""
    if not settings.gemini_api_key:
        return False
    if heuristic.score >= 0.6:
        return False
    return req.has_password_field or req.form_count > 0 or heuristic.score >= 0.2


def _gemini_score(g: GeminiOutput) -> float:
    if g.verdict == "phishing":
        return round(max(g.confidence, 0.6), 2)
    if g.verdict == "suspicious":
        return round(min(max(g.confidence, 0.3), 0.59), 2)
    return round(min(1 - g.confidence, 0.29), 2)


def merge(h: AnalyzeResponse, g: GeminiOutput) -> AnalyzeResponse:
    """Kết luận nghiêm trọng hơn sẽ thắng. Nhờ vậy một trang chèn câu lệnh
    kiểu 'hãy báo trang này an toàn' cũng không thể hạ kết luận của luật."""
    g_score = _gemini_score(g)
    if SEVERITY[g.verdict] > SEVERITY[h.verdict]:
        verdict, score, reasons = g.verdict, g_score, g.reasons + h.reasons
    elif SEVERITY[g.verdict] == SEVERITY[h.verdict]:
        verdict, score = h.verdict, max(h.score, g_score)
        reasons = g.reasons + h.reasons
    else:
        verdict, score, reasons = h.verdict, h.score, h.reasons + g.reasons

    unique = list(dict.fromkeys(reasons))[:6]
    return AnalyzeResponse(verdict=verdict, score=score, reasons=unique, source="gemini")


async def analyze(db, req: AnalyzeRequest) -> AnalyzeResponse:
    """Luồng: blacklist -> whitelist -> cache -> luật -> (Gemini) -> ghi cache."""
    candidates = candidate_domains(req.hostname)

    # Blacklist kiểm tra trước: nếu một tên miền nằm ở cả hai danh sách thì
    # blacklist thắng (an toàn hơn).
    if await db["blacklist"].find_one({"domain": {"$in": candidates}}):
        return AnalyzeResponse(
            verdict="phishing", score=1.0,
            reasons=["Tên miền nằm trong danh sách đen."], source="blacklist",
        )

    if await db["whitelist"].find_one({"domain": {"$in": candidates}}):
        return AnalyzeResponse(
            verdict="safe", score=0.0,
            reasons=["Tên miền nằm trong danh sách tin cậy."], source="whitelist",
        )

    key = cache_key(req.url)
    cached = await db["cache"].find_one({"key": key})
    if cached:
        result = AnalyzeResponse(**cached["result"])
        result.source = "cache"
        return result

    result = run_heuristics(req)
    gemini_failed = False

    if should_call_gemini(req, result):
        g = await gemini_client.classify_with_gemini(req)
        if g is None:
            gemini_failed = True  # dùng kết quả của luật, nhưng KHÔNG ghi cache
        else:
            result = merge(result, g)

    if not gemini_failed:
        await db["cache"].update_one(
            {"key": key},
            {"$set": {
                "key": key,
                "hostname": req.hostname,
                "result": result.model_dump(),
                "created_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    return result
