"""Environment-driven configuration.

All sensitive assessment logic (rubric, scenarios, scores) lives on the server.
This module only handles infrastructure/config concerns.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def _get(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


# ---- LLM provider configuration (OpenAI-compatible) ----
OPENAI_API_KEY = _get("OPENAI_API_KEY")
OPENAI_BASE_URL = _get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = _get("OPENAI_MODEL", "gpt-4o-mini")

AZURE_OPENAI_API_KEY = _get("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = _get("AZURE_OPENAI_ENDPOINT").rstrip("/")
AZURE_OPENAI_DEPLOYMENT = _get("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_API_VERSION = _get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")


def detect_provider() -> str:
    forced = _get("LLM_PROVIDER").lower()
    if forced in {"openai", "azure", "demo"}:
        return forced
    if AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT:
        return "azure"
    if OPENAI_API_KEY:
        return "openai"
    return "demo"


PROVIDER = detect_provider()
LLM_ENABLED = PROVIDER in {"openai", "azure"}

# ---- App behaviour ----
# Max number of candidate messages before submission is required.
MAX_CANDIDATE_TURNS = int(_get("MAX_CANDIDATE_TURNS", "18") or "18")
# Minimum candidate messages before the "Finish" button is enabled.
MIN_CANDIDATE_TURNS = int(_get("MIN_CANDIDATE_TURNS", "4") or "4")

PORT = int(_get("PORT", "8000") or "8000")
HOST = _get("HOST", "0.0.0.0")

DB_PATH = Path(_get("DB_PATH", str(DATA_DIR / "assessment.db")))

# Durable storage: when set (e.g. on Render), all sessions/messages/scores are
# stored in this PostgreSQL database instead of the ephemeral local SQLite file,
# so recruiter results survive restarts, redeploys, and free-tier sleeps.
DATABASE_URL = _get("DATABASE_URL")

LLM_TIMEOUT = float(_get("LLM_TIMEOUT", "45") or "45")
LLM_MAX_TOKENS = int(_get("LLM_MAX_TOKENS", "500") or "500")


def _resolve_admin_token() -> str:
    token = _get("ADMIN_TOKEN")
    if token:
        return token
    # Persist a generated token so it stays stable across restarts.
    token_file = DATA_DIR / ".admin_token"
    if token_file.exists():
        return token_file.read_text(encoding="utf-8").strip()
    generated = secrets.token_urlsafe(16)
    token_file.write_text(generated, encoding="utf-8")
    return generated


ADMIN_TOKEN = _resolve_admin_token()


def provider_summary() -> str:
    if PROVIDER == "openai":
        return f"OpenAI-compatible ({OPENAI_BASE_URL}, model={OPENAI_MODEL})"
    if PROVIDER == "azure":
        return f"Azure OpenAI ({AZURE_OPENAI_ENDPOINT}, deployment={AZURE_OPENAI_DEPLOYMENT})"
    return "DEMO mode (no API key set — using built-in adaptive simulator)"
