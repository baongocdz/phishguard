"""Đặc trưng của tên miền, DÙNG CHUNG lúc huấn luyện (eval/) và lúc chạy (app/url_model.py).

Chỉ dùng tên miền, không dùng đường dẫn / giao thức: trong PhiUSIIL mọi URL hợp lệ đều có dạng
https://www.<domain> không có đường dẫn, mô hình học "có đường dẫn = lừa đảo" sẽ sai ngoài đời thật.
"""
import math
import re

from .domains import is_ip

NGRAM_RANGE = (3, 5)
_VOWELS = set("aeiou")

# Tên hiển thị của từng đặc trưng tự thiết kế (cùng thứ tự với handcrafted_features), dùng để giải thích kết quả.
FEATURE_NAMES = [
    "tên miền dài", "nhiều phần cách bởi dấu chấm", "nhiều dấu gạch ngang", "nhiều chữ số", "tỉ lệ chữ số cao",
    "tỉ lệ nguyên âm bất thường", "chuỗi ký tự lộn xộn (entropy)", "có phần tên rất dài", "độ dài đuôi tên miền",
    "đuôi tên miền hay bị lạm dụng", "chứa tên thương hiệu", "chứa từ dụ đăng nhập/xác minh", "dùng punycode",
    "có dãy số dài", "là địa chỉ IP", "đặt trên nền tảng tạo web miễn phí", "nhiều tầng subdomain",
    "ký tự lặp lại nhiều lần",
]


def prepare(host: str) -> str:
    """Chuẩn hóa tên miền trước khi cắt n-gram; ^ và $ đánh dấu đầu/cuối."""
    host = host.lower().rstrip(".")
    host = host.removeprefix("www.")
    return f"^{host}$"


def ngrams(host: str, ngram_range: tuple[int, int] = NGRAM_RANGE) -> set[str]:
    """Các n-gram ký tự (giống CountVectorizer(analyzer="char") của scikit-learn)."""
    text = prepare(host)
    lo, hi = ngram_range
    return {text[i:i + n] for n in range(lo, hi + 1) for i in range(len(text) - n + 1)}


def _entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = {c: s.count(c) for c in set(s)}
    return -sum(n / len(s) * math.log2(n / len(s)) for n in counts.values())


def handcrafted_features(host: str) -> list[float]:
    from .heuristics import BRANDS, LURE_WORDS, SUSPICIOUS_TLDS, _is_official, _tokens

    host = host.lower().removeprefix("www.")
    labels = host.split(".")
    name = ".".join(labels[:-1])
    letters = [c for c in name if c.isalpha()]
    tokens = _tokens(host)
    return [
        len(host),
        len(labels),
        host.count("-"),
        sum(c.isdigit() for c in host),
        sum(c.isdigit() for c in host) / max(1, len(host)),
        sum(c in _VOWELS for c in letters) / max(1, len(letters)),
        _entropy(name),
        max((len(x) for x in labels), default=0),
        len(labels[-1]),
        float(labels[-1] in SUSPICIOUS_TLDS),
        float(any(any(t.startswith(b) for t in tokens) and not _is_official(host, o) for b, o in BRANDS.items())),
        float(any(w in t for t in tokens for w in LURE_WORDS)),
        float("xn--" in host),
        float(bool(re.search(r"\d{4,}", host))),
        float(is_ip(host)),
        float(any(host.endswith(s) for s in ("firebaseapp.com", "web.app", "weebly.com", "wixsite.com",
                                              "godaddysites.com", "000webhostapp.com", "github.io",
                                              "netlify.app", "vercel.app", "pages.dev", "glitch.me"))),
        float(len(labels) > 3),
        float(bool(re.search(r"(.)\1{3,}", host))),
    ]
