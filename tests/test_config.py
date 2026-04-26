from src.config import Settings

def test_webull_duckdb_settings_exist():
    settings = Settings()
    assert hasattr(settings, "WEBULL_APP_KEY")
    assert hasattr(settings, "WEBULL_APP_SECRET")
    assert hasattr(settings, "WEBULL_ACCOUNT_ID")
    assert hasattr(settings, "DUCKDB_PATH")
    assert hasattr(settings, "SYMBOL")
