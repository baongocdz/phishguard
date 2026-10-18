import asyncio
import hashlib
import logging
from datetime import datetime, timezone

from . import gemini_client
from .config import settings
from .domains import cache_key, candidate_domains
from .gemini_client import GeminiOutput
from .email_rules import _domain_of, run_email_rules
from . import ml
from .heuristics import BRANDS, _is_official, run_heuristics
from .schemas import AnalyzeRequest, AnalyzeResponse, EmailRequest, ReportRequest

log = logging.getLogger("phishguard.service")

SEVERITY = {"safe": 0, "suspicious": 1, "phishing": 2}


OFFICIAL_DOMAINS = sorted({d for domains in BRANDS.values() for d in domains})


def apply_ml(req: AnalyzeRequest, result: AnalyzeResponse) -> AnalyzeResponse:
    """Cộng điểm từ mô hình ML (xem app/ml.py và eval/results/REPORT.md).
    Bỏ qua tên miền chính chủ của các thương hiệu: chính vì hay bị giả mạo nên
    mô hình dễ chấm nhầm tên miền thật (vd shopee.vn)."""
    host = req.hostname.lower()
    if _is_official(host, OFFICIAL_DOMAINS):
        return result
    prob = ml.predict(host)
    score = ml.combine(result.score, prob)
    if score == result.score:
        return result
    verdict = "phishing" if score >= 0.6 else "suspicious" if score >= 0.3 else "safe"
    reason = f"Mô hình học máy đánh giá tên miền giống trang lừa đảo ({prob:.0%})."
    return AnalyzeResponse(verdict=verdict, score=score, reasons=result.reasons + [reason],
                           source=result.source)


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
    key = cache_key(req.url)

    # Hỏi 3 bảng cùng lúc thay vì lần lượt: mỗi lượt tới Atlas mất vài trăm ms.
    black, white, cached = await asyncio.gather(
        db["blacklist"].find_one({"domain": {"$in": candidates}}),
        db["whitelist"].find_one({"domain": {"$in": candidates}}),
        db["cache"].find_one({"key": key}),
    )

    # Blacklist thắng nếu một tên miền nằm ở cả hai danh sách (an toàn hơn).
    if black:
        return AnalyzeResponse(
            verdict="phishing", score=1.0,
            reasons=["Tên miền nằm trong danh sách đen."], source="blacklist",
        )

    if white:
        return AnalyzeResponse(
            verdict="safe", score=0.0,
            reasons=["Tên miền nằm trong danh sách tin cậy."], source="whitelist",
        )

    if cached:
        result = AnalyzeResponse(**cached["result"])
        result.source = "cache"
        return result

    result = apply_ml(req, run_heuristics(req))
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


async def analyze_email(db, req: EmailRequest) -> AnalyzeResponse:
    """Luồng email: cache -> luật email -> (Gemini) -> ghi cache."""
    key = "email:" + hashlib.sha256(
        f"{req.sender}\n{req.subject}\n{req.body}".encode()
    ).hexdigest()
    cached = await db["cache"].find_one({"key": key})
    if cached:
        result = AnalyzeResponse(**cached["result"])
        result.source = "cache"
        return result

    result = run_email_rules(req)
    gemini_failed = False
    # Email do người dùng chủ động mở/dán nên hỏi Gemini khi luật chưa chắc chắn.
    if settings.gemini_api_key and result.score < 0.6:
        g = await gemini_client.classify_email(req)
        if g is None:
            gemini_failed = True
        else:
            result = merge(result, g)

    if not gemini_failed:
        await db["cache"].update_one(
            {"key": key},
            {"$set": {"key": key, "hostname": "", "result": result.model_dump(),
                      "created_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
    return result


async def record_event(db, kind: str, hostname: str, result: AnalyzeResponse) -> None:
    """Lưu lịch sử để dashboard thống kê. Chỉ lưu tên miền, không lưu URL đầy đủ
    hay nội dung email (có thể chứa thông tin cá nhân). Lỗi ghi log không được
    làm hỏng phản hồi cho người dùng."""
    if kind == "page" and result.verdict == "safe":
        hostname = ""  # trang an toàn người dùng tự mở: chỉ đếm, không lưu là trang nào
    try:
        await db["events"].insert_one({
            "kind": kind,
            "hostname": hostname,
            "verdict": result.verdict,
            "source": result.source,
            "score": result.score,
            "at": datetime.now(timezone.utc),
        })
    except Exception as e:
        log.warning("Không ghi được event: %s", e)


def sender_domain(req: EmailRequest) -> str:
    return _domain_of(req.sender)


async def save_report(db, req: ReportRequest) -> None:
    await db["reports"].insert_one({
        "url": req.url[:2048],
        "hostname": req.hostname.lower(),
        "kind": req.kind,
        "note": req.note,
        "at": datetime.now(timezone.utc),
    })
