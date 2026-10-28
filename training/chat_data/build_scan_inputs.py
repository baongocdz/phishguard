"""Tạo kết quả quét THẬT (đúng định dạng PhishGuard trả về) làm đầu vào cho nhóm "giải thích kết quả quét".

Chạy bộ chấm của backend (luật + học máy, không gọi mạng / Gemini) trên tên miền thật:
lừa đảo và hợp lệ lấy từ PhiUSIIL (nếu đưa file), cộng các trang hay dùng trong backend/eval/legit_hosts.txt.

    cd backend
    python ../training/chat_data/build_scan_inputs.py [--phiusiil <PhiUSIIL.csv>] [--n 400]
→ training/chat_data/data/scan_inputs.jsonl
"""
import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(HERE))

from app.heuristics import run_heuristics  # noqa: E402
from app.schemas import AnalyzeRequest  # noqa: E402
from app.service import apply_ml  # noqa: E402
from common import DATA, save_jsonl  # noqa: E402

PATHS = ["/", "/login", "/dang-nhap", "/verify/account", "/khuyen-mai", "/xac-minh?id=8812", "/signin", "/"]
TITLES = {True: ["Đăng nhập", "Xác minh tài khoản", "Sign in", "Cập nhật thông tin"], False: ["Trang chủ", "Home", ""]}


def scan(host: str, rnd: random.Random) -> dict:
    form = rnd.random() < 0.6
    url = f"https://{host}{rnd.choice(PATHS)}"
    req = AnalyzeRequest(url=url, hostname=host, protocol="https:", title=rnd.choice(TITLES[form]),
                         form_count=int(form), has_password_field=form)
    r = apply_ml(req, run_heuristics(req))
    return {"url": url, "has_login_form": form, "verdict": r.verdict, "score": r.score, "reasons": r.reasons,
            "breakdown": [b.model_dump() for b in r.breakdown]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phiusiil")
    ap.add_argument("--n", type=int, default=400)
    args = ap.parse_args()
    rnd = random.Random(7)

    legit = [h.strip() for h in (BACKEND / "eval" / "legit_hosts.txt").read_text(encoding="utf-8").splitlines()
             if h.strip() and not h.startswith("#")]
    phish = ["secure-vietcombank-xacminh.top", "vcb-digibank-update.com", "shopee-hoantien.xyz", "zalopay-nhanqua.click",
             "appleid-verify-account.com", "faceb00k-security-check.com", "momo-uudai.top", "tpbank-ebank.online",
             "dichvucong-capnhat.com", "vneid-xacthuc.app", "garena-quatang.xyz", "microsoft365-login.firebaseapp.com"]
    if args.phiusiil:
        from eval.evaluate import load  # noqa: E402 (cần pandas)
        df = load(args.phiusiil)
        phish += list(df[df.y == 1].host.sample(args.n, random_state=7))
        legit += list(df[df.y == 0].host.sample(args.n // 2, random_state=7))

    hosts = phish + legit
    rnd.shuffle(hosts)
    results = [scan(h, rnd) for h in hosts]
    # Tối đa n/3 mỗi mức kết luận để trợ lý học giải thích cả trang an toàn lẫn nguy hiểm.
    # (Chạy offline không có danh sách đen / Gemini nên mức "phishing" ít hơn hai mức còn lại.)
    by = {v: [r for r in results if r["verdict"] == v][:args.n // 3] for v in ("phishing", "suspicious", "safe")}
    out = [r for v in by.values() for r in v]
    rnd.shuffle(out)
    save_jsonl(DATA / "scan_inputs.jsonl", out)
    print(f"Đã ghi {len(out)} kết quả quét vào {DATA / 'scan_inputs.jsonl'}: "
          + ", ".join(f"{v} {len(rs)}" for v, rs in by.items()))
    print(json.dumps(out[0], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
