
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
itself is. Humble Sister's copy keeps its real names (D-036): its bundle is
marked so and is not checked. `publish` sends a bundle with real names only
when the chama's settings say its officials agreed to the hosting
(`hosting: agreed`, D-041); otherwise it stays on this laptop.

The Space's own disk is wiped at every restart, so `publish` also makes a
private storage bucket and mounts it into the Space at /data, where the
release keeps the pages added to it and a copy of its database
(release_storage.py, D-041).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy.exc import OperationalError

from chama import StepFailed
from chama.config import PROJECT_ROOT, shown_path

LAPTOP_DB = "kibaba_release"
SPACE_NAME = "kibaba"
DATASET_NAME = "kibaba-data"
BUCKET_NAME = "kibaba-storage"       # the Space's lasting records (D-041)
MOUNT_PATH = "/data"
BACKUP_DIR = "/data/kibaba"
GITHUB_REPO = "muriithi-alvin/chama-loan-default"

# What publish reads from .env; the laptop's own database settings are not among them.
PUBLISH_SETTINGS = (
    "HF_TOKEN",
    "HF_BUILD_TOKEN",
    "GITHUB_READ_TOKEN",
    "CLOUD_PSEUDONYM_KEY",
    "GROQ_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_PUBLISHABLE_KEY",
    "RELEASE_OFFICIAL_EMAIL",
    "RELEASE_MEMBER_EMAIL",
)

# The release's two accounts (D-036): members of Humble Sister renamed in the
# interface copy, so the project's own Google accounts can sign in as them.
OFFICIAL_NAME = "Alvin Muriithi"     # the treasurer
MEMBER_NAME = "Alvin Wise"           # an ordinary member


def release_chamas(config: dict) -> list[str]:
    """The chamas the release serves: `release: true` in config/pipeline.yaml."""
    found = [c["id"] for c in config["chamas"] if c.get("release")]
    if not found:
        raise StepFailed("Mark the chama the release serves with release: true in config/pipeline.yaml.")
    return found


def names_are_real(chama: dict) -> bool:
    """A copy whose officials agreed to their real names on screen (D-036)."""
    return chama.get("names") == "real"


def hosting_agreed(chama: dict) -> bool:
    """The chama's officials agreed to Kibaba holding its records on Hugging Face (D-041)."""
    return chama.get("hosting") == "agreed"


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
    books = sorted(raw_dir.glob("*.xlsx"))
    names_file = aliases.review_file(demo_id)
    if not books or not names_file.exists():
        raise StepFailed(f"Build the demo chama first: python -m chama.pipeline demo-chama "
                         f"({shown_path(raw_dir)} or {shown_path(names_file)} is missing).")

    real = real_names(config)
    if names_are_real(demo[0]):
        # Humble Sister's officials agreed to their names on screen (D-036). The
        # bundle says so, and publish refuses it: it stays on this laptop.
        real = []
    elif not real:
        raise StepFailed("No reviewed real names found to check the bundle against; nothing was written.")
    else:
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

    files = {
        p.relative_to(out_dir).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out_dir.rglob("*"))
        if p.is_file()
    }
    manifest = {
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "demo_chama": demo_id,
        "model": {
            "version": champion.version,
            "run_id": champion.run_id,
            "checksum": champion.checksum,
        },
        "checked_against_real_names": len(real),
        "real_names": names_are_real(demo[0]),
        "hosting_agreed": hosting_agreed(demo[0]),
        "files": files,
    }
    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return out_dir


