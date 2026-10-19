# PhishGuard

[![CI](https://github.com/baongocdz/phishguard/actions/workflows/ci.yml/badge.svg)](https://github.com/baongocdz/phishguard/actions/workflows/ci.yml)

Hệ thống phát hiện lừa đảo trực tuyến: **trang web giả mạo (phishing)**, **mã QR độc hại (quishing)**,
**email lừa đảo** và **tin nhắn SMS/Zalo lừa đảo (smishing)**.

| Thành phần | Mô tả |
|---|---|
| **Chrome extension** ([`extension/`](extension/)) | Tự kiểm tra mọi trang đang mở, hiện banner cảnh báo; cảnh báo khi rê chuột vào link nguy hiểm; quét mã QR trên màn hình; phân tích email đang mở trong Gmail; chặn chuyển hướng sang trang quảng cáo; báo cáo kết quả sai |
| **Backend API** ([`backend/`](backend/)) | FastAPI + MongoDB Atlas + Gemini, deploy trên Render |
| **Trang web kiểm tra** (`/`) | Kiểm tra link, mã QR (ảnh hoặc **camera điện thoại**), email (dán hoặc `.eml`), tin nhắn — không cần cài extension; cài được như ứng dụng (PWA) |
| **Dashboard quản trị** (`/dashboard`) | Biểu đồ thống kê, cảnh báo gần đây, duyệt báo cáo người dùng, quản lý danh sách đen/trắng |
| **Đánh giá + ML** ([`backend/eval/`](backend/eval/)) | 2 mô hình tự huấn luyện: tên miền (219 nghìn tên miền, AUC 0.914) và email/tin nhắn (20 nghìn văn bản, F1 0.966) |
| **Trang giới thiệu** (`/about`) | Kiến trúc, luồng phát hiện, kết quả đánh giá — dùng để trình bày |

Bản chạy thật: https://phishguard-backend-g3w0.onrender.com (trang kiểm tra) ·
[/dashboard](https://phishguard-backend-g3w0.onrender.com/dashboard) · [/docs](https://phishguard-backend-g3w0.onrender.com/docs) (tài liệu API)

## Kiến trúc và luồng phát hiện

```
Extension / Trang web ──► POST /analyze, /analyze-email ──► Backend (Render)
                                                              │
   1. Danh sách đen  ─► lừa đảo ngay                          │
   2. Danh sách trắng ─► an toàn ngay                         ├── MongoDB Atlas
   3. Cache 24 giờ   ─► trả kết quả cũ                        │   (whitelist, blacklist, cache,
   4. Bộ luật (giả mạo thương hiệu, đuôi tên miền rẻ,         │    events, reports)
      từ khóa dụ dỗ, IP, punycode, HTTP + mật khẩu...)        │
   5. Mô hình học máy (n-gram ký tự, cộng tối đa 0.3 điểm)    │
   6. Gemini đọc nội dung trang/email khi còn nghi ngờ ───────┴── Google Gemini (flash-lite)
      → kết luận nghiêm trọng hơn thắng (chống prompt injection)
```

Mất mạng hoặc backend lỗi, extension tự dùng bộ luật cục bộ (bản TypeScript của bước 4).

## Kết quả đánh giá (tóm tắt)

Trên tập test 43.808 tên miền của PhiUSIIL (chi tiết, biểu đồ ROC và ma trận nhầm lẫn:
[`backend/eval/results/REPORT.md`](backend/eval/results/REPORT.md)):

| Phương pháp | Precision | Recall | F1 | Chặn nhầm (FPR) |
|---|---|---|---|---|
| Chỉ bộ luật | 0.975 | 0.028 | 0.054 | 0.0% |
| Chỉ ML (n-gram) | 0.882 | 0.758 | 0.816 | 6.3% |
| **Luật + ML (cách backend dùng)** | **0.986** | **0.641** | **0.776** | **0.6%** |

Trên mẫu 59 tên miền, ML đạt độ chính xác ngang Gemini (0.797) nhưng nhanh hơn ~80.000 lần
(0.033 ms so với 2.6 s) và không tốn phí — vì vậy Gemini chỉ được gọi khi thật sự cần.

## Bảo mật và quyền riêng tư
- Không ghi API key vào code; key nằm trong biến môi trường Render / file `.env` (đã gitignore).
- Chỉ gửi chữ trên trang khi trang có form; lịch sử chỉ lưu tên miền, không lưu URL đầy đủ hay nội dung email.
- Nội dung trang/email được bọc trong thẻ dữ liệu và Gemini được dặn không làm theo chỉ dẫn bên trong;
  kết quả AI không thể hạ mức cảnh báo của bộ luật.
- Giới hạn 30 lượt/phút mỗi IP; dashboard cần mã quản trị.
- Banner/tooltip dùng Shadow DOM và `textContent` (không `innerHTML`) để trang độc không chèn mã.

## Chạy ở máy
```bash
# Backend
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env               # rồi điền PHISHGUARD_MONGO_URI, PHISHGUARD_GEMINI_API_KEY, PHISHGUARD_ADMIN_TOKEN
python -m scripts.seed               # nạp whitelist/blacklist mẫu
uvicorn app.main:app --reload --port 8000
pytest -q                            # 59 test, không cần MongoDB

# Đánh giá + huấn luyện lại mô hình
pip install -r eval/requirements-eval.txt
python -m eval.evaluate <đường-dẫn>/PhiUSIIL_Phishing_URL_Dataset.csv --gemini 60

# Extension
cd extension
npm install
npm run build                        # rồi Load unpacked thư mục extension/dist
```

## Deploy
`render.yaml` ở thư mục gốc (Render Blueprint, `rootDir: backend`). Mỗi lần push lên `main`, Render tự deploy lại.
Chi tiết: [backend/README.md](backend/README.md).

Ghi chú nội bộ (tính năng, cấu hình, sự cố đã gặp, hướng phát triển): [docs/GHI_CHU_DU_AN.md](docs/GHI_CHU_DU_AN.md).
