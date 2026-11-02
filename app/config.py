"""Configuration, loaded from environment variables / .env."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    provider: str
    gemini_api_key: str | None
    gemini_model: str
    max_diff_chars: int


def load_settings() -> Settings:
    return Settings(
        provider=os.getenv("REVIEWER_PROVIDER", "mock").strip().lower(),
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        max_diff_chars=int(os.getenv("MAX_DIFF_CHARS", "120000")),
    )


settings = load_settings()
