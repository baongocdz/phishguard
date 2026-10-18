"""Đánh giá PhishGuard trên bộ dữ liệu PhiUSIIL và huấn luyện mô hình ML.

Chạy (từ thư mục backend):
    pip install -r eval/requirements-eval.txt
    python -m eval.evaluate <đường-dẫn>/PhiUSIIL_Phishing_URL_Dataset.csv [--gemini 100]

Tải dataset: https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset

LƯU Ý VỀ DỮ LIỆU: trong PhiUSIIL, 100% URL hợp lệ có dạng "https://www.<domain>"
không có đường dẫn, còn URL lừa đảo thì đủ kiểu. Huấn luyện trên URL đầy đủ thì
mô hình chỉ học mẹo "có www + không có path = an toàn" và đạt ~100% một cách vô
nghĩa. Vì vậy ở đây chỉ dùng TÊN MIỀN (đã bỏ "www."), bỏ giao thức và đường dẫn,
và loại trùng tên miền.

Kết quả ghi vào eval/results/, mô hình ghi vào app/ml_model.json.
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score, roc_curve)
from sklearn.model_selection import train_test_split

from app.heuristics import run_heuristics
from app.ml import NGRAM_RANGE, combine, handcrafted_features, prepare
from app.schemas import AnalyzeRequest

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results"
MODEL_PATH = ROOT.parent / "app" / "ml_model.json"
SEED = 42


def load(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, usecols=["URL", "label"], encoding="utf-8-sig")
    df["host"] = df["URL"].map(lambda u: (urlsplit(u if "://" in u else "http://" + u).hostname or "").lower())
    df["host"] = df["host"].str.removeprefix("www.").str.rstrip(".")
    df = df[df["host"].str.contains(r"\.", regex=True)]
    df["y"] = (df["label"] == 0).astype(int)  # PhiUSIIL: label 0 = phishing, 1 = hợp lệ
    # Một tên miền chỉ giữ một dòng; bỏ tên miền vừa có nhãn lừa đảo vừa hợp lệ.
    conflict = df.groupby("host")["y"].nunique()
    df = df[df["host"].isin(conflict[conflict == 1].index)].drop_duplicates("host")
    return df[["host", "y"]].reset_index(drop=True)


def rules_score(host: str) -> float:
    # Cố định https và không có ô mật khẩu để luật chỉ xét tên miền như ML.
    return run_heuristics(AnalyzeRequest(url=f"https://{host}/", hostname=host, protocol="https:")).score


def metrics(name: str, y, pred, prob=None) -> dict:
    row = {
        "Phương pháp": name,
        "Accuracy": accuracy_score(y, pred),
        "Precision": precision_score(y, pred, zero_division=0),
        "Recall": recall_score(y, pred, zero_division=0),
        "F1": f1_score(y, pred, zero_division=0),
        "ROC-AUC": roc_auc_score(y, prob) if prob is not None else float("nan"),
    }
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    row["FPR"] = fp / (fp + tn) if fp + tn else 0.0  # tỉ lệ chặn nhầm trang thật
    return row


def plot_confusion(y, pred, title: str, path: Path) -> None:
    cm = confusion_matrix(y, pred, labels=[0, 1])
    fig, ax = plt.subplots(figsize=(4, 3.6))
    ax.imshow(cm, cmap="Blues")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{cm[i, j]:,}", ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black", fontsize=12)
    ax.set_xticks([0, 1], ["Hợp lệ", "Lừa đảo"])
    ax.set_yticks([0, 1], ["Hợp lệ", "Lừa đảo"])
    ax.set_xlabel("Dự đoán")
    ax.set_ylabel("Thực tế")
    ax.set_title(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


async def gemini_sample(hosts: list[str]) -> list[float | None]:
    from app import gemini_client
    from app.service import _gemini_score

    out = []
    for i, h in enumerate(hosts):
        req = AnalyzeRequest(url=f"https://{h}/", hostname=h, protocol="https:")
        g = None
        for attempt in range(3):  # hạn mức miễn phí có thể trả 429: đợi rồi thử lại
            g = await gemini_client.classify_with_gemini(req)
            if g is not None:
                break
            await asyncio.sleep(5 * (attempt + 1))
        out.append(_gemini_score(g) if g else None)
        print(f"  Gemini {i + 1}/{len(hosts)}", end="\r", flush=True)
    print()
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--gemini", type=int, default=0, help="số tên miền (chia đôi 2 nhãn) để thử Gemini")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    t0 = time.time()
    df = load(args.csv)
    train, test = train_test_split(df, test_size=0.2, stratify=df["y"], random_state=SEED)
    print(f"Dữ liệu sau khi làm sạch: {len(df):,} tên miền "
          f"({df.y.sum():,} lừa đảo / {(1 - df.y).sum():,} hợp lệ). Train {len(train):,} / Test {len(test):,}")

    rows = []
    y = test["y"].to_numpy()

    # 1. Bộ luật
    t = time.perf_counter()
    r_score = np.array([rules_score(h) for h in test["host"]])
    rules_ms = (time.perf_counter() - t) / len(test) * 1000
    rows.append(metrics("Bộ luật (ngưỡng 0.3 – đáng ngờ trở lên)", y, (r_score >= 0.3).astype(int), r_score))
    rows.append(metrics("Bộ luật (ngưỡng 0.6 – chỉ lừa đảo)", y, (r_score >= 0.6).astype(int), r_score))

    # 2. ML trên đặc trưng tự thiết kế
    Xtr_f = np.array([handcrafted_features(h) for h in train["host"]])
    Xte_f = np.array([handcrafted_features(h) for h in test["host"]])
    hgb = HistGradientBoostingClassifier(random_state=SEED).fit(Xtr_f, train["y"])
    p_hgb = hgb.predict_proba(Xte_f)[:, 1]
    rows.append(metrics("ML: Gradient Boosting (18 đặc trưng)", y, (p_hgb >= 0.5).astype(int), p_hgb))

    # 3. ML trên n-gram ký tự của tên miền (mô hình được triển khai)
    vec = CountVectorizer(analyzer="char", ngram_range=NGRAM_RANGE, binary=True, min_df=10, max_features=40000)
    Xtr = vec.fit_transform(train["host"].map(prepare))
    Xte = vec.transform(test["host"].map(prepare))
    lr = LogisticRegression(C=1.0, max_iter=2000).fit(Xtr, train["y"])
    t = time.perf_counter()
    p_lr = lr.predict_proba(Xte)[:, 1]
    rows.append(metrics("ML: Logistic Regression (n-gram ký tự)", y, (p_lr >= 0.5).astype(int), p_lr))

    # 4. Kết hợp như backend: luật + điểm cộng từ ML
    c_score = np.array([combine(s, p) for s, p in zip(r_score, p_lr)])
    rows.append(metrics("Kết hợp: luật + ML (cách backend dùng)", y, (c_score >= 0.3).astype(int), c_score))

    # Xuất mô hình cho backend
    vocab = vec.get_feature_names_out()
    weights = {g: round(float(w), 4) for g, w in zip(vocab, lr.coef_[0]) if abs(w) >= 0.01}
    MODEL_PATH.write_text(json.dumps({
        "type": "char_ngram_logreg", "ngram_range": list(NGRAM_RANGE),
        "intercept": round(float(lr.intercept_[0]), 4), "weights": weights,
        "trained_on": "PhiUSIIL (tên miền, đã bỏ www và loại trùng)", "n_train": int(len(train)),
    }, ensure_ascii=False), encoding="utf-8")

    # Kiểm tra mô hình xuất ra cho kết quả y hệt sklearn
    from app import ml
    ml.reload(MODEL_PATH)
    sample = test["host"].iloc[:500]
    diff = max(abs(ml.predict(h) - p) for h, p in zip(sample, p_lr[:500]))
    ml_ms = (lambda t0: [ml.predict(h) for h in sample] and (time.perf_counter() - t0) / len(sample) * 1000)(time.perf_counter())
    print(f"Sai khác giữa mô hình JSON và sklearn: {diff:.2e}")

    # 5. Gemini trên một mẫu nhỏ (tốn hạn mức nên chỉ chạy khi yêu cầu)
    gem_note = ""
    if args.gemini:
        half = args.gemini // 2
        samp = pd.concat([test[test.y == 1].sample(half, random_state=SEED),
                          test[test.y == 0].sample(half, random_state=SEED)])
        print(f"Đang hỏi Gemini {len(samp)} tên miền…")
        t = time.perf_counter()
        g = asyncio.run(gemini_sample(samp["host"].tolist()))
        gem_ms = (time.perf_counter() - t) / len(samp) * 1000
        ok = [i for i, s in enumerate(g) if s is not None]
        ys = samp["y"].to_numpy()[ok]
        gs = np.array([g[i] for i in ok])
        idx = samp.index
        rs = np.array([rules_score(h) for h in samp["host"]])[ok]
        ps = lr.predict_proba(vec.transform(samp["host"].map(prepare)))[:, 1][ok]
        sub = [
            metrics("Bộ luật (cùng mẫu)", ys, (rs >= 0.3).astype(int), rs),
            metrics("ML n-gram (cùng mẫu)", ys, (ps >= 0.5).astype(int), ps),
            metrics("Gemini (chỉ xem URL)", ys, (gs >= 0.3).astype(int), gs),
        ]
        gem_note = (f"\n### So sánh với Gemini trên mẫu {len(ok)} tên miền (cân bằng 2 nhãn)\n\n"
                    + pd.DataFrame(sub).to_markdown(index=False, floatfmt=".3f")
                    + f"\n\nGemini trả lời {len(ok)}/{len(samp)} lần, trung bình {gem_ms:.0f} ms/lần "
                      "(gồm cả thời gian chờ khi bị giới hạn).\n")

    # Biểu đồ
    plot_confusion(y, (r_score >= 0.3).astype(int), "Bộ luật (ngưỡng 0.3)", OUT / "cm_rules.png")
    plot_confusion(y, (p_lr >= 0.5).astype(int), "ML n-gram (ngưỡng 0.5)", OUT / "cm_ml.png")
    plot_confusion(y, (c_score >= 0.3).astype(int), "Kết hợp luật + ML", OUT / "cm_combined.png")
    fig, ax = plt.subplots(figsize=(5, 4.2))
    for name, prob in [("Bộ luật", r_score), ("Gradient Boosting", p_hgb),
                       ("LogReg n-gram", p_lr), ("Kết hợp", c_score)]:
        fpr, tpr, _ = roc_curve(y, prob)
        ax.plot(fpr, tpr, label=f"{name} (AUC={roc_auc_score(y, prob):.3f})")
    ax.plot([0, 1], [0, 1], "k--", lw=0.8)
    ax.set_xlabel("Tỉ lệ chặn nhầm (FPR)")
    ax.set_ylabel("Tỉ lệ phát hiện (TPR)")
    ax.legend(fontsize=8)
    ax.set_title("Đường ROC trên tập test")
    fig.tight_layout()
    fig.savefig(OUT / "roc.png", dpi=150)
    plt.close(fig)

    top = sorted(weights.items(), key=lambda kv: kv[1])
    feat_md = ("| n-gram nghiêng về LỪA ĐẢO | trọng số | n-gram nghiêng về HỢP LỆ | trọng số |\n|---|---|---|---|\n"
               + "\n".join(f"| `{a[0]}` | {a[1]:.2f} | `{b[0]}` | {b[1]:.2f} |"
                           for a, b in zip(top[::-1][:15], top[:15])))

    table = pd.DataFrame(rows).to_markdown(index=False, floatfmt=".3f")
    report = f"""# Kết quả đánh giá PhishGuard

