"""Huấn luyện + đánh giá mô hình email/tin nhắn lừa đảo.

Chạy (từ thư mục backend):
    python -m eval.evaluate_text <đường-dẫn>/texts.json

Dữ liệu: ealvaradob/phishing-dataset (Hugging Face, Apache-2.0), file texts.json —
email và SMS tiếng Anh, nhãn 1 = lừa đảo, 0 = bình thường.
https://huggingface.co/datasets/ealvaradob/phishing-dataset

Kết quả ghi vào eval/results/TEXT_REPORT.md, mô hình ghi vào app/text_model.json.
"""
import json
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score)
from sklearn.model_selection import train_test_split

from app import text_ml
from app.email_rules import run_email_rules
from app.schemas import EmailRequest

from .evaluate import plot_confusion

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results"
SEED = 42


def row(name, y, pred, prob=None):
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {"Phương pháp": name, "Accuracy": accuracy_score(y, pred),
            "Precision": precision_score(y, pred, zero_division=0),
            "Recall": recall_score(y, pred, zero_division=0), "F1": f1_score(y, pred, zero_division=0),
            "ROC-AUC": roc_auc_score(y, prob) if prob is not None else float("nan"),
            "FPR": fp / (fp + tn) if fp + tn else 0.0}


def main(path: str) -> None:
    t0 = time.time()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    df = pd.DataFrame(data).dropna()
    df["text"] = df["text"].astype(str).str.slice(0, 20000)
    df = df.drop_duplicates("text")
    train, test = train_test_split(df, test_size=0.2, stratify=df["label"], random_state=SEED)
    print(f"{len(df):,} văn bản ({df.label.sum():,} lừa đảo). Train {len(train):,} / Test {len(test):,}")

    vec = CountVectorizer(analyzer=text_ml.features, binary=True, min_df=5, max_features=40000)
    Xtr = vec.fit_transform(train["text"])
    Xte = vec.transform(test["text"])
    lr = LogisticRegression(C=0.5, max_iter=3000).fit(Xtr, train["label"])
    p = lr.predict_proba(Xte)[:, 1]
    y = test["label"].to_numpy()

    # Bộ luật email (chỉ có nội dung, không có người gửi/link) để so sánh
    r_score = np.array([run_email_rules(EmailRequest(body=t)).score for t in test["text"]])

    rows = [
        row("Bộ luật email (chỉ nội dung)", y, (r_score >= 0.3).astype(int), r_score),
        row("ML: Logistic Regression (từ + cặp từ)", y, (p >= 0.5).astype(int), p),
    ]

    weights = {g: round(float(w), 4) for g, w in zip(vec.get_feature_names_out(), lr.coef_[0]) if abs(w) >= 0.02}
    model_path = ROOT.parent / "app" / "text_model.json"
    model_path.write_text(json.dumps({
        "type": "word_bigram_logreg", "intercept": round(float(lr.intercept_[0]), 4),
        "weights": weights, "trained_on": "ealvaradob/phishing-dataset texts.json", "n_train": int(len(train)),
    }, ensure_ascii=False), encoding="utf-8")
    text_ml.reload(model_path)
    covered = [text_ml.predict(t) for t in test["text"].iloc[:2000]]
    coverage = sum(c is not None for c in covered) / len(covered)

    plot_confusion(y, (p >= 0.5).astype(int), "ML email/SMS (ngưỡng 0.5)", OUT / "cm_text_ml.png")
    top = sorted(weights.items(), key=lambda kv: kv[1])
    feat = ("| Từ nghiêng về LỪA ĐẢO | trọng số | Từ nghiêng về BÌNH THƯỜNG | trọng số |\n|---|---|---|---|\n"
            + "\n".join(f"| `{a[0]}` | {a[1]:.2f} | `{b[0]}` | {b[1]:.2f} |" for a, b in zip(top[::-1][:15], top[:15])))
    table = pd.DataFrame(rows).to_markdown(index=False, floatfmt=".3f")
    (OUT / "TEXT_REPORT.md").write_text(f"""# Đánh giá mô hình email / tin nhắn

- Dữ liệu: ealvaradob/phishing-dataset (`texts.json`, email + SMS tiếng Anh, Apache-2.0),
  {len(df):,} văn bản sau khi bỏ trùng ({df.label.sum():,} lừa đảo).
- Chia train/test 80/20 phân tầng, `random_state={SEED}`. Test: {len(test):,} văn bản.
- Bộ luật email ở đây chỉ được xem nội dung (dataset không có người gửi / link riêng),
  nên thiệt thòi hơn khi chạy thật.

{table}

Mô hình chỉ cho điểm khi văn bản có ít nhất {text_ml.MIN_KNOWN} từ/cặp từ nó biết:
{coverage:.0%} văn bản test đạt điều kiện này. Tin nhắn tiếng Việt thường không đạt,
khi đó hệ thống dựa vào bộ luật (có từ khóa tiếng Việt) và Gemini.

![](cm_text_ml.png)

## Mô hình học được gì

{feat}

_Tạo bởi `eval/evaluate_text.py` trong {time.time() - t0:.0f} giây._
""", encoding="utf-8")
    print(table)
    print(f"Độ phủ: {coverage:.0%}. Mô hình: {model_path} ({model_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main(sys.argv[1])
