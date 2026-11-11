"""Keeping the cloud release's records across restarts (D-041).

A Hugging Face Space's own disk is wiped whenever the Space restarts, sleeps
or is rebuilt. A private storage bucket is mounted into the Space as a folder
(BACKUP_DIR, /data/kibaba) and keeps what officials add:

- files, written straight into the bucket: each release chama's accepted
  pages (data/raw/<chama>/scans), their photos (data/photos/<chama>), the
  names learned from them (data/interim/aliases_<chama>.csv) and the photos
  waiting for review (PHOTO_DIR). The project's paths become links into the
  bucket (`attach`);
- the database, saved as a pg_dump file within two minutes of any change,
  right after each records update and when the Space stops (`save`). The
  newest of the last three is restored at the next start (`restore`); a
  file that does not restore is skipped for the one before it.

The database itself never runs on the bucket: a mounted bucket is object
storage and makes no promise about locking or fsync.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from chama import StepFailed
from chama.config import PROJECT_ROOT

KEEP = 3                      # database copies kept in the bucket
CHECK_EVERY = 60              # seconds between looks for changes
QUIET_TABLES = ("worker_status",)   # the worker's heartbeat changes every 10 s; not worth a save


def base_dir() -> Path | None:
    """The bucket's folder, if this run keeps its records (BACKUP_DIR is set)."""
    value = os.getenv("BACKUP_DIR", "").strip()
    return Path(value) if value else None


def _link(local: Path, kept: Path) -> None:
    """Make `local` a link to `kept`, moving anything already at `local` into it first."""
    if local.is_symlink():
        if local.resolve() == kept.resolve():
            return
        local.unlink()
    elif local.is_dir():
        for item in local.iterdir():
            if not (kept / item.name).exists():
                shutil.move(str(item), str(kept / item.name))
        shutil.rmtree(local)
    elif local.exists():
        local.unlink()                     # a file: the kept copy wins
    local.parent.mkdir(parents=True, exist_ok=True)
    local.symlink_to(kept, target_is_directory=kept.is_dir())


def attach(base: Path, config: dict) -> list[str]:
    """Point each release chama's scans, photos and names file into the bucket."""
    done = []
    for chama in (c for c in config["chamas"] if c.get("release")):
        home = base / chama["id"]
        for local, kept in ((PROJECT_ROOT / chama["raw_dir"] / "scans", home / "scans"),
                            (PROJECT_ROOT / chama["photos_dir"], home / "photos")):
            kept.mkdir(parents=True, exist_ok=True)
            _link(local, kept)
            done.append(f"{local.relative_to(PROJECT_ROOT).as_posix()} -> {kept.as_posix()}")
        names = PROJECT_ROOT / "data" / "interim" / f"aliases_{chama['id']}.csv"
        kept = home / names.name
        if not kept.exists() and names.exists():
            shutil.copy2(names.resolve(), kept)      # the first start: the bundle's names
        if kept.exists():
            _link(names, kept)
            done.append(f"{names.relative_to(PROJECT_ROOT).as_posix()} -> {kept.as_posix()}")
    return done


def _pg_env() -> tuple[list[str], dict]:
    args = ["-h", os.environ["POSTGRES_HOST"], "-p", os.getenv("POSTGRES_PORT", "5432"),
            "-U", os.environ["POSTGRES_USER"]]
    return args, {**os.environ, "PGPASSWORD": os.environ["POSTGRES_PASSWORD"]}


def dumps(base: Path) -> list[Path]:
    """The saved database copies, newest first."""
    return sorted((base / "db").glob("kibaba-*.dump"), reverse=True)


def save(base: Path, run=subprocess.run) -> Path:
    """The database as a new file in the bucket; the oldest beyond KEEP are removed."""
    folder = base / "db"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    final = folder / f"kibaba-{stamp}.dump"
    part = folder / f".kibaba-{stamp}.dump.part"
    args, env = _pg_env()
    done = run(["pg_dump", *args, "-d", os.environ["POSTGRES_DB"], "-Fc", "-f", str(part)], env=env,
               capture_output=True, text=True, check=False)
    if done.returncode or not part.exists():
        part.unlink(missing_ok=True)
        raise StepFailed(f"The database could not be saved: {(done.stderr or '').strip()[:300]}")
    os.replace(part, final)
    for old in dumps(base)[KEEP:]:
        old.unlink(missing_ok=True)
    (folder / "LAST_SAVED.json").write_text(json.dumps(
        {"at": datetime.now(UTC).isoformat(timespec="seconds"), "file": final.name}), encoding="utf-8")
    return final


