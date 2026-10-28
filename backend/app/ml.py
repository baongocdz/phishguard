"""Mô hình ML chấm tên miền (Logistic Regression trên n-gram ký tự).

Huấn luyện bằng eval/evaluate.py (scikit-learn), xuất trọng số ra ml_model.json.
Lúc chạy chỉ cần cộng trọng số nên không phải cài scikit-learn trên Render.
"""
import json
import math
from pathlib import Path

from .domains import is_ip
from .url_features import prepare

MODEL_PATH = Path(__file__).with_name("ml_model.json")

_model: dict | None = None
_loaded = False


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


def combine(rule_score: float, prob: float | None, high: float = 0.9, low: float = 0.7) -> float:
    """Cộng điểm ML vào điểm luật. ML chỉ được cộng tối đa 0.3: một mình ML chỉ
    đẩy trang lên mức "đáng ngờ" (rồi Gemini xem tiếp), không tự kết luận lừa đảo.
    Ngưỡng high/low tùy mô hình (XGBoost chọn trên tập validation, xem app/url_model.py)."""
    if prob is None:
        return rule_score
    bonus = 0.3 if prob >= high else 0.15 if prob >= low else 0.0
    return min(1.0, round(rule_score + bonus, 2))
