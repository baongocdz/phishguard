"""API cho trang quản trị (dashboard). Mọi route đều cần header X-Admin-Token."""
import asyncio
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from .config import settings
from . import threatfeeds
from .deps import get_db


def require_admin(x_admin_token: str = Header(default="")) -> None:
    # Chưa đặt PHISHGUARD_ADMIN_TOKEN thì khóa hẳn trang quản trị.
    given, expected = x_admin_token.encode(), settings.admin_token.encode()
    # So bằng bytes: compare_digest với chuỗi có dấu tiếng Việt sẽ báo lỗi.
    if not expected or not secrets.compare_digest(given, expected):
        raise HTTPException(status_code=401, detail="Sai hoặc thiếu mã quản trị.")


router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])

ListName = Literal["whitelist", "blacklist"]
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9-]+\.)+[a-z]{2,}$")


def _clean(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


async def _agg(coll, pipeline: list[dict]) -> list[dict]:
    cursor = await coll.aggregate(pipeline)
    return await cursor.to_list()


@router.get("/stats")
async def stats(days: int = 7, db=Depends(get_db)):
    days = max(1, min(days, 90))
    # Gom theo ngày giờ Việt Nam để biểu đồ khớp với lịch người xem.
    vn = timezone(timedelta(hours=7))
    today = datetime.now(vn).replace(hour=0, minute=0, second=0, microsecond=0)
    since = today - timedelta(days=days - 1)
    match = {"$match": {"at": {"$gte": since}}}
    events = db["events"]

    def count_by(field: str):
        return _agg(events, [match, {"$group": {"_id": f"${field}", "n": {"$sum": 1}}}])

    by_verdict, by_source, by_kind, per_day, top_hosts, reports, wl, bl = await asyncio.gather(
        count_by("verdict"),
        count_by("source"),
        count_by("kind"),
        _agg(events, [
            match,
            {"$group": {
                "_id": {"day": {"$dateToString": {"format": "%Y-%m-%d", "date": "$at", "timezone": "+07:00"}},
                        "verdict": "$verdict"},
                "n": {"$sum": 1},
            }},
        ]),
        _agg(events, [
            match,
            {"$match": {"verdict": {"$ne": "safe"}, "hostname": {"$ne": ""}}},
            {"$group": {"_id": "$hostname", "n": {"$sum": 1}, "verdict": {"$max": "$verdict"},
                        "last": {"$max": "$at"}}},
            {"$sort": {"n": -1}},
            {"$limit": 10},
        ]),
        db["reports"].count_documents({}),
        db["whitelist"].count_documents({}),
        db["blacklist"].count_documents({}),
    )

    days_list = [(since + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    series = {v: [0] * days for v in ("safe", "suspicious", "phishing")}
    for row in per_day:
        day, verdict = row["_id"]["day"], row["_id"]["verdict"]
        if day in days_list and verdict in series:
            series[verdict][days_list.index(day)] = row["n"]

    def as_dict(rows):
        return {str(r["_id"]): r["n"] for r in rows}

    return {
        "days": days,
        "by_verdict": as_dict(by_verdict),
        "by_source": as_dict(by_source),
        "by_kind": as_dict(by_kind),
        "per_day": {"labels": days_list, **series},
        "top_hosts": [{"hostname": r["_id"], "count": r["n"], "verdict": r["verdict"],
                       "last": r["last"]} for r in top_hosts],
        "reports": reports,
        "whitelist": wl,
        "blacklist": bl,
        "openphish": await db["meta"].find_one({"_id": "openphish"}, {"_id": 0}),
    }


@router.get("/events")
async def recent_events(limit: int = 50, flagged: bool = True, db=Depends(get_db)):
    flt = {"verdict": {"$ne": "safe"}} if flagged else {}
    docs = await db["events"].find(flt).sort("at", -1).limit(max(1, min(limit, 200))).to_list()
    return [_clean(d) for d in docs]


@router.get("/reports")
async def list_reports(limit: int = 100, db=Depends(get_db)):
    docs = await db["reports"].find({}).sort("at", -1).limit(max(1, min(limit, 500))).to_list()
    return [_clean(d) for d in docs]


@router.delete("/reports/{report_id}")
async def delete_report(report_id: str, db=Depends(get_db)):
    try:
        oid = ObjectId(report_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Không tìm thấy báo cáo.")
    await db["reports"].delete_one({"_id": oid})
    return {"ok": True}


class DomainIn(BaseModel):
    domain: str = Field(max_length=253)


@router.get("/lists/{name}")
async def get_list(name: ListName, q: str = "", limit: int = 300, db=Depends(get_db)):
    """Tìm trên server vì danh sách đen có thể có hàng nghìn mục (OpenPhish)."""
    flt = {"domain": {"$regex": re.escape(q.strip().lower())}} if q.strip() else {}
    # Mục do quản trị viên/mẫu thêm hiện trước, mục từ OpenPhish sau.
    docs = await db[name].find(flt).sort([("source", 1), ("domain", 1)]).limit(max(1, min(limit, 1000))).to_list()
    return {"total": await db[name].count_documents(flt),
            "items": [{"domain": d["domain"], "source": d.get("source", ""), "added_at": d.get("added_at")}
                      for d in docs]}


@router.post("/feeds/openphish")
async def sync_openphish(db=Depends(get_db)):
    try:
        return await threatfeeds.sync_openphish(db)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Không tải được OpenPhish: {e}")


@router.post("/lists/{name}")
async def add_domain(name: ListName, body: DomainIn, db=Depends(get_db)):
    domain = body.domain.strip().lower().removeprefix("www.").rstrip(".")
    if not DOMAIN_RE.match(domain):
        raise HTTPException(status_code=422, detail="Tên miền không hợp lệ.")
    other = "blacklist" if name == "whitelist" else "whitelist"
    await db[other].delete_one({"domain": domain})  # một tên miền chỉ ở một danh sách
    await db[name].update_one(
        {"domain": domain},
        {"$set": {"domain": domain, "source": "admin", "added_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    # Xóa kết quả cũ trong cache để thay đổi có hiệu lực ngay.
    await db["cache"].delete_many({"hostname": {"$regex": f"(^|\\.){re.escape(domain)}$"}})
    return {"ok": True, "domain": domain}


@router.delete("/lists/{name}/{domain}")
async def remove_domain(name: ListName, domain: str, db=Depends(get_db)):
    await db[name].delete_one({"domain": domain.lower()})
    return {"ok": True}
