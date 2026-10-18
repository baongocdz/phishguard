# PhishGuard Backend

FastAPI + MongoDB (Atlas) + Gemini. Phục vụ API cho extension, trang web kiểm tra (`/`)
và dashboard quản trị (`/dashboard`).

## Chạy ở máy
1. `python -m venv .venv` rồi `.venv\Scripts\activate` (macOS/Linux: `source .venv/bin/activate`)
2. `pip install -r requirements.txt`
3. Sao chép `.env.example` thành `.env` và điền:
   - `PHISHGUARD_MONGO_URI`: chuỗi `mongodb+srv://...` của Atlas
     (hoặc chạy Mongo trên máy bằng `docker compose up -d` và để mặc định `mongodb://localhost:27017`)
   - `PHISHGUARD_GEMINI_API_KEY`: để trống thì chỉ dùng luật + ML
   - `PHISHGUARD_ADMIN_TOKEN`: mật khẩu vào `/dashboard`
4. Nạp whitelist/blacklist mẫu: `python -m scripts.seed`
5. Chạy: `uvicorn app.main:app --reload --port 8000` → mở http://localhost:8000 (trang kiểm tra),
   http://localhost:8000/dashboard, http://localhost:8000/docs (tài liệu API)
6. Test (không cần MongoDB, không gọi Gemini thật): `pytest -q`

## Cấu trúc
| File | Vai trò |
|---|---|
| `app/main.py` | Khai báo route, CORS, index MongoDB |
| `app/service.py` | Luồng chấm URL và email, ghi cache/lịch sử/báo cáo |
| `app/heuristics.py` | Bộ luật cho URL (giữ đồng bộ với `extension/src/analyzer.ts`) |
| `app/ml.py`, `app/ml_model.json` | Mô hình học máy (n-gram ký tự), chạy bằng Python thuần |
| `app/email_rules.py` | Bộ luật cho email/tin nhắn |
| `app/gemini_client.py` | Gọi Gemini, prompt chống prompt injection |
| `app/admin.py` | API cho dashboard (cần header `X-Admin-Token`) |
| `app/rate_limit.py` | Giới hạn lượt gọi mỗi IP |
| `app/web/` | Trang kiểm tra và dashboard (HTML/JS thuần) |
| `eval/evaluate.py` | Đánh giá trên PhiUSIIL và huấn luyện lại mô hình ML |

## Luồng xử lý POST /analyze
blacklist → whitelist → cache 24h (3 bước hỏi song song) → bộ luật → điểm cộng ML
→ Gemini (nếu trang có form và điểm < 0.6) → ghi cache + lịch sử.

## Deploy (Render + MongoDB Atlas, miễn phí)
1. Atlas: cluster M0, tạo database user, Network Access thêm `0.0.0.0/0`, lấy chuỗi kết nối.
2. Nạp dữ liệu mẫu lên Atlas từ máy: đặt `PHISHGUARD_MONGO_URI` trong `.env` rồi `python -m scripts.seed`.
3. Render → New → **Blueprint** → chọn repo (đọc `render.yaml` ở thư mục gốc, `rootDir: backend`).
   Nhập `PHISHGUARD_MONGO_URI`, `PHISHGUARD_GEMINI_API_KEY`, `PHISHGUARD_ADMIN_TOKEN`.
4. Settings → **Auto-Deploy: On Commit** để mỗi lần push là tự deploy.
5. Kiểm tra `https://<service>.onrender.com/health` → `{"status":"ok"}`.

Gói free ngủ sau ~15 phút không có request (lần gọi đầu mất 30–50 giây). Muốn luôn thức:
dùng https://cron-job.org gọi `/health` mỗi 10 phút.
