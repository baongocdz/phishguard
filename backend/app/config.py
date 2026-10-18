from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PHISHGUARD_", env_file=".env", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    db_name: str = "phishguard"
    cache_ttl_seconds: int = 24 * 60 * 60  # kết quả cache sống 24 giờ

    # --- Gemini (tuần 6) ---
    # Để trống thì backend chạy như tuần 5 (chỉ dùng luật), không gọi Gemini.
    # KHÔNG ghi key vào code: đặt trong .env (local) hoặc biến môi trường (Render).
    gemini_api_key: str = ""
    # Thay bằng model ID chính xác lấy trong Google AI Studio.
    gemini_model: str = "gemini-flash-lite-latest"
    gemini_timeout_seconds: float = 10.0

    # Origin được phép gọi API (CORS), phân tách bằng dấu phẩy. "*" = tất cả.
    cors_origins: str = "*"

    # Số lần gọi /analyze tối đa mỗi phút cho một IP. 0 = không giới hạn.
    rate_limit_per_minute: int = 30

    # Google Safe Browsing (Lookup API v4). Để trống = bỏ qua lớp này.
    safe_browsing_api_key: str = ""

    # Mã đăng nhập trang quản trị /dashboard. Để trống = khóa trang quản trị.
    admin_token: str = ""


settings = Settings()
