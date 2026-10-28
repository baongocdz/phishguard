"""Tên miền phổ biến (Tranco top 10.000, đã bỏ nền tảng bị lạm dụng): học máy không cộng điểm.
Danh sách sinh bằng scripts/build_popular.py, xem lý do ở đó."""
from pathlib import Path

from .domains import registrable_domain

PATH = Path(__file__).with_name("popular_domains.txt")
_domains: frozenset[str] | None = None


def is_popular(host: str) -> bool:
    global _domains
    if _domains is None:
        lines = PATH.read_text(encoding="utf-8").splitlines() if PATH.exists() else []
        _domains = frozenset(d for d in lines if d and not d.startswith("#"))
    return registrable_domain(host) in _domains
