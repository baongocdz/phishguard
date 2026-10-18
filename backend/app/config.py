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
    gemini_model: str = "gemini-flash-latest"
    gemini_timeout_seconds: float = 10.0

    # Origin được phép gọi API (CORS), phân tách bằng dấu phẩy. "*" = tất cả.
    cors_origins: str = "*"


settings = Settings()