- Dữ liệu: PhiUSIIL Phishing URL Dataset (UCI, 2024), {len(df):,} tên miền sau khi làm sạch
  ({df.y.sum():,} lừa đảo / {(1 - df.y).sum():,} hợp lệ).
- Chia train/test 80/20 phân tầng theo nhãn, `random_state={SEED}`. Test: {len(test):,} tên miền.
- Chỉ dùng tên miền (bỏ `www.`, giao thức, đường dẫn) để tránh "mẹo" của dataset
  (100% URL hợp lệ có dạng `https://www.<domain>` không có đường dẫn).
- FPR = tỉ lệ trang hợp lệ bị chặn nhầm (càng thấp càng tốt).

## Kết quả trên tập test

{table}

Thời gian xử lý trung bình: bộ luật {rules_ms:.3f} ms/tên miền, mô hình ML (bản JSON trong backend) {ml_ms:.3f} ms/tên miền.
{gem_note}
## Biểu đồ

![ROC](roc.png)

| Bộ luật | ML n-gram | Kết hợp |
|---|---|---|
| ![](cm_rules.png) | ![](cm_ml.png) | ![](cm_combined.png) |

## Mô hình học được gì (15 n-gram có trọng số lớn nhất mỗi phía)

{feat_md}

## Nhận xét

