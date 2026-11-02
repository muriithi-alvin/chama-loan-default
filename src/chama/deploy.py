"""The cloud release: its private bundle and publishing it (Sprint III, D-032).

The release on Hugging Face runs the demo chama only (fictional names,
D-028). Its data and model are in neither the GitHub repository nor the
public Space: `python -m chama.pipeline deploy-bundle` writes them to
data/deploy/bundle/, `deploy-publish` uploads them to a private Hugging Face
dataset, and the Space's image fetches them when it is built:

- data/raw/<demo chama>/*.xlsx  the typed pages with fictional names (no
  scans, no photos)
- data/interim/aliases_<demo chama>.csv  its reviewed, fictional names
- model/  the champion model's files and champion.json (registry.py)
- MANIFEST.json  every file with its SHA-256

Before anything is written, every value is checked for every word of every
real member's name (each real chama's reviewed names), as the demo copy
itself is.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from chama import StepFailed
from chama.config import PROJECT_ROOT, shown_path

SPACE_NAME = "kibaba"
DATASET_NAME = "kibaba-data"
GITHUB_REPO = "muriithi-alvin/chama-loan-default"
# What publish reads from .env; the laptop's own database settings are not among them
PUBLISH_SETTINGS = ("HF_TOKEN", "HF_BUILD_TOKEN", "GITHUB_READ_TOKEN", "CLOUD_POSTGRES_HOST", "CLOUD_POSTGRES_USER",
                    "CLOUD_POSTGRES_PASSWORD", "CLOUD_PSEUDONYM_KEY", "GROQ_API_KEY", "SUPABASE_URL",
                    "SUPABASE_PUBLISHABLE_KEY")


def real_names(config: dict) -> list[str]:
    """Every reviewed spelling and name of every real (not demo) chama."""
    from chama.anonymisation import aliases

    names: set[str] = set()
    for chama in config["chamas"]:
        path = aliases.review_file(chama["id"])
        if not chama.get("demo") and path.exists():
            spellings = aliases.read_review_file(path, only_reviewed=True)
            names |= set(spellings) | set(spellings.values())
    return sorted(names)


def find_leaks(books: list[Path], names_file: Path, real: list[str], demo_id: str) -> dict[str, int]:
    """{"file column": count} of values holding a word of a real name; empty when clean."""
    from chama.anonymisation.anonymise import find_names
    from chama.ingestion.excel_loader import read_workbook

    leaks = {}
    for book in books:
        frames, _ = read_workbook(book, demo_id)
        for column, count in find_names(frames, real).items():
            leaks[f"{book.name} {column}"] = count
    for column, count in find_names({"names": pd.read_csv(names_file, dtype=str)}, real).items():
        leaks[f"{names_file.name} {column}"] = count
    return leaks


def build(config: dict, out_dir: Path | None = None) -> Path:
    from chama.anonymisation import aliases
    from chama.models.registry import export_bundle

    demo = [c for c in config["chamas"] if c.get("demo")]
    if len(demo) != 1:
        raise StepFailed("Exactly one chama with demo: true is needed in config/pipeline.yaml.")
    demo_id, raw_dir = demo[0]["id"], PROJECT_ROOT / demo[0]["raw_dir"]
    books = sorted(raw_dir.glob("*.xlsx"))           # the yearly workbooks, not scans/
    names_file = aliases.review_file(demo_id)
    if not books or not names_file.exists():
        raise StepFailed(f"Build the demo chama first: python -m chama.pipeline demo-chama "
                         f"({shown_path(raw_dir)} or {shown_path(names_file)} is missing).")

    real = real_names(config)
    if not real:
        raise StepFailed("No reviewed real names found to check the bundle against; nothing was written.")
    leaks = find_leaks(books, names_file, real, demo_id)
    if leaks:
        detail = ", ".join(f"{place} ({n})" for place, n in leaks.items())
        raise StepFailed(f"Real names found in the demo files: {detail}. Nothing was written.")

    out_dir = Path(out_dir or PROJECT_ROOT / "data" / "deploy" / "bundle")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "data" / "raw" / demo_id).mkdir(parents=True)
    (out_dir / "data" / "interim").mkdir(parents=True)
    for book in books:
        shutil.copy2(book, out_dir / "data" / "raw" / demo_id / book.name)
    shutil.copy2(names_file, out_dir / "data" / "interim" / names_file.name)
    champion = export_bundle(out_dir / "model", config=config)

    files = {p.relative_to(out_dir).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(out_dir.rglob("*")) if p.is_file()}
    manifest = {"built_at": datetime.now(UTC).isoformat(timespec="seconds"), "demo_chama": demo_id,
                "model": {"version": champion.version, "run_id": champion.run_id, "checksum": champion.checksum},
                "checked_against_real_names": len(real), "files": files}
    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return out_dir


def first_start(config: dict, engine) -> None:
    """On the release's first start, load the demo chama into the empty
    database and score it; on later starts the records are already there."""
    from sqlalchemy import text

    from chama.db import create_schemas, table_exists
    from chama.pipeline import run_all
    from chama.web.services.scoring import run_score

    create_schemas(engine)
    with engine.connect() as conn:
        loaded = table_exists(conn, "analytics.meetings") and conn.execute(
            text("SELECT count(*) FROM analytics.meetings")).scalar_one() > 0
    if loaded:
        print("records already loaded; starting")
        return
    print("first start: loading the demo chama")
    run_all(config, engine)
    run_score(config, engine)



def publish(ref: str = "main", rebuild: bool = False, api=None, bundle: Path | None = None) -> str:
    """Create or update the private dataset and the public Space; return the
    site's address. The Dockerfile goes up last, because that starts the build
    and the build needs the settings. Safe to run again."""
    values = {name: os.getenv(name, "").strip() for name in PUBLISH_SETTINGS}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise StepFailed(f"Add to .env first: {', '.join(missing)} (see docs/deployment.md).")
    bundle = Path(bundle or PROJECT_ROOT / "data" / "deploy" / "bundle")
    if not (bundle / "MANIFEST.json").exists():
        raise StepFailed("Build the bundle first: python -m chama.pipeline deploy-bundle")
    if api is None:
        from huggingface_hub import HfApi

        api = HfApi(token=values["HF_TOKEN"])

    owner = api.whoami()["name"]
    dataset, space = f"{owner}/{DATASET_NAME}", f"{owner}/{SPACE_NAME}"
    api.create_repo(dataset, repo_type="dataset", private=True, exist_ok=True)
    if not api.repo_info(dataset, repo_type="dataset").private:
        raise StepFailed(f"{dataset} is not private on Hugging Face, so nothing was uploaded. Make it private first.")
    api.upload_folder(folder_path=str(bundle), repo_id=dataset, repo_type="dataset",
                      commit_message="Demo chama and champion model")

    api.create_repo(space, repo_type="space", space_sdk="docker", private=False, exist_ok=True)
    address = api.space_info(space).host
    variables = {"GITHUB_REPO": GITHUB_REPO, "GIT_REF": ref, "BUNDLE_REPO": dataset, "WEB_ORIGINS": address,
                 "COOKIE_SECURE": "true", "POSTGRES_HOST": values["CLOUD_POSTGRES_HOST"], "POSTGRES_PORT": "5432",
                 "POSTGRES_DB": "postgres", "POSTGRES_SSLMODE": "require"}
    secrets = {"GITHUB_TOKEN": values["GITHUB_READ_TOKEN"], "HF_TOKEN": values["HF_BUILD_TOKEN"],
               "POSTGRES_USER": values["CLOUD_POSTGRES_USER"], "POSTGRES_PASSWORD": values["CLOUD_POSTGRES_PASSWORD"],
               "PSEUDONYM_KEY": values["CLOUD_PSEUDONYM_KEY"], "GROQ_API_KEY": values["GROQ_API_KEY"],
               "SUPABASE_URL": values["SUPABASE_URL"], "SUPABASE_PUBLISHABLE_KEY": values["SUPABASE_PUBLISHABLE_KEY"]}
    for key, value in variables.items():
        api.add_space_variable(space, key, value)
    for key, value in secrets.items():
        api.add_space_secret(space, key, value)
    for name in ("README.md", "Dockerfile"):
        api.upload_file(path_or_fileobj=str(PROJECT_ROOT / "deploy" / "huggingface" / name), path_in_repo=name,
                        repo_id=space, repo_type="space", commit_message=f"Kibaba release: {name}")
    if rebuild:
        api.restart_space(space, factory_reboot=True)
    return address