def add_accounts(config: dict, engine) -> None:
    """Create the release's treasurer and member accounts.

    Google sign-in is handled through Supabase Auth. Phone numbers are retained
    for account records and meeting reminders, not authentication.
    """
    from sqlalchemy import text

    from chama.web.services.accounts import add_user

    demo_id = next(c["id"] for c in config["chamas"] if c.get("demo"))
    with engine.connect() as conn:
        code = conn.execute(
            text(
                "SELECT member_code FROM private.member_codes "
                "WHERE chama_id = :c AND canonical_name = :n"
            ),
            {"c": demo_id, "n": MEMBER_NAME},
        ).scalar_one_or_none()

    if code is None:
        raise StepFailed(f"{MEMBER_NAME} is not a member of {demo_id}.")

    def phone(name: str) -> str | None:
        return os.getenv(name, "").strip() or None

    print(
        add_user(
            engine,
            os.environ["RELEASE_OFFICIAL_EMAIL"].strip(),
            "official",
            demo_id,
            None,
            OFFICIAL_NAME,
            "treasurer",
            phone=phone("RELEASE_OFFICIAL_PHONE"),
        )
    )
    print(
        add_user(
            engine,
            os.environ["RELEASE_MEMBER_EMAIL"].strip(),
            "member",
            demo_id,
            code,
            None,
            None,
            phone=phone("RELEASE_MEMBER_PHONE"),
        )
    )


def first_start(config: dict, engine) -> None:
    """Each time the release starts its database is new (D-033): load the demo
    chama, score it and add the accounts."""
    from sqlalchemy import text

    from chama.db import create_schemas, table_exists
    from chama.pipeline import run_all
    from chama.web.services.scoring import run_score

    create_schemas(engine)
    with engine.connect() as conn:
        loaded = table_exists(conn, "analytics.meetings") and conn.execute(
            text("SELECT count(*) FROM analytics.meetings")
        ).scalar_one() > 0

    if loaded:
        print("records already loaded; starting")
        return

    print("first start: loading the demo chama")
    run_all(config, engine)
    run_score(config, engine)
    add_accounts(config, engine)


def laptop_settings(
    address: str,
    bundle: Path | None = None,
    config: dict | None = None,
) -> dict[str, str]:
    """The release on this laptop behind a tunnel (D-034): its own database, only
    the chamas marked `release: true` and its own key, so chama B's own records
    (the ones the model learned from) are out of its reach."""
    address = address.strip().rstrip("/").lower()
    if not re.fullmatch(r"https://[a-z0-9.-]+", address):
        raise StepFailed(
            f"{address!r} is not the tunnel's https address, "
            "for example https://name.ngrok-free.app"
        )

    from chama.config import load_config

    needed = (
        "CLOUD_PSEUDONYM_KEY",
        "RELEASE_OFFICIAL_EMAIL",
        "RELEASE_MEMBER_EMAIL",
        "GROQ_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
    )
    missing = [name for name in needed if not os.getenv(name, "").strip()]
    if missing:
        raise StepFailed(f"Add to .env first: {', '.join(missing)} (see docs/deployment.md).")

    bundle = Path(bundle or PROJECT_ROOT / "data" / "deploy" / "bundle")
    if not (bundle / "model" / "champion.json").exists():
        raise StepFailed("Build the bundle first: python -m chama.pipeline deploy-bundle")

    only = ",".join(release_chamas(config or load_config()))
    return {
        "POSTGRES_DB": LAPTOP_DB,
        "CHAMA_ONLY": only,
        "PSEUDONYM_KEY": os.environ["CLOUD_PSEUDONYM_KEY"].strip(),
        "MODEL_BUNDLE": str(bundle / "model"),
        "WEB_ORIGINS": f"{address},http://localhost:3000",
        "COOKIE_SECURE": "true",
        "DRIVE_DIR": "",
        "WEB_LOG_DIR": str(PROJECT_ROOT / "data" / "logs" / "release"),
    }


def _ensure_laptop_database(fresh: bool) -> None:
    """Start the Docker database and make the release's own database inside it.
    Runs before the release's settings apply: Compose reads the laptop's own."""
    from sqlalchemy import create_engine, text

    from chama.config import database_url

    print("Starting the database")
    try:
        done = subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=PROJECT_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=180,
        )
    except subprocess.TimeoutExpired as e:
        raise StepFailed(
            "Docker did not answer within 3 minutes. Restart the laptop, then try again."
        ) from e

    if done.returncode:
        raise StepFailed("The database did not start. Is Docker Desktop running? Try: docker compose up -d")

    admin = create_engine(database_url(), isolation_level="AUTOCOMMIT")
    for _ in range(30):
        try:
            with admin.connect() as conn:
                if fresh:
                    conn.execute(text(f"DROP DATABASE IF EXISTS {LAPTOP_DB} WITH (FORCE)"))
                if not conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :d"),
                    {"d": LAPTOP_DB},
                ).first():
                    conn.execute(text(f"CREATE DATABASE {LAPTOP_DB}"))
            return
        except OperationalError:
            time.sleep(2)

    raise StepFailed("The database did not answer within a minute.")


