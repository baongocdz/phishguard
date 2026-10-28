"""Nạp dữ liệu mẫu cho whitelist/blacklist. Chạy: python -m scripts.seed"""
from datetime import datetime, timezone

from pymongo import MongoClient

from app.config import settings

WHITELIST = [
    # Quốc tế
    "google.com", "github.com", "wikipedia.org", "microsoft.com", "anthropic.com", "apple.com",
    "facebook.com", "youtube.com", "paypal.com", "amazon.com", "netflix.com", "instagram.com",
    "stackoverflow.com", "reddit.com", "linkedin.com", "zoom.us", "notion.so", "chatgpt.com",
    # Việt Nam: báo chí, thương mại, ngân hàng, giáo dục, nhà nước
    "vnexpress.net", "tuoitre.vn", "dantri.com.vn", "thanhnien.vn", "24h.com.vn", "kenh14.vn",
    "zingnews.vn", "baomoi.com", "cafef.vn", "shopee.vn", "tiki.vn", "lazada.vn",
    "thegioididong.com", "dienmayxanh.com", "fptshop.com.vn", "cellphones.com.vn",
    "vietcombank.com.vn", "techcombank.com.vn", "vietinbank.vn", "bidv.com.vn", "agribank.com.vn",
    "mbbank.com.vn", "tpb.vn", "acb.com.vn", "vpbank.com.vn", "sacombank.com.vn", "hdbank.com.vn", "vib.com.vn",
    "shb.com.vn", "ocb.com.vn", "msb.com.vn", "seabank.com.vn", "vnpay.vn", "zalopay.vn", "momo.vn", "zalo.me", "viettel.vn", "fpt.com.vn", "vnpt.vn",
    "chinhphu.vn", "tdmu.edu.vn",
    # Chính trang PhishGuard (onrender.com là nơi ai cũng đăng web được nên chỉ tin đúng tên máy này) và Render.
    "phishguard-backend-g3w0.onrender.com", "render.com",
]
BLACKLIST = ["phish-sample.test"]  # Sau này nạp từ PhishTank/OpenPhish


def main() -> None:
    db = MongoClient(settings.mongo_uri)[settings.db_name]
    now = datetime.now(timezone.utc)
    for d in WHITELIST:
        db["whitelist"].update_one({"domain": d}, {"$set": {"domain": d, "source": "seed", "added_at": now}}, upsert=True)
    for d in BLACKLIST:
        db["blacklist"].update_one({"domain": d}, {"$set": {"domain": d, "source": "sample", "added_at": now}}, upsert=True)
    print(f"Đã nạp {len(WHITELIST)} whitelist, {len(BLACKLIST)} blacklist.")


if __name__ == "__main__":
    main()
