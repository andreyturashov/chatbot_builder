from app.core.config import Settings


def test_settings_is_production() -> None:
    dev_settings = Settings(APP_ENV="development")
    assert dev_settings.is_production is False

    prod_settings = Settings(APP_ENV="production")
    assert prod_settings.is_production is True
