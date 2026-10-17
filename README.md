# PhishGuard Backend (Tuần 5)

## Chạy
1. Bật MongoDB: `docker compose up -d`
2. `python -m venv .venv && source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)
3. `pip install -r requirements.txt`
4. Nạp dữ liệu mẫu: `python -m scripts.seed`
5. Chạy API: `uvicorn app.main:app --reload --port 8000`
6. Xem tài liệu API tại http://localhost:8000/docs
7. Test (không cần MongoDB): `pytest -q`

## Deploy online (Render + MongoDB Atlas, miễn phí)
1. **MongoDB Atlas** (https://cloud.mongodb.com): tạo cluster **M0 Free** →
   Database Access: tạo user/mật khẩu → Network Access: thêm `0.0.0.0/0` →
   Connect → Drivers: copy chuỗi `mongodb+srv://...`.
2. Nạp dữ liệu mẫu lên Atlas (chạy ở máy, PowerShell):
   `$env:PHISHGUARD_MONGO_URI="mongodb+srv://..."; python -m scripts.seed`
3. Đẩy repo này lên GitHub (file `.env` đã nằm trong `.gitignore`).
4. **Render** (https://render.com): New → **Blueprint** → chọn repo. Render đọc
   `render.yaml` và hỏi 2 biến: `PHISHGUARD_MONGO_URI`, `PHISHGUARD_GEMINI_API_KEY`.
5. Deploy xong, mở `https://<tên-service>.onrender.com/health` phải thấy `{"status":"ok"}`.
6. Sửa `API_BASE` trong `phishguard_ext/src/config.ts` thành URL trên, `npm run build`,
   Reload extension.

Gói free của Render ngủ sau ~15 phút không có request. Muốn luôn thức, dùng
https://cron-job.org gọi `/health` mỗi 10 phút.

## Luồng xử lý POST /analyze
blacklist -> whitelist -> cache (TTL 24h) -> heuristic -> ghi cache
(Tuần 6 sẽ thêm bước gọi Gemini sau heuristic.)
