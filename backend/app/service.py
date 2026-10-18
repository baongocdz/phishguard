import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from urllib.parse import urlsplit

from . import gemini_client
from .config import settings
from .domains import cache_key, candidate_domains, is_lan_host
from .gemini_client import GeminiOutput
from .email_rules import _domain_of, run_email_rules
from . import domain_age, ml, safebrowsing, shortlinks, text_ml
from .heuristics import BRANDS, _is_official, run_heuristics, verdict_of
from .schemas import AnalyzeRequest, AnalyzeResponse, EmailRequest, ReportRequest, Signal

log = logging.getLogger("phishguard.service")

SEVERITY = {"safe": 0, "suspicious": 1, "phishing": 2}
# Tăng khi đổi cách chấm hoặc định dạng kết quả để bỏ qua kết quả cũ trong cache
# (v2: có breakdown, tên miền na ná, Safe Browsing, mạng nội bộ).
CACHE_VERSION = "v2"


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
    reason = f"Mô hình học máy đánh giá tên miền giống trang lừa đảo ({prob:.0%})."
    signal = Signal(layer="ml", label=reason, points=round(score - result.score, 2))
    return AnalyzeResponse(verdict=verdict_of(score), score=score, reasons=result.reasons + [reason],
                           source=result.source, breakdown=result.breakdown + [signal])


async def apply_domain_age(req: AnalyzeRequest, result: AnalyzeResponse) -> AnalyzeResponse:
    """Tên miền mới đăng ký thì cộng điểm (xem app/domain_age.py). Bỏ qua khi đã chắc là
    lừa đảo (đỡ một lượt tra cứu) hoặc là tên miền chính chủ của thương hiệu."""
    if result.score >= 0.6 or _is_official(req.hostname.lower(), OFFICIAL_DOMAINS):
        return result
    # Chỉ tra khi đáng tra: người dùng chủ động kiểm tra (dán link, quét QR), trang có
    # form/mật khẩu, hoặc đã có dấu hiệu nghi ngờ. Trang đọc báo bình thường thì bỏ qua.
    worth = req.kind != "page" or req.has_password_field or req.form_count > 0 or result.score >= 0.2
    if not worth:
        return result
    age = await domain_age.age_days(req.hostname)
    points = domain_age.points_for(age)
    if not points:
        return result
    score = min(1.0, round(result.score + points, 2))
    reason = f"Tên miền mới đăng ký {age} ngày trước (trang lừa đảo thường dùng tên miền mới)."
    signal = Signal(layer="age", label=reason, points=round(score - result.score, 2))
    return AnalyzeResponse(verdict=verdict_of(score), score=score, reasons=result.reasons + [reason],
                           source=result.source, breakdown=result.breakdown + [signal])


def apply_text_ml(req: EmailRequest, result: AnalyzeResponse) -> AnalyzeResponse:
    """Cộng điểm từ mô hình học máy cho email/tin nhắn (app/text_ml.py), tối đa 0.3."""
    prob = text_ml.predict(f"{req.subject}\n{req.body}")
    score = ml.combine(result.score, prob)
    if score == result.score:
        return result
    reason = f"Mô hình học máy đánh giá nội dung giống email/tin nhắn lừa đảo ({prob:.0%})."
    signal = Signal(layer="ml", label=reason, points=round(score - result.score, 2))
    return AnalyzeResponse(verdict=verdict_of(score), score=score, reasons=result.reasons + [reason],
                           source=result.source, breakdown=result.breakdown + [signal])


def should_call_gemini(req: AnalyzeRequest, heuristic: AnalyzeResponse) -> bool:
    """Chỉ hỏi Gemini khi cần, để tiết kiệm hạn mức và độ trễ:
    - phải có API key;
    - luật chưa kết luận chắc chắn là phishing (điểm < 0.6);
    - trang có form/ô mật khẩu hoặc đã có dấu hiệu nghi ngờ từ luật."""
    if not settings.gemini_api_key or is_lan_host(req.hostname):
        return False  # không gửi nội dung trang trong mạng nội bộ ra ngoài
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
    label = {"safe": "an toàn", "suspicious": "đáng ngờ", "phishing": "lừa đảo"}[g.verdict]
    signal = Signal(layer="ai", points=round(max(0.0, score - h.score), 2),
                    label=f"Gemini đọc nội dung và kết luận: {label} (độ tin cậy {g.confidence:.0%}).")
    return AnalyzeResponse(verdict=verdict, score=score, reasons=unique, source="gemini",
                           breakdown=h.breakdown + [signal])


