"""Runtime configuration loaded from the process environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


class ConfigurationError(ValueError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    calibre_url: str
    username: str | None = None
    password: str | None = None
    timeout: float = 15.0

    @classmethod
    def from_environment(cls) -> "Settings":
        raw_url = os.getenv("CALIBRE_SERVER_URL", "http://127.0.0.1:8080").strip()
        parsed = urlparse(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigurationError(
                "CALIBRE_SERVER_URL must be an absolute http:// or https:// URL"
            )

        try:
            timeout = float(os.getenv("CALIBRE_REQUEST_TIMEOUT", "15"))
        except ValueError as error:
            raise ConfigurationError("CALIBRE_REQUEST_TIMEOUT must be a positive number") from error
        if timeout <= 0:
            raise ConfigurationError("CALIBRE_REQUEST_TIMEOUT must be a positive number")

        username = os.getenv("CALIBRE_USERNAME") or None
        password = os.getenv("CALIBRE_PASSWORD") or None
        if (username is None) != (password is None):
            raise ConfigurationError(
                "CALIBRE_USERNAME and CALIBRE_PASSWORD must be provided together"
            )

        return cls(calibre_url=raw_url.rstrip("/"), username=username, password=password, timeout=timeout)