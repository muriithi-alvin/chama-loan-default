"""Loads settings from config/pipeline.yaml and secrets from .env."""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from chama import StepFailed

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def shown_path(path: Path) -> Path:
    """A path relative to the project folder when inside it, for messages."""
    return path.relative_to(PROJECT_ROOT) if path.is_relative_to(PROJECT_ROOT) else path


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


def drive_dir() -> Path | None:
    """The project folder on Google Drive (DRIVE_DIR), or None when not set.

    On this computer it is the folder synced by Drive for desktop, for example
    G:/My Drive/chama-loan-default; in Colab the notebooks set it to
    /content/drive/MyDrive/chama-loan-default.
    """
    configured = os.getenv("DRIVE_DIR", "").strip()
    return Path(configured) if configured else None


def export_dir() -> Path:
    """Where the modelling table is written and read: <DRIVE_DIR>/data, else data/processed."""
    drive = drive_dir()
    return drive / "data" if drive else PROJECT_ROOT / "data" / "processed"


def mlflow_dir() -> Path:
    """Where MLflow keeps runs, models and plots: <DRIVE_DIR>/mlruns, else ./mlruns."""
    drive = drive_dir()
    return drive / "mlruns" if drive else PROJECT_ROOT / "mlruns"


def pseudonym_key() -> bytes:
    key = os.getenv("PSEUDONYM_KEY", "")
    if not key:
        raise StepFailed("PSEUDONYM_KEY is missing from .env")
    return key.encode("utf-8")
