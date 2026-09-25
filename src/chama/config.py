"""Loads settings from config/pipeline.yaml and secrets from .env."""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def load_config() -> dict:
    with open(PROJECT_ROOT / "config" / "pipeline.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def database_url() -> str:
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.environ["POSTGRES_DB"]
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def pseudonym_key() -> bytes:
    key = os.getenv("PSEUDONYM_KEY", "")
    if not key:
        raise RuntimeError("PSEUDONYM_KEY is missing from .env")
    return key.encode("utf-8")