def _reset_demo_files(demo_id: str = "chama_demo") -> None:
    """Back to the bundle's starting state: no scanned pages, their photos or names learned from them."""
    for scan in (PROJECT_ROOT / "data" / "raw" / demo_id / "scans").glob("scan-*.xlsx"):
        scan.unlink()

    photos = PROJECT_ROOT / (
        os.getenv("PHOTO_DIR", "").strip() or "data/interim/uploads"
    ) / demo_id
    for photo in photos.glob("*.jpg"):
        photo.unlink()

    names = f"aliases_{demo_id}.csv"
    shutil.copy2(
        PROJECT_ROOT / "data" / "deploy" / "bundle" / "data" / "interim" / names,
        PROJECT_ROOT / "data" / "interim" / names,
    )


def serve_on_laptop(address: str, fresh: bool = False) -> None:
    """Run the release on this laptop until Ctrl+C: the database, then the API, the
    worker and the pages. Only the pages listen, on 127.0.0.1, for the tunnel."""
    import httpx

    from chama.config import load_config
    from chama.db import get_engine

    settings = laptop_settings(address)
    for port in (3000, 8000):
        with socket.socket() as probe:
            probe.settimeout(1)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise StepFailed(f"Port {port} is in use. Stop the server using it first.")

    _ensure_laptop_database(fresh)
    if fresh:
        _reset_demo_files()

    os.environ.update(settings)

    report = PROJECT_ROOT / "data" / "processed" / "quality_report.csv"
    kept = report.read_bytes() if report.exists() else None
    try:
        first_start(load_config(), get_engine())
    finally:
        if kept is not None:
            report.write_bytes(kept)

    frontend = PROJECT_ROOT / "frontend"
    print("Building the pages")
    built = subprocess.run(
        [shutil.which("npm") or "npm", "run", "build"],
        cwd=frontend,
        capture_output=True,
        check=False,
    )
    if built.returncode:
        raise StepFailed("The pages did not build. Run npm run build in frontend/ to see why.")

    children = [
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "chama.web.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=PROJECT_ROOT,
        ),
        subprocess.Popen([sys.executable, "-m", "chama.web.worker"], cwd=PROJECT_ROOT),
        subprocess.Popen(
            [
                shutil.which("node") or "node",
                "node_modules/next/dist/bin/next",
                "start",
                "--hostname",
                "127.0.0.1",
                "--port",
                "3000",
            ],
            cwd=frontend,
        ),
    ]

    ready = False
    try:
        while all(child.poll() is None for child in children):
            time.sleep(3)
            if not ready:
                try:
                    ready = all(
                        httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=3).status_code == 200
                        for port in (8000, 3000)
                    )
                except httpx.HTTPError:
                    continue

                if ready:
                    print(
                        f"\nReady. Kibaba is at {address.strip().rstrip('/').lower()}\n"
                        "Keep this window and the tunnel's window open. Ctrl+C here stops it."
                    )

        raise StepFailed("A part of the release stopped; see the messages above.")
    except KeyboardInterrupt:
        print("Stopping")
    finally:
        for child in children:
            child.terminate()


