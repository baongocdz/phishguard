"""Mô hình học máy cho email / tin nhắn (Logistic Regression trên từ và cặp từ).

Huấn luyện bằng eval/evaluate_text.py, xuất trọng số ra text_model.json; lúc chạy
chỉ cần cộng trọng số (không cần scikit-learn). Dữ liệu huấn luyện là tiếng Anh,
nên mô hình chỉ cho điểm khi văn bản có đủ từ mà nó biết (xem MIN_KNOWN).
"""
import json
import math
import re
from pathlib import Path

MODEL_PATH = Path(__file__).with_name("text_model.json")
WORD_RE = re.compile(r"[a-z0-9']+")
MIN_KNOWN = 12  # cần ít nhất chừng này từ/cặp từ có trong mô hình mới tin kết quả

_model: dict | None = None
_loaded = False


def features(text: str) -> list[str]:
    """Từ đơn + cặp từ liền nhau (không trùng). Dùng chung cho huấn luyện và lúc chạy."""
    words = WORD_RE.findall(text.lower())[:2000]
    grams = set(words)
    grams.update(f"{a} {b}" for a, b in zip(words, words[1:]))
    return sorted(grams)


def reload(path: Path = MODEL_PATH) -> None:
    global _model, _loaded
    _loaded = True
    try:
        _model = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _model = None


def predict(text: str) -> float | None:
    """Xác suất là lừa đảo (0..1), hoặc None nếu chưa có mô hình / văn bản quá lạ với mô hình."""
    if not _loaded:
        reload()
    if _model is None or not text.strip():
        return None
    weights = _model["weights"]
    known = [weights[g] for g in features(text) if g in weights]
    if len(known) < MIN_KNOWN:
        return None
    z = _model["intercept"] + sum(known)
    return 1 / (1 + math.exp(-max(-35.0, min(35.0, z))))
