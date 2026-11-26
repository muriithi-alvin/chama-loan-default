
"""Settings for the web interface, read from .env (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from chama.config import PROJECT_ROOT, load_config


def _flag(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class WebSettings:
    supabase_url: str
    supabase_key: str  # publishable (or legacy anon) key; never the secret key
    demo_mode: bool
    photo_dir: Path
    cookie_secure: bool
    session_hours: int
    allowed_origins: tuple[str, ...]
    log_dir: Path

    # Legacy compatibility: Kibaba now uses Google-only authentication.
    two_step_for_officials: bool = False

    # Phone numbers remain available for account records and meeting reminders.
    phone_country: str = "254"
    meeting_texts: bool = False
    meeting_text_hour: int = 9

    @property
    def supabase_ready(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)


@lru_cache
def web_settings() -> WebSettings:
    photo_dir = Path(
        os.getenv("PHOTO_DIR", "").strip()
        or PROJECT_ROOT / "data" / "interim" / "uploads"
    )

    if not photo_dir.is_absolute():
        photo_dir = PROJECT_ROOT / photo_dir

    origins = (
        os.getenv("WEB_ORIGINS", "").strip()
        or "http://localhost:3000,http://127.0.0.1:3000"
    )

    return WebSettings(
        supabase_url=os.getenv("SUPABASE_URL", "").strip().rstrip("/"),
        supabase_key=(
            os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
            or os.getenv("SUPABASE_ANON_KEY", "").strip()
        ),
        demo_mode=_flag("DEMO_MODE", False),
        photo_dir=photo_dir,
        cookie_secure=_flag("COOKIE_SECURE", True),
        session_hours=int(os.getenv("SESSION_HOURS", "12")),
        allowed_origins=tuple(
            origin.strip().rstrip("/")
            for origin in origins.split(",")
            if origin.strip()
        ),
        # Tests write to a folder of their own, so web-stats shows real use only.
        log_dir=Path(
            os.getenv("WEB_LOG_DIR", "").strip()
            or PROJECT_ROOT / "data" / "logs"
        ),
        phone_country=(
            os.getenv("PHONE_COUNTRY_CODE", "").strip().lstrip("+")
            or "254"
        ),
        meeting_texts=_flag("MEETING_TEXTS", False),
        meeting_text_hour=min(
            23,
            max(
                0,
                int(os.getenv("MEETING_TEXT_HOUR", "").strip() or "9"),
            ),
        ),
    )


@lru_cache
def chamas() -> dict[str, dict]:
    """The chamas in config/pipeline.yaml by id, each with its name and demo flag."""
    return {
        c["id"]: {
            **c,
            "name": c.get("name") or c["id"],
            "demo": bool(c.get("demo")),
        }
        for c in load_config()["chamas"]
    }


def chama_name(chama_id: str) -> str:
    return chamas().get(chama_id, {}).get("name", chama_id)


def is_demo_chama(chama_id: str) -> bool:
    """A chama made for the demo, whose names are fictional already."""
    return chamas().get(chama_id, {}).get("demo", False)
