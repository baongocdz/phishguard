"""Google Safe Browsing (Lookup API v4): danh sách trang độc hại của Google.

Miễn phí cho mục đích phi thương mại. Không có key (PHISHGUARD_SAFE_BROWSING_KEY)
thì bỏ qua lớp này. Lỗi mạng / hết hạn mức cũng chỉ bỏ qua, không làm hỏng kết quả.
https://developers.google.com/safe-browsing/v4/lookup-api
"""
import logging

import httpx

from .config import settings

log = logging.getLogger("phishguard.safebrowsing")

ENDPOINT = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
THREAT_LABEL = {
    "SOCIAL_ENGINEERING": "trang lừa đảo / giả mạo",
    "MALWARE": "phần mềm độc hại",
    "UNWANTED_SOFTWARE": "phần mềm không mong muốn",
    "POTENTIALLY_HARMFUL_APPLICATION": "ứng dụng có thể gây hại",
}


async def check(url: str) -> str | None:
    """Trả về loại mối đe dọa (vd 'SOCIAL_ENGINEERING') nếu Google đánh dấu URL, ngược lại None."""
    if not settings.safe_browsing_key:
        return None
    body = {
        "client": {"clientId": "phishguard", "clientVersion": "0.3.0"},
        "threatInfo": {
            "threatTypes": list(THREAT_LABEL),
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(ENDPOINT, params={"key": settings.safe_browsing_key}, json=body)
            resp.raise_for_status()
            matches = resp.json().get("matches") or []
            return matches[0]["threatType"] if matches else None
    except (httpx.HTTPError, ValueError, KeyError) as e:
        log.warning("Safe Browsing lỗi: %s", e)
        return None
