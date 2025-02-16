import pytest


# Fixture to set up fake environment variables
@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing"""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", 123456789)


def test_imports():
    from app.bot import main, dp

    assert main
    assert dp
