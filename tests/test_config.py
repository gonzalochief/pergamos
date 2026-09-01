import pytest

from pergamos.config import ConfigurationError, Settings


def test_settings_default_to_local_calibre(monkeypatch):
    monkeypatch.delenv("CALIBRE_SERVER_URL", raising=False)
    monkeypatch.delenv("CALIBRE_USERNAME", raising=False)
    monkeypatch.delenv("CALIBRE_PASSWORD", raising=False)
    settings = Settings.from_environment()
    assert settings.calibre_url == "http://127.0.0.1:8080"


def test_credentials_must_be_a_pair(monkeypatch):
    monkeypatch.setenv("CALIBRE_USERNAME", "reader")
    monkeypatch.delenv("CALIBRE_PASSWORD", raising=False)
    with pytest.raises(ConfigurationError):
        Settings.from_environment()