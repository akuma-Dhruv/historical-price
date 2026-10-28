from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PARENT_ENV = Path("/home/martin/Documents/live-price/.env")


@dataclass(frozen=True)
class Settings:
    api_key: str
    client_code: str
    pin: str
    totp_secret: str
    database_url: str | None
    env_file: Path


def load_settings(env_file: str | None = None) -> Settings:
    configured_path = env_file or os.getenv("HISTORICAL_ENV_FILE")
    path = (
        Path(configured_path).expanduser().resolve()
        if configured_path
        else next(
            (candidate for candidate in (REPOSITORY_ROOT / ".env", DEFAULT_PARENT_ENV) if candidate.is_file()),
            REPOSITORY_ROOT / ".env",
        )
    )
    if not path.is_file():
        raise FileNotFoundError(f"Environment file does not exist: {path}")
    values = {key: value for key, value in dotenv_values(path).items() if value is not None}
    values.update(os.environ)
    required = {name: values.get(name) for name in (
        "ANGEL_API_KEY", "ANGEL_CLIENT_CODE", "ANGEL_PIN", "ANGEL_TOTP_SECRET"
    )}
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError("Missing required settings: " + ", ".join(missing))
    return Settings(
        api_key=required["ANGEL_API_KEY"],
        client_code=required["ANGEL_CLIENT_CODE"],
        pin=required["ANGEL_PIN"],
        totp_secret=required["ANGEL_TOTP_SECRET"],
        database_url=values.get("DATABASE_URL"),
        env_file=path,
    )