def publish(
    ref: str = "main",
    rebuild: bool = False,
    api=None,
    bundle: Path | None = None,
    config: dict | None = None,
) -> str:
    """Create or update the private dataset, the private storage bucket and the
    public Space; return the site's address. The Dockerfile goes up last,
    because that starts the build and the build needs the settings. Safe to run
    again: the bucket and what it holds are kept."""
    from huggingface_hub import Volume

    from chama.config import load_config

    names = PUBLISH_SETTINGS
    values = {name: os.getenv(name, "").strip() for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise StepFailed(f"Add to .env first: {', '.join(missing)} (see docs/deployment.md).")

    bundle = Path(bundle or PROJECT_ROOT / "data" / "deploy" / "bundle")
    if not (bundle / "MANIFEST.json").exists():
        raise StepFailed("Build the bundle first: python -m chama.pipeline deploy-bundle")

    manifest = json.loads((bundle / "MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("real_names") and not manifest.get("hosting_agreed"):
        raise StepFailed(
            "The bundle holds real names, and the chama's settings do not say its officials agreed "
            "to Kibaba holding its records on Hugging Face (hosting: agreed, D-041). It stays on this "
            "laptop. If they have agreed, add it in config/pipeline.yaml and build the bundle again."
        )

    only = ",".join(release_chamas(config or load_config()))
    if api is None:
        from huggingface_hub import HfApi

        api = HfApi(token=values["HF_TOKEN"])

    owner = api.whoami()["name"]
    dataset, space = f"{owner}/{DATASET_NAME}", f"{owner}/{SPACE_NAME}"
    api.create_repo(dataset, repo_type="dataset", private=True, exist_ok=True)
    if not api.repo_info(dataset, repo_type="dataset").private:
        raise StepFailed(
            f"{dataset} is not private on Hugging Face, so nothing was uploaded. Make it private first."
        )

    api.upload_folder(
        folder_path=str(bundle),
        repo_id=dataset,
        repo_type="dataset",
        commit_message="Demo chama and champion model",
    )

    api.create_repo(space, repo_type="space", space_sdk="docker", private=False, exist_ok=True)
    address = api.space_info(space).host

    bucket = f"{owner}/{BUCKET_NAME}"
    api.create_bucket(bucket, private=True, exist_ok=True)
    if not api.bucket_info(bucket).private:
        raise StepFailed(
            f"{bucket} is not private on Hugging Face, so it was not attached. Make it private first."
        )

    api.set_space_volumes(
        space,
        [Volume(type="bucket", source=bucket, mount_path=MOUNT_PATH)],
    )

    variables = {
        "GITHUB_REPO": GITHUB_REPO,
        "GIT_REF": ref,
        "BUNDLE_REPO": dataset,
        "WEB_ORIGINS": address,
        "COOKIE_SECURE": "true",
        "CHAMA_ONLY": only,
        "BACKUP_DIR": BACKUP_DIR,
    }
    secrets = {
        "GITHUB_TOKEN": values["GITHUB_READ_TOKEN"],
        "HF_TOKEN": values["HF_BUILD_TOKEN"],
        "PSEUDONYM_KEY": values["CLOUD_PSEUDONYM_KEY"],
        "GROQ_API_KEY": values["GROQ_API_KEY"],
        "SUPABASE_URL": values["SUPABASE_URL"],
        "SUPABASE_PUBLISHABLE_KEY": values["SUPABASE_PUBLISHABLE_KEY"],
        "RELEASE_OFFICIAL_EMAIL": values["RELEASE_OFFICIAL_EMAIL"],
        "RELEASE_MEMBER_EMAIL": values["RELEASE_MEMBER_EMAIL"],
    }

    for optional in (
        "RELEASE_OFFICIAL_PHONE",
        "RELEASE_MEMBER_PHONE",
        "SMS_HOOK_SECRET",
        "AFRICASTALKING_USERNAME",
        "AFRICASTALKING_API_KEY",
        "AFRICASTALKING_SENDER_ID",
    ):
        if os.getenv(optional, "").strip():
            secrets[optional] = os.environ[optional].strip()

    for optional in ("MEETING_TEXTS", "MEETING_TEXT_HOUR"):
        if os.getenv(optional, "").strip():
            variables[optional] = os.environ[optional].strip()

    for key, value in variables.items():
        api.add_space_variable(space, key, value)

    for key, value in secrets.items():
        api.add_space_secret(space, key, value)

    for name in ("README.md", "Dockerfile"):
        api.upload_file(
            path_or_fileobj=str(PROJECT_ROOT / "deploy" / "huggingface" / name),
            path_in_repo=name,
            repo_id=space,
            repo_type="space",
            commit_message=f"Kibaba release: {name}",
        )

    if rebuild:
        api.restart_space(space, factory_reboot=True)

    return address
