"""Nạp dữ liệu mẫu cho whitelist/blacklist. Chạy: python -m scripts.seed"""
from datetime import datetime, timezone

from pymongo import MongoClient

from app.config import settings

WHITELIST = ["google.com", "github.com", "wikipedia.org", "microsoft.com", "anthropic.com"]
BLACKLIST = ["phish-sample.test"]  # Sau này nạp từ PhishTank/OpenPhish


def main() -> None:
    db = MongoClient(settings.mongo_uri)[settings.db_name]
    now = datetime.now(timezone.utc)
    for d in WHITELIST:
        db["whitelist"].update_one({"domain": d}, {"$set": {"domain": d, "added_at": now}}, upsert=True)
    for d in BLACKLIST:
        db["blacklist"].update_one({"domain": d}, {"$set": {"domain": d, "source": "sample", "added_at": now}}, upsert=True)
    print(f"Đã nạp {len(WHITELIST)} whitelist, {len(BLACKLIST)} blacklist.")


if __name__ == "__main__":
    main()
