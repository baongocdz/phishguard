# PhishGuard

Hệ thống phát hiện trang web lừa đảo (phishing), gồm 2 phần:

| Thư mục | Nội dung | Hướng dẫn |
|---|---|---|
| [`backend/`](backend/) | API FastAPI + MongoDB + Gemini, deploy lên Render | [backend/README.md](backend/README.md) |
| [`extension/`](extension/) | Chrome extension (TypeScript), gọi API backend | [extension/README.md](extension/README.md) |

## Chạy nhanh ở máy
```bash
# Backend
cd backend
docker compose up -d                 # MongoDB
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -m scripts.seed
uvicorn app.main:app --reload --port 8000

# Extension (terminal khác)
cd extension
npm install
npm run build                        # rồi Load unpacked thư mục extension/dist
```

## Deploy
`render.yaml` ở thư mục gốc, đã trỏ `rootDir: backend`. Chi tiết xem
[backend/README.md](backend/README.md#deploy-online-render--mongodb-atlas-miễn-phí).
