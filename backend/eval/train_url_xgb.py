"""Huấn luyện mô hình XGBoost chấm tên miền, so sánh với các mô hình khác, xuất app/url_model.json.

Chạy (từ thư mục backend):
    pip install -r eval/requirements-eval.txt
    python -m eval.train_url_xgb <đường-dẫn>/PhiUSIIL_Phishing_URL_Dataset.csv [--lightgbm]

Cách chia dữ liệu GIỐNG eval/evaluate.py (train/test 80/20, random_state=42) để so sánh công bằng với
mô hình Logistic Regression cũ. Tập train lại tách 10% làm validation để chọn ngưỡng cộng điểm; tập
test chỉ dùng để báo cáo kết quả cuối.

Kết quả: eval/results/URL_MODEL_REPORT.md + biểu đồ; mô hình: app/url_model.json.
"""
import argparse
import json
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.sparse as sp
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_curve
from sklearn.model_selection import train_test_split

from app import url_model
from app.domains import is_ip
from app.ml import combine
from app.service import ml_skipped
from app.url_features import FEATURE_NAMES, NGRAM_RANGE, handcrafted_features, prepare
from eval.evaluate import OUT, SEED, load, metrics, plot_confusion, rules_score

MODEL_PATH = url_model.MODEL_PATH
LEGIT_HOSTS = OUT.parent / "legit_hosts.txt"
XGB_PARAMS = dict(n_estimators=600, max_depth=8, learning_rate=0.1, subsample=0.9, colsample_bytree=0.5,
                  tree_method="hist", n_jobs=-1, random_state=SEED)


class Features:
    """n-gram ký tự (học từ tập fit) + 18 đặc trưng tự thiết kế, thành ma trận thưa như lúc chạy."""

    def __init__(self, hosts):
        self.vec = CountVectorizer(analyzer="char", ngram_range=NGRAM_RANGE, binary=True, min_df=10,
                                   max_features=40000).fit([prepare(h) for h in hosts])
        self.vocab = list(self.vec.get_feature_names_out())
        self.names = [f"'{g}'" for g in self.vocab] + FEATURE_NAMES

    def ngram(self, hosts):
        return self.vec.transform([prepare(h) for h in hosts])

    def hand(self, hosts):
        return np.array([handcrafted_features(h) for h in hosts])

    def both(self, hosts):
        # sp.csr_matrix bỏ các số 0 → xgboost coi là "thiếu"; app/url_model.py làm y hệt.
        return sp.hstack([self.ngram(hosts).astype(np.float32), sp.csr_matrix(self.hand(hosts))]).tocsr()


def pipeline_scores(hosts, probs, high=0.9, low=0.7):
    """Điểm cuối như backend: luật + điểm cộng ML (bỏ qua các tên miền trong service.ml_skipped)."""
    out = []
    for h, p in zip(hosts, probs):
        r = rules_score(h)
        out.append(r if ml_skipped(h) else combine(r, p, high, low))
    return np.array(out)


def rates(scores, y):
    flag = scores >= 0.3
    tp, fp = (flag & (y == 1)).sum(), (flag & (y == 0)).sum()
    return tp / (y == 1).sum(), tp / max(1, tp + fp), fp / (y == 0).sum()


