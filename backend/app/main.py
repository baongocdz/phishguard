import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pymongo import ASCENDING, DESCENDING, AsyncMongoClient

from . import admin, service, threatfeeds
from .config import settings
from .deps import get_db
from .rate_limit import client_ip, limit_by_ip
from .schemas import AnalyzeRequest, AnalyzeResponse, EmailRequest, ReportRequest

WEB_DIR = Path(__file__).parent / "web"
EVAL_DIR = Path(__file__).parent.parent / "eval" / "results"


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncMongoClient(settings.mongo_uri)
    db = client[settings.db_name]
    await db["whitelist"].create_index([("domain", ASCENDING)], unique=True)
    await db["blacklist"].create_index([("domain", ASCENDING)], unique=True)
    await db["cache"].create_index([("key", ASCENDING)], unique=True)
    # TTL index: MongoDB tự xóa bản ghi cache cũ (kiểm tra mỗi ~60 giây)
    await db["cache"].create_index(
        [("created_at", ASCENDING)], expireAfterSeconds=settings.cache_ttl_seconds
    )
    # Lịch sử kiểm tra cho dashboard, tự xóa sau 90 ngày.
    await db["events"].create_index([("at", DESCENDING)], expireAfterSeconds=90 * 24 * 3600)
    await db["reports"].create_index([("at", DESCENDING)])
    app.state.db = db
    # Cập nhật danh sách đen từ OpenPhish ở nền (không chặn khởi động).
    feed_task = asyncio.create_task(threatfeeds.sync_if_stale(db))
    yield
    feed_task.cancel()
    await client.close()


app = FastAPI(title="PhishGuard API", version="0.2.0", lifespan=lifespan)

# Extension gửi JSON nên trình duyệt sẽ preflight (OPTIONS) trước khi POST.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)
app.include_router(admin.router)


# Trang web và file tĩnh: bắt trình duyệt hỏi lại server mỗi lần (không đổi thì chỉ nhận 304).
# Không có header này, trình duyệt tự giữ style.css cũ hàng giờ → HTML mới + CSS cũ là vỡ giao diện.
@app.middleware("http")
async def no_stale_web_files(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if request.method == "GET" and (path in ("/", "/about", "/dashboard", "/manifest.webmanifest")
                                    or path.startswith("/static/")):
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
# Ảnh ROC / ma trận nhầm lẫn của phần đánh giá, cho trang /about.
if EVAL_DIR.is_dir():
    app.mount("/eval", StaticFiles(directory=EVAL_DIR), name="eval")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(limit_by_ip)])
async def analyze(req: AnalyzeRequest, db=Depends(get_db)):
    result = await service.analyze(db, req)
    await service.record_event(db, req.kind, req.hostname.lower(), result)
    return result


@app.post("/analyze-email", response_model=AnalyzeResponse, dependencies=[Depends(limit_by_ip)])
async def analyze_email(req: EmailRequest, db=Depends(get_db)):
    result = await service.analyze_email(db, req)
    await service.record_event(db, "email", service.sender_domain(req), result)
    return result


@app.post("/report", dependencies=[Depends(limit_by_ip)])
async def report(req: ReportRequest, request: Request, db=Depends(get_db)):
    await service.save_report(db, req, client_ip(request))
    return {"ok": True}


# Trang web: kiểm tra URL / QR / email cho mọi người, và dashboard quản trị.
@app.get("/", include_in_schema=False)
async def home():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/manifest.webmanifest", include_in_schema=False)
async def manifest():
    return FileResponse(WEB_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js", include_in_schema=False)
async def service_worker():
    return FileResponse(WEB_DIR / "sw.js", media_type="text/javascript",
                        headers={"Cache-Control": "no-cache"})


@app.get("/about", include_in_schema=False)
async def about():
    return FileResponse(WEB_DIR / "about.html")


@app.get("/public-stats")
async def public_stats(db=Depends(get_db)):
    """Số liệu công khai cho trang /about: chỉ con số tổng, không có tên miền."""
    return await service.public_stats(db, EVAL_DIR / "metrics.csv")


@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    return FileResponse(WEB_DIR / "dashboard.html")
