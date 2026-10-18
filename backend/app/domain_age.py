"""Tuổi tên miền qua RDAP (bản thay thế WHOIS, miễn phí, trả JSON).

Trang lừa đảo thường dùng tên miền vừa đăng ký vài ngày. rdap.org chuyển tiếp tới
máy chủ RDAP của nhà đăng ký phù hợp. Một số đuôi (vd .vn) chưa hỗ trợ RDAP → trả None
và lớp này tự bỏ qua. Kết quả được nhớ trong RAM để không hỏi lại liên tục.
"""
import logging
import time
from datetime import datetime, timezone

import httpx

from .domains import is_ip, is_lan_host, registrable_domain

log = logging.getLogger("phishguard.domain_age")

RDAP_URL = "https://rdap.org/domain/{}"
TIMEOUT = 3.0
_memo: dict[str, tuple[int | None, float]] = {}
MEMO_SECONDS = 6 * 3600
MEMO_MAX = 5000


def points_for(age_days: int | None) -> float:
    """Điểm cộng theo tuổi: < 14 ngày +0.3, < 90 ngày +0.15."""
    if age_days is None:
        return 0.0
    if age_days < 14:
        return 0.3
    if age_days < 90:
        return 0.15
    return 0.0


async def age_days(hostname: str) -> int | None:
    """Số ngày kể từ khi tên miền gốc được đăng ký, hoặc None nếu không tra được."""
    if not hostname or is_ip(hostname) or is_lan_host(hostname) or "." not in hostname:
        return None
    domain = registrable_domain(hostname)
    now = time.monotonic()
    hit = _memo.get(domain)
    if hit and now - hit[1] < MEMO_SECONDS:
        return hit[0]
    age = None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(RDAP_URL.format(domain), headers={"Accept": "application/rdap+json"})
        if resp.status_code == 200:
            for event in resp.json().get("events", []):
                if event.get("eventAction") == "registration":
                    created = datetime.fromisoformat(event["eventDate"].replace("Z", "+00:00"))
                    age = max(0, (datetime.now(timezone.utc) - created).days)
                    break
    except (httpx.HTTPError, ValueError, KeyError) as e:
        log.warning("RDAP lỗi với %s: %s", domain, e)
        return None  # lỗi mạng: không nhớ, lần sau thử lại
    if len(_memo) > MEMO_MAX:
        _memo.clear()
    _memo[domain] = (age, now)
    return age
