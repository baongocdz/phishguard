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


class AnalyzeResponse(BaseModel):
    verdict: Literal["safe", "suspicious", "phishing"]
    score: float
    reasons: list[str]
    # Tuần 6 sẽ thêm "gemini"
    source: Literal["blacklist", "whitelist", "cache", "heuristic", "gemini"]
