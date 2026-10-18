from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pymongo import ASCENDING, AsyncMongoClient

from . import service
from .config import settings
from .rate_limit import limit_by_ip
from .schemas import AnalyzeRequest, AnalyzeResponse


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
    app.state.db = db
    yield
    await client.close()


app = FastAPI(title="PhishGuard API", version="0.1.0", lifespan=lifespan)

# Extension gửi JSON nên trình duyệt sẽ preflight (OPTIONS) trước khi POST.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


def get_db(request: Request):
    return request.app.state.db


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(limit_by_ip)])
async def analyze(req: AnalyzeRequest, db=Depends(get_db)):
    return await service.analyze(db, req)
