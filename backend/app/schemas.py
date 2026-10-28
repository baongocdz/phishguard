from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class AnalyzeRequest(BaseModel):
    """Khớp với PageInfo mà Extension gửi lên (camelCase)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    url: str = Field(max_length=2048)
    hostname: str = Field(max_length=253)
    protocol: str
    title: str = Field(default="", max_length=512)
    form_count: int = 0
    has_password_field: bool = False
    link_count: int = 0
    external_link_count: int = 0
    # Đoạn văn bản hiển thị trên trang (Extension cắt sẵn), dùng cho Gemini
    text_snippet: str = Field(default="", max_length=4000)
    # Nguồn của URL: trang đang mở, link quét từ mã QR (quishing), hay link do
    # người dùng dán vào trang web. Chỉ dùng để thống kê.
    kind: Literal["page", "qr", "manual"] = "page"


class Signal(BaseModel):
    """Một tín hiệu góp điểm, để giải thích vì sao ra kết luận (Explainable AI)."""

    layer: Literal["list", "intel", "rule", "ml", "ai", "link", "age", "community"]
    label: str
    points: float


class AnalyzeResponse(BaseModel):
    verdict: Literal["safe", "suspicious", "phishing"]
    score: float
    reasons: list[str]
    source: Literal["blacklist", "whitelist", "cache", "safebrowsing", "heuristic", "gemini", "email"]
    # Từng lớp góp bao nhiêu điểm (danh sách, luật, học máy, AI...).
    breakdown: list[Signal] = Field(default_factory=list)


class EmailLink(BaseModel):
    text: str = Field(default="", max_length=500)  # chữ hiển thị của link
    href: str = Field(max_length=2048)              # địa chỉ thật của link


class EmailRequest(BaseModel):
    """Email lấy từ Gmail (extension) hoặc người dùng dán vào trang web."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    sender: str = Field(default="", max_length=320)     # "Tên <a@b.com>"
    reply_to: str = Field(default="", max_length=320)
    subject: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=20000)
    links: list[EmailLink] = Field(default_factory=list, max_length=300)


class PredictUrlRequest(BaseModel):
    url: str = Field(max_length=2048)  # URL đầy đủ hoặc chỉ tên miền


class PredictUrlResponse(BaseModel):
    """Kết quả của riêng mô hình học máy (không phải kết luận cuối như /analyze)."""

    label: Literal["safe", "suspicious", "phishing"]
    probability: float | None  # None: là địa chỉ IP / chưa có mô hình
    reasons: list[str]          # đặc trưng đẩy điểm về phía lừa đảo nhiều nhất
    model: str                  # "xgboost" hoặc "logistic-regression"
    used_in_analyze: bool       # False: /analyze bỏ qua học máy với tên miền này (chính chủ, phổ biến...)


class ReportRequest(BaseModel):
    """Người dùng báo kết quả sai: trang thật bị chặn nhầm, hoặc trang lừa đảo bị bỏ sót."""

    url: str = Field(max_length=2048)
    hostname: str = Field(max_length=253)
    kind: Literal["false_positive", "phishing"]
    note: str = Field(default="", max_length=1000)
