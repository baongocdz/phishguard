"""Tự cập nhật danh sách đen từ OpenPhish Community Feed (miễn phí, ~300 URL lừa đảo
đang hoạt động, https://openphish.com/feed.txt).

- Chỉ lưu đúng tên máy (host) trong URL, vd `abc.pages.dev`, không bao giờ chặn cả nền
  tảng chung (`pages.dev`, `github.io`...).
- Bỏ qua tên miền trong danh sách tin cậy / chính chủ thương hiệu và địa chỉ mạng nội bộ.
- Mục do quản trị viên thêm tay không bị ghi đè; mục OpenPhish không còn xuất hiện
  trong feed quá STALE_DAYS ngày thì tự xóa.
"""
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx
from pymongo import UpdateOne

from .domains import candidate_domains, is_lan_host
from .heuristics import BRANDS

log = logging.getLogger("phishguard.threatfeeds")

OPENPHISH_URL = "https://openphish.com/feed.txt"
SOURCE = "openphish"
STALE_DAYS = 7
SYNC_EVERY_HOURS = 12
OFFICIAL = {d for domains in BRANDS.values() for d in domains}
# Nền tảng cho người dùng tự đăng trang: không chặn cả nền tảng, nhưng VẪN chặn được từng
# trang con (vd vigya-29.github.io) dù github.io nằm trong tên miền chính chủ của GitHub.
USER_CONTENT = {
    "github.io", "pages.dev", "web.app", "firebaseapp.com", "vercel.app", "netlify.app",
    "blogspot.com", "googleusercontent.com", "amazonaws.com", "glitch.me", "weebly.com",
    "wixsite.com", "godaddysites.com", "gitbook.io", "typedream.app", "azurewebsites.net",
}


def parse_feed(text: str, trusted: set[str]) -> set[str]:
    """Lấy tên máy từ từng URL trong feed, bỏ những tên không được phép chặn."""
    hosts = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            host = (urlsplit(line if "://" in line else "http://" + line).hostname or "").lower().rstrip(".")
        except ValueError:
            continue
        if not host or "." not in host or is_lan_host(host) or host in USER_CONTENT:
            continue
        if any((c in trusted or c in OFFICIAL) and c not in USER_CONTENT for c in candidate_domains(host)):
            continue  # vd docs.google.com: không thể chặn cả Google
        hosts.add(host)
    return hosts


async def sync_openphish(db) -> dict:
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(OPENPHISH_URL)
        resp.raise_for_status()
    trusted = {d["domain"] for d in await db["whitelist"].find({}, {"domain": 1}).to_list()}
    hosts = parse_feed(resp.text, trusted)
    now = datetime.now(timezone.utc)

    before = await db["blacklist"].count_documents({"source": SOURCE})
    if hosts:
        await db["blacklist"].bulk_write([
            UpdateOne({"domain": h},
                      {"$setOnInsert": {"domain": h, "source": SOURCE, "added_at": now},
                       "$set": {"seen_at": now}},
                      upsert=True)
            for h in hosts
        ], ordered=False)
        # Kết quả cũ trong cache của các tên miền này không còn đúng nữa.
        await db["cache"].delete_many({"hostname": {"$in": list(hosts)}})
    removed = (await db["blacklist"].delete_many(
        {"source": SOURCE, "seen_at": {"$lt": now - timedelta(days=STALE_DAYS)}})).deleted_count
    total = await db["blacklist"].count_documents({"source": SOURCE})
    info = {"last_sync": now, "in_feed": len(hosts), "added": max(0, total - before + removed),
            "removed": removed, "total": total}
    await db["meta"].update_one({"_id": SOURCE}, {"$set": info}, upsert=True)
    log.info("OpenPhish: %s", info)
    return info


async def sync_if_stale(db) -> None:
    """Gọi lúc khởi động: quá SYNC_EVERY_HOURS giờ chưa cập nhật thì cập nhật (lỗi thì bỏ qua)."""
    try:
        meta = await db["meta"].find_one({"_id": SOURCE})
        last = meta and meta.get("last_sync")
        if last and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last and datetime.now(timezone.utc) - last < timedelta(hours=SYNC_EVERY_HOURS):
            return
        await sync_openphish(db)
    except Exception as e:  # mạng lỗi, OpenPhish bảo trì... không được làm sập server
        log.warning("Không cập nhật được OpenPhish: %s", e)