def export(model: xgb.XGBClassifier, feats: Features, high: float, low: float, check_hosts: list[str]) -> float:
    """Ghi cây ra JSON cho app/url_model.py rồi kiểm tra chạy bằng Python ra đúng như xgboost."""
    booster = model.get_booster()
    trees = []
    for t in json.loads(booster.save_raw("json"))["learner"]["gradient_booster"]["model"]["trees"]:
        left, right, hess = t["left_children"], t["right_children"], t["sum_hessian"]
        value = [0.0] * len(left)

        def fill(n):  # lá: giá trị lá; nút trong: trung bình con theo trọng số (để giải thích kiểu Saabas)
            if left[n] == -1:
                value[n] = t["split_conditions"][n]
            else:
                fill(left[n]); fill(right[n])
                value[n] = (hess[left[n]] * value[left[n]] + hess[right[n]] * value[right[n]]) / hess[n]
        fill(0)
        trees.append({"left": left, "right": right, "feature": t["split_indices"],
                      "threshold": [0.0 if left[i] == -1 else c for i, c in enumerate(t["split_conditions"])],
                      "default_left": [int(d) for d in t["default_left"]], "value": value})

    margins = booster.predict(xgb.DMatrix(feats.both(check_hosts)), output_margin=True)
    data = {"kind": "xgboost", "ngram_range": list(NGRAM_RANGE), "vocab": feats.vocab, "base_margin": 0.0,
            "bonus_high": round(high, 2), "bonus_low": round(low, 2), "trees": trees}
    MODEL_PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    url_model.reload()
    # base_margin: phần hằng số của xgboost (base_score), suy ra từ tên miền đầu tiên.
    first = url_model._features(check_hosts[0])
    data["base_margin"] = float(margins[0]) - sum(url_model._walk(t, first, None) for t in url_model._model["trees"])
    probs = model.predict_proba(feats.both(check_hosts))[:, 1]
    data["checks"] = [[h, round(float(p), 6)] for h, p in zip(check_hosts[:20], probs[:20])]
    MODEL_PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    url_model.reload()
    diff = max(abs(url_model.predict(h) - p) for h, p in zip(check_hosts, probs))
    if diff > 1e-4:
        raise SystemExit(f"Python thuần lệch xgboost {diff:.2e} — không dùng được mô hình đã xuất.")
    return diff


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--lightgbm", action="store_true", help="so sánh thêm LightGBM (chậm, ~5 phút)")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    t0 = time.time()

    df = load(args.csv)
    train, test = train_test_split(df, test_size=0.2, stratify=df["y"], random_state=SEED)
    fit, val = train_test_split(train, test_size=0.1, stratify=train["y"], random_state=SEED)
    print(f"Fit {len(fit):,} / Validation {len(val):,} / Test {len(test):,}")
    feats = Features(fit.host)
    yf, yv, yt = fit.y.to_numpy(), val.y.to_numpy(), test.y.to_numpy()
    th = list(test.host)

    probs, rows = {}, []
    lr = LogisticRegression(C=1.0, max_iter=2000).fit(feats.ngram(fit.host), yf)
    probs["Logistic Regression (n-gram) – mô hình cũ"] = lr, lambda h: lr.predict_proba(feats.ngram(h))[:, 1]
    rf = RandomForestClassifier(300, n_jobs=-1, random_state=SEED).fit(feats.hand(fit.host), yf)
    probs["Random Forest (18 đặc trưng)"] = rf, lambda h: rf.predict_proba(feats.hand(h))[:, 1]
    xh = xgb.XGBClassifier(**XGB_PARAMS).fit(feats.hand(fit.host), yf)
    probs["XGBoost (18 đặc trưng)"] = xh, lambda h: xh.predict_proba(feats.hand(h))[:, 1]
    if args.lightgbm:
        import lightgbm as lgb
        lg = lgb.LGBMClassifier(n_estimators=600, num_leaves=63, learning_rate=0.1, colsample_bytree=0.5,
                                subsample=0.9, subsample_freq=1, random_state=SEED, verbose=-1)
        lg.fit(feats.both(fit.host), yf)
        probs["LightGBM (n-gram + 18 đặc trưng)"] = lg, lambda h: lg.predict_proba(feats.both(h))[:, 1]
    xb = xgb.XGBClassifier(**XGB_PARAMS).fit(feats.both(fit.host), yf)
    best_name = "XGBoost (n-gram + 18 đặc trưng) – mô hình mới"
    probs[best_name] = xb, lambda h: xb.predict_proba(feats.both(h))[:, 1]

    test_p = {}
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    for name, (_, f) in probs.items():
        p = f(th)
        test_p[name] = p
        rows.append(metrics(name, yt, (p >= 0.5).astype(int), p))
        fpr, tpr, _ = roc_curve(yt, p)
        ax.plot(fpr, tpr, label=f"{name.split(' – ')[0]} (AUC {rows[-1]['ROC-AUC']:.3f})")
    ax.plot([0, 1], [0, 1], "k--", lw=0.8)
    ax.set_xlabel("Tỉ lệ chặn nhầm (FPR)"); ax.set_ylabel("Tỉ lệ bắt được (Recall)")
    ax.set_title("ROC – các mô hình chấm tên miền", fontsize=10); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(OUT / "roc_url_models.png", dpi=150); plt.close(fig)

    # Chọn ngưỡng cộng 0.3 điểm trên VALIDATION: Recall cao nhất mà tỉ lệ chặn nhầm không vượt mô hình cũ.
    vh = list(val.host)
    lr_val = probs["Logistic Regression (n-gram) – mô hình cũ"][1](vh)
    xb_val = probs[best_name][1](vh)
    _, _, lr_fpr = rates(pipeline_scores(vh, lr_val), yv)
    grid = []
    for high in np.arange(0.5, 0.96, 0.05):
        low = min(0.7, high)
        r, p, f = rates(pipeline_scores(vh, xb_val, high, low), yv)
        grid.append((round(high, 2), r, f))
    high = max((g for g in grid if g[2] <= lr_fpr), key=lambda g: g[1])[0]
    low = min(0.7, high)

    lr_test = pipeline_scores(th, test_p["Logistic Regression (n-gram) – mô hình cũ"])
    xb_test = pipeline_scores(th, test_p[best_name], high, low)
    pipe_rows = []
    for name, s in (("Luật + LR (mô hình cũ, ngưỡng 0.9/0.7)", lr_test),
                    (f"Luật + XGBoost (ngưỡng {high:.2f}/{low:.2f})", xb_test)):
        rows_ = metrics(name, yt, (s >= 0.3).astype(int), s)
        pipe_rows.append(rows_)
    plot_confusion(yt, (xb_test >= 0.3).astype(int), "Luật + XGBoost (luồng thật)", OUT / "cm_url_xgb.png")

    # Trang thật hay dùng: bao nhiêu trang bị báo nhầm.
    legit = [line.strip() for line in LEGIT_HOSTS.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.startswith("#")]
    fp_lr = [h for h, s in zip(legit, pipeline_scores(legit, probs["Logistic Regression (n-gram) – mô hình cũ"][1](legit))) if s >= 0.3]
    fp_xb = [h for h, s in zip(legit, pipeline_scores(legit, probs[best_name][1](legit), high, low)) if s >= 0.3]

    # Mức ảnh hưởng của từng đặc trưng: TreeSHAP chính xác của xgboost trên 3.000 tên miền test.
    sample = list(test.sample(3000, random_state=SEED).host)
    contrib = xb.get_booster().predict(xgb.DMatrix(feats.both(sample)), pred_contribs=True)[:, :-1]
    imp = np.abs(contrib).mean(axis=0)
    top = np.argsort(-imp)[:20][::-1]
    fig, ax = plt.subplots(figsize=(6, 5.5))
    ax.barh([feats.names[i] for i in top], imp[top], color="#4c72b0")
    ax.set_xlabel("Trung bình |SHAP| (thang log-odds)")
    ax.set_title("20 đặc trưng ảnh hưởng nhất – XGBoost", fontsize=10)
    fig.tight_layout(); fig.savefig(OUT / "shap_url_xgb.png", dpi=150); plt.close(fig)

    diff = export(xb, feats, high, low, [h for h in th[:3100] if not is_ip(h)][:3000])  # mô hình bỏ qua IP
    t = time.perf_counter()
    for h in th[:1000]:
        url_model.predict(h)
    ms = (time.perf_counter() - t)
    examples = ["secure-vietcombank-xacminh.top", "paypal-login.firebaseapp.com", "shopee-sale.vn", "tdmu.edu.vn"]
    ex = [f"| `{h}` | {url_model.predict(h):.0%} | " + "; ".join(f"{n} (+{c})" for n, c in url_model.explain(h)) + " |"
          for h in examples]

    fmt = lambda frame: frame.to_markdown(index=False, floatfmt=".3f")
    grid_md = "\n".join(f"| {g[0]:.2f} | {g[1]:.3f} | {g[2]:.3%} |" for g in grid)
    report = f"""# Mô hình XGBoost chấm tên miền

- Dữ liệu: PhiUSIIL (UCI, 2024), {len(df):,} tên miền sau làm sạch; chia **giống** `eval/evaluate.py`
  (train/test 80/20, `random_state={SEED}`). Tập train tách tiếp 10% làm **validation** để chọn ngưỡng.
  Fit {len(fit):,} / Validation {len(val):,} / Test {len(test):,}.
- Đặc trưng: n-gram ký tự 3–5 của tên miền ({len(feats.vocab):,} cụm) + 18 đặc trưng tự thiết kế
  (`app/url_features.py`, dùng chung lúc huấn luyện và lúc chạy). Không dùng đường dẫn/giao thức (lộ nhãn).
- XGBoost: {XGB_PARAMS['n_estimators']} cây, sâu tối đa {XGB_PARAMS['max_depth']}, learning rate {XGB_PARAMS['learning_rate']}.

## 1. Từng mô hình đứng riêng (ngưỡng 0.5, tập test)

{fmt(pd.DataFrame(rows))}

![ROC](roc_url_models.png)

## 2. Trong luồng chấm thật của backend (luật + điểm cộng ML, tập test)

Điểm cuối ≥ 0.3 là "đáng ngờ" trở lên. ML không chấm tên miền chính chủ, `.gov/.edu`, trang phổ biến và đúng
tên máy của nơi người dùng tự đăng nội dung như docs.google.com (`service.ml_skipped`).
Ngưỡng cộng 0.3 điểm của XGBoost chọn trên **validation** = Recall cao nhất mà tỉ lệ chặn nhầm không vượt
mô hình cũ ({lr_fpr:.3%}):

| Ngưỡng | Recall (val) | FPR (val) |
|---|---|---|
{grid_md}

Chọn **{high:.2f}**. Kết quả trên tập test:

{fmt(pd.DataFrame(pipe_rows))}

![](cm_url_xgb.png)

Trang thật hay dùng (`eval/legit_hosts.txt`, {len(legit)} trang) bị báo nhầm:
- Mô hình cũ ({len(fp_lr)}): {", ".join(fp_lr) or "không có"}
- XGBoost ({len(fp_xb)}): {", ".join(fp_xb) or "không có"}

(Danh sách này chỉ chạy luật + ML, không qua whitelist của server; ngân hàng VN như acb.com.vn, vpbank.com.vn
và chính trang PhishGuard nằm trong whitelist (`scripts/seed.py`) nên khi chạy thật không bị báo.)

## 3. Giải thích (SHAP)

![](shap_url_xgb.png)

Lưu ý: "nhiều phần cách bởi dấu chấm" đứng đầu vì PhiUSIIL **lệch về subdomain** (chỉ ~3,9% tên miền hợp lệ có
subdomain, lừa đảo ~55%), nên mô hình nghi ngờ mọi subdomain. Backend giảm tác hại bằng cách không cho học máy chấm
trang phổ biến / chính chủ (`service.ml_skipped`, `scripts/build_popular.py`); dữ liệu hợp lệ có subdomain là hướng
cải thiện tiếp theo.

Lúc chạy, `app/url_model.py` tính đóng góp từng đặc trưng theo đường đi trên cây (xấp xỉ Saabas của SHAP,
không cần thư viện) và trả 3 lý do mạnh nhất:

| Tên miền | Xác suất | Lý do |
|---|---|---|
{chr(10).join(ex)}

## 4. Chạy trên server

- Mô hình xuất ra `app/url_model.json`, chấm bằng **Python thuần** (không cài xgboost trên Render, đỡ ~120 MB RAM).
  Lệch tối đa so với xgboost trên 3.000 tên miền: {diff:.1e}.
- Thời gian chấm: {ms:.2f} ms/tên miền (Python thuần, máy phát triển).

_Tạo tự động bởi `eval/train_url_xgb.py` trong {time.time() - t0:.0f} giây._
"""
    (OUT / "URL_MODEL_REPORT.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
