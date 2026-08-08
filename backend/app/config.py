"""
Application configuration using pydantic-settings.
Owner: MOHAMMED

Reads environment variables (and .env file) to configure the application.
All settings are centralized here — no magic strings scattered across the codebase.
"""

from pathlib import Path
from functools import lru_cache
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ──────────────────────────────────────────────────
    app_name: str = "AI Interview Agent"
    app_version: str = "0.1.0"
    debug: bool = False

    # ── Server ───────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000

    # ── CORS ─────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── Data file paths ──────────────────────────────────────────────
    candidates_file: Path = Path(__file__).resolve().parent / "data" / "files" / "candidates.json"
    curriculum_file: Path = Path(__file__).resolve().parent / "data" / "files" / "curriculum.json"

    # ── Logging ──────────────────────────────────────────────────────
    log_level: str = "INFO"

    # ── AI Engine (placeholder — not implemented yet) ────────────────
    ai_provider: str = "none"
    ai_api_key: str = ""
    ai_model: str = ""


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — created once, reused everywhere."""
    return Settings()
