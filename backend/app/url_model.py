"""Mô hình XGBoost chấm tên miền, chạy bằng Python thuần.

Huấn luyện bằng eval/train_url_xgb.py, xuất cây ra url_model.json. Lúc chạy chỉ cần đi theo các cây
nên không phải cài xgboost trên Render (thư viện tốn thêm ~120 MB RAM). Khi xuất, script đã kiểm tra
kết quả ở đây khớp với xgboost.

Đặc trưng: n-gram ký tự của tên miền (có trong từ điển thì = 1) + 18 đặc trưng tự thiết kế
(app/url_features.py). Giống ma trận thưa lúc huấn luyện, đặc trưng bằng 0 coi là "thiếu" và đi theo
nhánh mặc định của cây.

Giải thích: mỗi bước đi từ nút cha xuống nút con làm giá trị dự đoán thay đổi một lượng, cộng lượng đó
cho đặc trưng của nút cha (phương pháp Saabas, xấp xỉ nhanh của SHAP). Báo cáo dùng TreeSHAP chính xác.
"""
import json
import math
import struct
from array import array
from pathlib import Path

from .domains import is_ip
from .url_features import FEATURE_NAMES, handcrafted_features, ngrams

MODEL_PATH = Path(__file__).with_name("url_model.json")

_model: dict | None = None
_loaded = False


def _f32(x: float) -> float:
    """Làm tròn về float32 như xgboost trước khi so với ngưỡng của cây."""
    return struct.unpack("f", struct.pack("f", x))[0]


def reload(path: Path = MODEL_PATH) -> None:
    global _model, _loaded
    _loaded = True
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _model = None
        return
    # Lưu cây bằng array để nhẹ RAM (list số của Python tốn ~32 byte mỗi phần tử).
    raw["trees"] = [{"left": array("i", t["left"]), "right": array("i", t["right"]),
                     "feature": array("i", t["feature"]), "threshold": array("f", t["threshold"]),
                     "default_left": array("b", t["default_left"]), "value": array("d", t["value"])}
                    for t in raw["trees"]]
    raw["vocab_list"] = raw["vocab"]
    raw["vocab"] = {g: i for i, g in enumerate(raw["vocab"])}
    _model = raw


def loaded() -> bool:
    if not _loaded:
        reload()
    return _model is not None


def thresholds() -> tuple[float, float]:
    """(high, low): xác suất từ đó cộng 0.3 / 0.15 điểm (chọn trên tập validation)."""
    return _model["bonus_high"], _model["bonus_low"]


def _features(host: str) -> dict[int, float]:
    vocab = _model["vocab"]
    x = {vocab[g]: 1.0 for g in ngrams(host, tuple(_model["ngram_range"])) if g in vocab}
    offset = len(vocab)
    for i, v in enumerate(handcrafted_features(host)):
        if v:
            x[offset + i] = _f32(v)
    return x


def _walk(tree: dict, x: dict[int, float], contrib: dict[int, float] | None) -> float:
    left, right, feature = tree["left"], tree["right"], tree["feature"]
    threshold, default_left, value = tree["threshold"], tree["default_left"], tree["value"]
    node = 0
    while left[node] != -1:
        f = feature[node]
        v = x.get(f)
        nxt = (left[node] if default_left[node] else right[node]) if v is None else \
            (left[node] if v < threshold[node] else right[node])
        if contrib is not None:
            contrib[f] = contrib.get(f, 0.0) + value[nxt] - value[node]
        node = nxt
    return value[node]


def predict(host: str) -> float | None:
    """Xác suất tên miền là lừa đảo (0..1); None nếu chưa có mô hình hoặc là IP."""
    if not loaded() or not host or is_ip(host):
        return None
    x = _features(host)
    z = _model["base_margin"] + sum(_walk(t, x, None) for t in _model["trees"])
    return 1 / (1 + math.exp(-max(-35.0, min(35.0, z))))


def _name(index: int) -> str:
    n_vocab = len(_model["vocab"])
    if index >= n_vocab:
        return FEATURE_NAMES[index - n_vocab]
    gram = _model["vocab_list"][index]
    where = "đầu tên miền" if gram.startswith("^") else "cuối tên miền" if gram.endswith("$") else "tên miền"
    return f"cụm ký tự '{gram.strip('^$')}' ở {where}"


def explain(host: str, k: int = 3) -> list[tuple[str, float]]:
    """k đặc trưng đẩy điểm về phía lừa đảo nhiều nhất: [(tên dễ đọc, mức đóng góp), ...]."""
    if not loaded() or not host or is_ip(host):
        return []
    x = _features(host)
    contrib: dict[int, float] = {}
    for t in _model["trees"]:
        _walk(t, x, contrib)
    merged: dict[str, float] = {}
    for i, c in contrib.items():
        merged[_name(i)] = merged.get(_name(i), 0.0) + c
    top = sorted(((n, c) for n, c in merged.items() if c > 0), key=lambda nc: -nc[1])
    return [(n, round(c, 2)) for n, c in top[:k]]
