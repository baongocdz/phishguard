import pytest

from app import rate_limit
from app.config import settings


@pytest.fixture(autouse=True)
def no_real_gemini(monkeypatch):
    """Test không bao giờ gọi Gemini thật, kể cả khi .env có key.
    Test nào cần Gemini thì dùng fixture `gemini` (Gemini giả)."""
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "safe_browsing_key", "")


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    """Không tra RDAP thật trong test (test nào cần thì tự giả lập age_days)."""
    from app import domain_age

    async def no_age(host):
        return None
    monkeypatch.setattr(domain_age, "age_days", no_age)


@pytest.fixture(autouse=True)
def fresh_rate_limit():
    """Mỗi test bắt đầu với bộ đếm rate limit trống."""
    rate_limit.reset()