def _fresh_database(env: dict, args: list[str]) -> None:
    db = os.environ["POSTGRES_DB"]
    for sql in (f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)', f'CREATE DATABASE "{db}"'):
        subprocess.run(["psql", *args, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", sql], env=env,
                       capture_output=True, check=True)


def restore(base: Path, run=subprocess.run, fresh=None) -> Path | None:
    """Restore the newest copy that restores whole into the (empty) database.
    None when the bucket has none yet: the release then loads its starting records.
    When copies exist but none restores, it stops: starting afresh would soon
    save over them, and the officials' pages would be lost."""
    args, env = _pg_env()
    fresh = fresh or (lambda: _fresh_database(env, args))
    found = dumps(base)
    for dump in found:
        done = run(["pg_restore", *args, "-d", os.environ["POSTGRES_DB"], "--no-owner", "--no-privileges",
                    "--single-transaction", "--exit-on-error", str(dump)], env=env, capture_output=True,
                   text=True, check=False)
        if done.returncode == 0:
            return dump
        print(f"{dump.name} did not restore ({(done.stderr or '').strip()[:200]}); trying the one before")
        try:
            fresh()        # one transaction, so nothing should be left; start empty to be sure
        except Exception as e:  # noqa: BLE001 - the next restore runs in a transaction anyway
            print(f"could not empty the database first: {type(e).__name__}")
    if found:
        raise StepFailed(f"None of the {len(found)} saved copies in {base / 'db'} restored, so the release did "
                         "not start: starting afresh would save over them. They are untouched; see the log above.")
    return None


def status(base: Path | None = None) -> str:
    """For the health check: whether pages added here are kept, and when they last were."""
    base = base if base is not None else base_dir()
    if base is None:
        if os.getenv("SPACE_ID"):          # set by Hugging Face in every Space
            return "not kept: no storage bucket, so pages added here are lost at the next restart"
        return "kept in this computer's database"
    try:
        saved = json.loads((base / "db" / "LAST_SAVED.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "kept in the storage bucket; not saved yet"
    return f"kept in the storage bucket; database last saved {saved['at']}"


def change_count(conn) -> int:
    """Rows written so far in every table but the heartbeat's; it grows with each change."""
    from sqlalchemy import text

    return int(conn.execute(text(
        "SELECT coalesce(sum(n_tup_ins + n_tup_upd + n_tup_del), 0) FROM pg_stat_user_tables "
        "WHERE NOT (relname = ANY(:quiet))"), {"quiet": list(QUIET_TABLES)}).scalar_one())


class Saver(threading.Thread):
    """In the worker: saves the database when it has changed, at most every CHECK_EVERY seconds,
    and at once after a records update (`save_now`)."""

    def __init__(self, engine, base: Path, every: int = CHECK_EVERY, log=print):
        super().__init__(daemon=True)
        self.engine, self.base, self.every, self.log = engine, base, every, log
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.saved_at_count: int | None = None

    def save_now(self) -> None:
        with self.lock:
            try:
                with self.engine.connect() as conn:
                    count = change_count(conn)
                path = save(self.base)
                self.saved_at_count = count
                self.log(f"database saved to the storage bucket ({path.name})")
            except Exception as e:  # noqa: BLE001 - a failed save is tried again at the next look
                self.log(f"saving the database failed: {type(e).__name__}: {str(e)[:200]}")

    def changed(self) -> bool:
        with self.engine.connect() as conn:
            return change_count(conn) != self.saved_at_count

    def run(self) -> None:
        while not self.stop.wait(self.every):
            try:
                if self.changed():
                    self.save_now()
            except Exception as e:  # noqa: BLE001 - the database may be restarting
                self.log(f"looking for changes failed: {type(e).__name__}")


def wait_for_mount(base: Path, seconds: int = 30) -> bool:
    """The bucket's folder may appear a moment after the container starts."""
    for _ in range(seconds):
        try:
            base.mkdir(parents=True, exist_ok=True)
            probe = base / ".write-check"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return True
        except OSError:
            time.sleep(1)
    return False