- Bộ luật có **độ chính xác (Precision) cao, FPR thấp** nhưng **bỏ sót nhiều** (Recall thấp): nó chỉ
  bắt các mẫu rõ ràng (giả mạo thương hiệu, đuôi tên miền rẻ, từ khóa dụ dỗ). Đây là lựa chọn có chủ đích
  để không chặn nhầm trang thật.
- Mô hình ML học được nhiều mẫu hơn nên Recall cao hơn hẳn, đổi lại chặn nhầm nhiều hơn.
- Backend dùng ML như **điểm cộng** cho luật (xem `app/ml.py`), sau đó trang có form đăng nhập
  còn được Gemini đọc nội dung trang, nên kết quả thực tế tốt hơn khi chỉ xét tên miền.
- Hạn chế: chỉ đánh giá trên tên miền; dữ liệu hợp lệ của PhiUSIIL chủ yếu là trang chủ của website
  quốc tế, ít tên miền Việt Nam.

_Tạo tự động bởi `eval/evaluate.py` trong {time.time() - t0:.0f} giây._
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    pd.DataFrame(rows).to_csv(OUT / "metrics.csv", index=False, encoding="utf-8-sig")
    print(table)
    print(f"\nĐã ghi {OUT / 'REPORT.md'} và {MODEL_PATH} ({MODEL_PATH.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    sys.exit(main())
