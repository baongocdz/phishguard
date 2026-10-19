"""Xuất danh sách thương hiệu (heuristics.py) cho extension: extension/src/brands.json.

Chạy sau khi sửa BRANDS / USER_CONTENT / BRAND_SUFFIXES:  python -m scripts.export_brands
(test_brands_json_matches_backend báo lỗi nếu quên chạy.)
"""
import json
from pathlib import Path

from app.heuristics import BRAND_SUFFIXES, BRANDS, SHORT_BRAND, USER_CONTENT

OUT = Path(__file__).resolve().parents[2] / "extension" / "src" / "brands.json"


def data() -> dict:
    return {"_note": "Sinh từ backend/app/heuristics.py bằng: python -m scripts.export_brands. Đừng sửa tay.",
            "brands": BRANDS, "userContent": USER_CONTENT, "shortBrand": SHORT_BRAND,
            "brandSuffixes": list(BRAND_SUFFIXES)}


if __name__ == "__main__":
    OUT.write_text(json.dumps(data(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: {OUT}")
