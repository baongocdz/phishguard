"""Kiểm tra nhanh toàn bộ chức năng trên server thật (chạy trước khi demo).

    python -m scripts.smoke                                   # mặc định: bản trên Render
    python -m scripts.smoke http://localhost:8000              # bản chạy ở máy
    python -m scripts.smoke <url> --admin <mã quản trị>        # kiểm tra thêm dashboard

Lần đầu có thể mất 30-50 giây nếu Render đang ngủ.
"""
import sys
import time

import httpx

DEFAULT = "https://phishguard-backend-g3w0.onrender.com"


def page(url: str) -> dict:
    host = httpx.URL(url).host
    return {"url": url, "hostname": host, "protocol": httpx.URL(url).scheme + ":", "kind": "manual"}


def main() -> int:
    args = sys.argv[1:]
    admin = None
    if "--admin" in args:
        i = args.index("--admin")
        admin = args[i + 1]
        args = args[:i] + args[i + 2:]
    base = (args[0] if args else DEFAULT).rstrip("/")
    c = httpx.Client(base_url=base, timeout=90)
    results: list[tuple[bool, str, str]] = []

    def check(name: str, fn):
        t = time.perf_counter()
        try:
            ok, info = fn()
        except Exception as e:  # mạng lỗi, JSON sai...
            ok, info = False, f"{type(e).__name__}: {e}"
        ms = (time.perf_counter() - t) * 1000
        results.append((ok, name, info))
        print(f"{'✅' if ok else '❌'} {name:42} {ms:6.0f} ms  {info}")

    def analyze(url, expect):
        r = c.post("/analyze", json=page(url)).json()
        return r["verdict"] in expect, f"{r['verdict']} {r['score']} ({r['source']})"

    print(f"Kiểm tra {base}\n")
    check("Server sống (/health)", lambda: (c.get("/health").json() == {"status": "ok"}, "ok"))
    for path in ("/", "/about", "/dashboard", "/docs", "/eval/roc.png"):
        check(f"Trang {path}", lambda p=path: (c.get(p).status_code == 200, str(c.get(p).status_code)))
    check("Trang thật (vnexpress.net) → an toàn", lambda: analyze("https://vnexpress.net/", {"safe"}))
    check("Giả mạo thương hiệu → lừa đảo",
          lambda: analyze("https://secure-vietcombank-xacminh.top/login", {"phishing"}))
    check("Tên miền na ná (vietcornbank) → cảnh báo",
          lambda: analyze("https://vietcornbank-online.com/", {"suspicious", "phishing"}))
    check("Google Safe Browsing (trang thử của Google)",
          lambda: analyze("http://testsafebrowsing.appspot.com/s/phishing.html", {"phishing"}))
    check("Link rút gọn t.co → mở ra đích thật", lambda: (
        lambda r: (any(s["layer"] == "link" for s in r.get("breakdown", [])), r["reasons"][0][:60])
    )(c.post("/analyze", json=page("https://t.co/abc")).json()))

    def email():
        r = c.post("/analyze-email", json={
            "sender": "Vietcombank <thongbao@vcb-canhbao.com>", "replyTo": "hotro.vcb@gmail.com",
            "subject": "[KHẨN] Tài khoản sẽ bị tạm khóa", "body": "Nhập mật khẩu và mã OTP để xác minh.",
            "links": [{"text": "https://www.vietcombank.com.vn", "href": "https://vcb-xacminh.top/login"}]}).json()
        return r["verdict"] == "phishing", f"{r['verdict']} {r['score']}, {len(r['reasons'])} lý do"
    check("Email giả ngân hàng → lừa đảo", email)

    def sms():
        r = c.post("/analyze-email", json={"body": "Congratulations! You have won a 1000 dollar gift card. "
                                                   "Claim your prize now by replying with your bank account "
                                                   "number. Offer expires today, act immediately."}).json()
        return r["verdict"] != "safe", f"{r['verdict']} {r['score']}"
    check("Tin nhắn trúng thưởng → cảnh báo", sms)
    check("Số liệu công khai (/public-stats)", lambda: (
        lambda s: ("total" in s and len(s["metrics"]) > 0, f"{s['total']} lượt, {len(s['metrics'])} dòng đánh giá")
    )(c.get("/public-stats").json()))
    check("Dashboard chặn khi sai mã", lambda: (
        c.get("/admin/stats", headers={"X-Admin-Token": "sai-ma"}).status_code == 401, "401"))
    if admin:
        def admin_ok():
            code = c.get("/admin/stats", headers={"X-Admin-Token": admin}).status_code
            return code == 200, str(code) + (" — mã quản trị không khớp với server này" if code == 401 else "")
        check("Dashboard với mã quản trị", admin_ok)

    failed = [n for ok, n, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} đạt." + (f" Lỗi: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
