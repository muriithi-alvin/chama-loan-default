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
    supabase_key: str              # the publishable (or legacy anon) key; never the secret key
    demo_mode: bool                # fictional names and the demo banner (ground rule G5)
    photo_dir: Path                # uploaded photos, outside every web folder
    cookie_secure: bool            # false only to test from a phone over plain http on the LAN
    session_hours: int
    allowed_origins: tuple[str, ...]
    log_dir: Path

    @property
    def supabase_ready(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)


@lru_cache
def web_settings() -> WebSettings:
    photo_dir = Path(os.getenv("PHOTO_DIR", "").strip() or PROJECT_ROOT / "data" / "interim" / "uploads")
    if not photo_dir.is_absolute():
        photo_dir = PROJECT_ROOT / photo_dir
    origins = os.getenv("WEB_ORIGINS", "").strip() or "http://localhost:3000,http://127.0.0.1:3000"
    return WebSettings(
        supabase_url=os.getenv("SUPABASE_URL", "").strip().rstrip("/"),
        supabase_key=(os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
                      or os.getenv("SUPABASE_ANON_KEY", "").strip()),
        demo_mode=_flag("DEMO_MODE", False),
        photo_dir=photo_dir,
        cookie_secure=_flag("COOKIE_SECURE", True),
        session_hours=int(os.getenv("SESSION_HOURS", "12")),
        allowed_origins=tuple(o.strip().rstrip("/") for o in origins.split(",") if o.strip()),
        log_dir=PROJECT_ROOT / "data" / "logs",
    )


@lru_cache
def chamas() -> dict[str, dict]:
    """The chamas in config/pipeline.yaml by id, each with its `name` and `demo` flag."""
    return {
        c["id"]: {**c, "name": c.get("name") or c["id"], "demo": bool(c.get("demo"))}
        for c in load_config()["chamas"]
    }


def chama_name(chama_id: str) -> str:
    return chamas().get(chama_id, {}).get("name", chama_id)


def is_demo_chama(chama_id: str) -> bool:
    """A chama made for the demo, whose names are fictional already."""
    return chamas().get(chama_id, {}).get("demo", False)