async def analyze(db, req: AnalyzeRequest) -> AnalyzeResponse:
    """Link rút gọn thì mở ra trước, rồi chấm trang đích thật."""
    if shortlinks.is_shortener(req.hostname):
        target = await shortlinks.expand(req.url)
        if target:
            parts = urlsplit(target)
            inner = req.model_copy(update={
                "url": target, "hostname": parts.hostname or "", "protocol": parts.scheme + ":",
            })
            result = await _analyze(db, inner)
            note = f"Link rút gọn {req.hostname} thực ra dẫn tới {inner.hostname}."
            return result.model_copy(update={
                "reasons": [note] + result.reasons,
                "breakdown": [Signal(layer="link", label=note, points=0.0)] + result.breakdown,
            })
    return await _analyze(db, req)


async def _analyze(db, req: AnalyzeRequest) -> AnalyzeResponse:
    """Luồng: blacklist -> whitelist -> cache -> luật -> (Gemini) -> ghi cache."""
    candidates = candidate_domains(req.hostname)
    key = f"{CACHE_VERSION}:{cache_key(req.url)}"

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
            breakdown=[Signal(layer="list", label=f"Danh sách đen: {black['domain']}", points=1.0)],
        )

    if white:
        return AnalyzeResponse(
            verdict="safe", score=0.0,
            reasons=["Tên miền nằm trong danh sách tin cậy."], source="whitelist",
            breakdown=[Signal(layer="list", label=f"Danh sách tin cậy: {white['domain']}", points=0.0)],
        )

    if cached:
        result = AnalyzeResponse(**cached["result"])
        result.source = "cache"
        return result

    # Danh sách trang độc hại của Google (chỉ hỏi khi chưa có trong cache).
    threat = await safebrowsing.check(req.url)
    if threat:
        label = safebrowsing.THREAT_LABEL.get(threat, threat)
        reason = f"Google Safe Browsing đánh dấu đây là {label}."
        result = AnalyzeResponse(verdict="phishing", score=1.0, reasons=[reason], source="safebrowsing",
                                 breakdown=[Signal(layer="intel", label=reason, points=1.0)])
        await _save_cache(db, key, req.hostname, result)
        return result

    result = await apply_domain_age(req, apply_ml(req, run_heuristics(req)))
    gemini_failed = False

    if should_call_gemini(req, result):
        g = await gemini_client.classify_with_gemini(req)
        if g is None:
            gemini_failed = True  # dùng kết quả của luật, nhưng KHÔNG ghi cache
        else:
            result = merge(result, g)

    if not gemini_failed:
        await _save_cache(db, key, req.hostname, result)
    return result


async def _save_cache(db, key: str, hostname: str, result: AnalyzeResponse) -> None:
    await db["cache"].update_one(
        {"key": key},
        {"$set": {"key": key, "hostname": hostname, "result": result.model_dump(),
                  "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


async def analyze_email(db, req: EmailRequest) -> AnalyzeResponse:
    """Luồng email: cache -> luật email -> (Gemini) -> ghi cache."""
    key = f"email:{CACHE_VERSION}:" + hashlib.sha256(
        f"{req.sender}\n{req.subject}\n{req.body}".encode()
    ).hexdigest()
    cached = await db["cache"].find_one({"key": key})
    if cached:
        result = AnalyzeResponse(**cached["result"])
        result.source = "cache"
        return result

    # Mở tối đa 3 link rút gọn trong email/tin nhắn để luật xét đích thật.
    short = [i for i, l in enumerate(req.links) if shortlinks.is_shortener(urlsplit(l.href).hostname or "")][:3]
    if short:
        targets = await asyncio.gather(*(shortlinks.expand(req.links[i].href) for i in short))
        links = list(req.links)
        for i, target in zip(short, targets):
            if target:
                links[i] = links[i].model_copy(update={"href": target})
        req = req.model_copy(update={"links": links})

    result = apply_text_ml(req, run_email_rules(req))
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


async def public_stats(db, metrics_csv) -> dict:
    import csv

    events = db["events"]
    total, phishing, suspicious, qr, email, black, white = await asyncio.gather(
        events.count_documents({}),
        events.count_documents({"verdict": "phishing"}),
        events.count_documents({"verdict": "suspicious"}),
        events.count_documents({"kind": "qr"}),
        events.count_documents({"kind": "email"}),
        db["blacklist"].count_documents({}),
        db["whitelist"].count_documents({}),
    )
    metrics = []
    try:
        with open(metrics_csv, encoding="utf-8-sig") as f:
            metrics = [{k: (v if k == "Phương pháp" else round(float(v), 3)) for k, v in row.items()}
                       for row in csv.DictReader(f)]
    except OSError:
        pass
    return {"total": total, "phishing": phishing, "suspicious": suspicious, "qr": qr, "email": email,
            "blacklist": black, "whitelist": white, "brands": len(BRANDS), "metrics": metrics}
