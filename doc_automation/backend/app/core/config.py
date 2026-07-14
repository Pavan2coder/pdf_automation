"""
core/config.py
──────────────
Centralised application settings loaded from environment variables / .env file.
All services import from here – never hard-code secrets.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ── Directory constants ────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent.parent.parent   # …/backend
UPLOAD_DIR  = BASE_DIR / "uploads"
OUTPUT_DIR  = BASE_DIR / "outputs"
TEMPLATE_DIR= BASE_DIR / "templates"

for _d in (UPLOAD_DIR, OUTPUT_DIR, TEMPLATE_DIR):
    _d.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """
    All environment variables with sensible defaults.
    Copy .env.example → .env and fill in real values.
    """

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME:    str  = "AI Document Automation Platform"
    APP_VERSION: str  = "1.0.0"
    DEBUG:       bool = False
    LOG_LEVEL:   str  = "INFO"

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── AI Provider ───────────────────────────────────────────────────────────
    AI_PROVIDER: Literal["gemini", "openai"] = "gemini"

    # Gemini
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API key")
    GEMINI_MODEL:   str = "gemini-1.5-pro-latest"

    # OpenAI
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    OPENAI_MODEL:   str = "gpt-4o"

    # ── File limits ───────────────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB:   int = 50
    MAX_FILES_PER_BATCH:  int = 30
    ALLOWED_EXTENSIONS: list[str] = [
        ".pdf", ".docx", ".pptx", ".doc", ".ppt"
    ]

    # ── Processing ────────────────────────────────────────────────────────────
    AI_MAX_RETRIES:    int   = 3
    AI_RETRY_DELAY:    float = 2.0
    AI_TIMEOUT:        float = 120.0
    SESSION_TTL_HOURS: int   = 24

    # ── Paths (resolved at runtime) ───────────────────────────────────────────
    UPLOAD_DIR:   Path = UPLOAD_DIR
    OUTPUT_DIR:   Path = OUTPUT_DIR
    TEMPLATE_DIR: Path = TEMPLATE_DIR

    @field_validator("GEMINI_API_KEY", "OPENAI_API_KEY", mode="before")
    @classmethod
    def _strip(cls, v: str) -> str:
        return (v or "").strip()

    @property
    def active_ai_key(self) -> str:
        return (
            self.GEMINI_API_KEY
            if self.AI_PROVIDER == "gemini"
            else self.OPENAI_API_KEY
        )

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


# Singleton instance imported everywhere
settings = Settings()
