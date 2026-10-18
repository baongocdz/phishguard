"""Mô hình ML chấm tên miền (Logistic Regression trên n-gram ký tự).

Huấn luyện bằng eval/evaluate.py (scikit-learn), xuất trọng số ra ml_model.json.
Lúc chạy chỉ cần cộng trọng số nên không phải cài scikit-learn trên Render.
"""
import json
import math
import re
from pathlib import Path

from .domains import is_ip

NGRAM_RANGE = (3, 5)
MODEL_PATH = Path(__file__).with_name("ml_model.json")

_model: dict | None = None
_loaded = False


def prepare(host: str) -> str:
    """Chuẩn hóa tên miền trước khi cắt n-gram; ^ và $ đánh dấu đầu/cuối."""
    host = host.lower().rstrip(".")
    host = host.removeprefix("www.")
    return f"^{host}$"


def reload(path: Path = MODEL_PATH) -> None:
    global _model, _loaded
    _loaded = True
    try:
        _model = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _model = None


def predict(host: str) -> float | None:
    """Xác suất tên miền là lừa đảo (0..1); None nếu chưa có mô hình hoặc là IP."""
    if not _loaded:
        reload()
    if _model is None or not host or is_ip(host):
        return None
    text = prepare(host)
    lo, hi = _model["ngram_range"]
    grams = {text[i:i + n] for n in range(lo, hi + 1) for i in range(len(text) - n + 1)}
    weights = _model["weights"]
    z = _model["intercept"] + sum(weights.get(g, 0.0) for g in grams)
    return 1 / (1 + math.exp(-max(-35.0, min(35.0, z))))


def combine(rule_score: float, prob: float | None) -> float:
    """Cộng điểm ML vào điểm luật. ML chỉ được cộng tối đa 0.3: một mình ML chỉ
    đẩy trang lên mức "đáng ngờ" (rồi Gemini xem tiếp), không tự kết luận lừa đảo."""
    if prob is None:
        return rule_score
    bonus = 0.3 if prob >= 0.9 else 0.15 if prob >= 0.7 else 0.0
    return min(1.0, round(rule_score + bonus, 2))


# ---------- Đặc trưng tự thiết kế (dùng để so sánh trong báo cáo) ----------
_VOWELS = set("aeiou")


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
