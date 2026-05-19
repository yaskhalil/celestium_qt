from src.config import Settings

def test_alpaca_duckdb_settings_exist():
    settings = Settings()
    assert hasattr(settings, "ALPACA_API_KEY")
    assert hasattr(settings, "ALPACA_SECRET_KEY")
    assert hasattr(settings, "ALPACA_BASE_URL")
    assert hasattr(settings, "DUCKDB_PATH")
    assert hasattr(settings, "SYMBOL")
    assert hasattr(settings, "CONTEXT_SYMBOL")
