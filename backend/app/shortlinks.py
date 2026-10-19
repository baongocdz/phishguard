"""Mở link rút gọn (bit.ly, tinyurl...) để biết đích thật trước khi chấm điểm.

An toàn: tự đi theo từng bước chuyển hướng (tối đa MAX_HOPS), chỉ http/https,
không đi tới IP nội bộ / localhost (chống SSRF), chỉ đọc header, không tải trang.
"""
import ipaddress
import logging
from urllib.parse import urljoin, urlsplit

import httpx

log = logging.getLogger("phishguard.shortlinks")

SHORTENERS = {
    "bit.ly", "bitly.com", "tinyurl.com", "t.co", "goo.gl", "is.gd", "v.gd", "cutt.ly", "rb.gy",
    "shorturl.at", "s.id", "tiny.cc", "t.ly", "ow.ly", "buff.ly", "rebrand.ly", "bl.ink",
    "short.io", "tiny.one", "bom.so", "urlgon.com", "lnkd.in", "shorte.st", "1url.vn", "rutgon.me",
}
# Link qua hệ thống theo dõi lượt bấm của dịch vụ gửi thư / quảng bá ứng dụng: bản tin hợp lệ nào cũng dùng
# (chữ "tiki.vn" trỏ tới u123.ct.sendgrid.net). Mở ra như link rút gọn để biết đích thật.
TRACKERS = {
    "sendgrid.net", "list-manage.com", "mailchi.mp", "mandrillapp.com", "mailgun.org", "awstrack.me",
    "hubspotlinks.com", "sparkpostmail.com", "mjt.lu", "sendibt2.com", "sendibt3.com", "sendibm1.com",
    "exacttarget.com", "rs6.net", "createsend.com", "cmail19.com", "cmail20.com", "klclick.com", "klclick1.com",
    "convertkit-mail.com", "convertkit-mail2.com", "mailerlite.com", "mlsend.com", "elasticemail.com",
    "emltrk.com", "bnc.lt", "app.link", "onelink.me", "adj.st",
}
MAX_HOPS = 5
TIMEOUT = 4.0


def is_shortener(hostname: str) -> bool:
    host = hostname.lower().removeprefix("www.")
    return host in SHORTENERS


def is_tracker(hostname: str) -> bool:
    host = hostname.lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in TRACKERS)


def _safe_target(url: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    host = parts.hostname.lower()
    if host == "localhost" or host.endswith(".local") or host.endswith(".internal"):
        return False
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_global
    except ValueError:
        return True  # là tên miền (không phải IP)


async def expand(url: str, stop_at_destination: bool = False) -> str | None:
    """Trả về URL đích sau các bước chuyển hướng, hoặc None nếu không mở được.
    stop_at_destination: dừng ngay khi bước chuyển hướng trỏ ra ngoài các dịch vụ rút gọn / theo dõi, KHÔNG gửi
    yêu cầu tới trang đích (link theo dõi trong bản tin có thể là "Hủy đăng ký", "Xác nhận"...)."""
    current = url
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=TIMEOUT,
                                     headers={"User-Agent": "Mozilla/5.0 PhishGuard-link-check"}) as client:
            for _ in range(MAX_HOPS):
                if not _safe_target(current):
                    return None
                resp = await client.head(current)
                if resp.status_code in (405, 403, 400):  # có dịch vụ không nhận HEAD
                    resp = await client.get(current)
                location = resp.headers.get("location")
                if not resp.is_redirect or not location:
                    return current if current != url else None
                current = urljoin(current, location)
                host = urlsplit(current).hostname or ""
                if stop_at_destination and not (is_shortener(host) or is_tracker(host)):
                    return current if _safe_target(current) else None
            return current if _safe_target(current) else None
    except httpx.HTTPError as e:
        log.warning("Không mở được link rút gọn %s: %s", url, e)
        return None
