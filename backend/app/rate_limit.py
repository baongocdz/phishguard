import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .config import settings

# Lưu trong RAM: đủ cho 1 tiến trình trên Render free. Khởi động lại là mất,
# không sao vì chỉ cần chặn gọi dồn dập trong ngắn hạn.
_hits: dict[str, deque[float]] = defaultdict(deque)
WINDOW_SECONDS = 60.0


def client_ip(request: Request) -> str:
    # Render đứng trước app như một proxy nên IP thật nằm trong X-Forwarded-For.
    # Phần tử đầu có thể bị client tự điền, nên đây chỉ là chặn lạm dụng cơ bản.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def reset() -> None:
    _hits.clear()


async def limit_by_ip(request: Request) -> None:
    """Mỗi IP gọi tối đa settings.rate_limit_per_minute lần/phút, để người lạ
    không đốt hết hạn mức Gemini. Vượt quá thì trả 429 và extension tự dùng
    bộ luật cục bộ."""
    limit = settings.rate_limit_per_minute
    if limit <= 0:
        return
    now = time.monotonic()
    ip = client_ip(request)
    hits = _hits[ip]
    while hits and now - hits[0] > WINDOW_SECONDS:
        hits.popleft()
    if len(hits) >= limit:
        retry = int(WINDOW_SECONDS - (now - hits[0])) + 1
        raise HTTPException(
            status_code=429,
            detail="Quá nhiều yêu cầu, thử lại sau.",
            headers={"Retry-After": str(retry)},
        )
    hits.append(now)
    # Dọn IP không còn hoạt động để dict không phình mãi.
    if len(_hits) > 10_000:
        for key in [k for k, v in _hits.items() if not v or now - v[-1] > WINDOW_SECONDS]:
            del _hits[key]
