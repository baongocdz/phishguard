"""Sinh app/popular_domains.txt: tên miền phổ biến mà học máy KHÔNG được cộng điểm (luật vẫn chạy).

Mô hình học máy học từ PhiUSIIL, nơi chỉ 3,9% tên miền hợp lệ có subdomain (lừa đảo: 55%), nên chấm cao
cả trang thật như mail.yahoo.com, dash.cloudflare.com; trang rất hay bị giả mạo (coinbase.com,
steamcommunity.com) cũng bị "nhớ" là lừa đảo. Danh sách này lấy top N của Tranco rồi BỎ:
  - nền tảng bị lạm dụng: tên miền gốc có >= MIN_ABUSE trang lừa đảo trong tập TRAIN của PhiUSIIL
    (firebaseapp.com, web.app, weebly.com...). Chỉ dùng tập train để kết quả trên tập test vẫn khách quan;
  - nơi người dùng tự đăng nội dung (USER_CONTENT trong heuristics.py và threatfeeds.py).

Chạy (cần requirements-eval.txt):
    python -m scripts.build_popular <tranco top-1m.csv> <PhiUSIIL_Phishing_URL_Dataset.csv> <mã danh sách Tranco>
Tranco: https://tranco-list.eu/top-1m.csv.zip (mã danh sách: https://tranco-list.eu/top-1m-id)
PhiUSIIL: https://archive.ics.uci.edu/dataset/967
"""
import collections
import sys
from datetime import date
from pathlib import Path

from sklearn.model_selection import train_test_split

from app import heuristics, threatfeeds
from app.domains import registrable_domain
from eval.evaluate import SEED, load

TOP_N = 10_000
MIN_ABUSE = 3
OUT = Path(__file__).resolve().parents[1] / "app" / "popular_domains.txt"


def main(tranco_csv: str, phiusiil_csv: str, list_id: str) -> None:
    top = []
    with open(tranco_csv, encoding="utf-8") as f:
        for line in f:
            rank, domain = line.strip().split(",", 1)
            if int(rank) > TOP_N:
                break
            top.append(domain.lower())

    df = load(phiusiil_csv)
    train, _ = train_test_split(df, test_size=0.2, stratify=df["y"], random_state=SEED)
    abused = collections.Counter(registrable_domain(h) for h in train[train.y == 1].host)
    excluded = {d for d, n in abused.items() if n >= MIN_ABUSE}
    excluded |= {registrable_domain(d) for d in heuristics.USER_CONTENT}
    excluded |= {registrable_domain(d) for d in threatfeeds.USER_CONTENT}

    keep = [d for d in top if d not in excluded]
    header = (f"# Sinh bởi scripts/build_popular.py ngày {date.today():%d/%m/%Y}: Tranco top {TOP_N:,}"
              f" (danh sách {list_id}), bỏ {len(top) - len(keep)} tên miền bị lạm dụng / nội dung người dùng.\n"
              "# Đừng sửa tay. Học máy không cộng điểm cho các tên miền này (app/popular.py).\n")
    OUT.write_text(header + "\n".join(keep) + "\n", encoding="utf-8")
    print(f"OK: {OUT} ({len(keep)} tên miền, bỏ {len(top) - len(keep)})")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
