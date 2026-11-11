"""The job worker (S-2):  python -m chama.web.worker

Takes jobs from app.jobs with SELECT ... FOR UPDATE SKIP LOCKED (no Redis):

- read_photo: the vision model reads an uploaded page into a draft for review;
  a meeting in several photos is read one photo at a time and joined (D-039).
  The free plan allows about one photo a minute, so a rate limit between the
  photos is waited out here. A rate limit, timeout or outage is otherwise tried
  again up to 3 times, waiting longer each time, on the same job and upload;
  then the scan shows "failed" with the reason and a Retry button.
- run_pipeline: the steps after Accept (services/pipeline_run.py).

In the cloud release (BACKUP_DIR set) it also saves the database to the
storage bucket when it has changed and right after each records update
(release_storage.py, D-041).

It loads the chosen model once at start, and tells the health check it is
alive every 10 seconds. Logs hold upload and member codes, never names.
"""
from __future__ import annotations

import logging
import socket
import threading
import time
import traceback
from pathlib import Path

from chama import StepFailed
from chama.config import load_config, pseudonym_key
from chama.db import create_schemas
from chama.web.data import scans
from chama.web.db import engine as web_engine
from chama.web.services import pipeline_run
from chama.web.services import scans as scan_service
from chama.web.settings import chamas

log = logging.getLogger("chama.worker")

MAX_ATTEMPTS = 3
WAITS = [20, 60, 120]   # seconds before each new try after a rate limit or outage
PART_WAITS = [30, 45, 60]   # within one job: before reading the next photo of a meeting again
NOT_A_PAGE = ("This photo does not look like a page of the chama's ledger, or it is too blurred, dark or cut "
              "off to read. Take the photo again: the whole page in view, flat, in good light.")


def read_photo(engine, config: dict, job: dict) -> None:
    from chama.extraction.extractor import ExtractionFailed, make_extractor, provider_settings
    from chama.extraction.run import read_photo as model_read
    from chama.extraction.schema import page_to_frames

    settings = config["extraction"]
    with engine.begin() as conn:
        upload = scans.upload_row(conn, job["upload_id"])
        parts = scans.photo_parts(conn, upload)
        scans.set_upload(conn, upload["id"], status="reading", problem=None)
        scans.set_job_step(conn, job["id"], "reading")
        if not parts:
            scans.set_upload(conn, upload["id"], status="failed", problem="The photo is no longer on the server.")
            scans.finish_job(conn, job["id"], "failed", "image", "no photo")
            return
    provider, _ = provider_settings(settings)
    notes = chamas().get(upload["chama_id"], {}).get("reading_notes", "")
    extractor = make_extractor(settings)
    readings = []

    def which(n: int) -> str:
        return f"Photo {n} of {len(parts)}: " if len(parts) > 1 else ""

    try:
        for n, path in enumerate(parts, start=1):
            with engine.begin() as conn:
                scans.set_job_step(conn, job["id"], f"reading photo {n} of {len(parts)}")
            for wait in [*PART_WAITS, None]:
                try:
                    readings.append(model_read(Path(path), settings, extractor, notes))
                    break
                except ExtractionFailed as e:
                    # A later photo meets the per-minute limit the earlier ones used up: wait here,
                    # so the photos already read are not read again
                    if not (e.transient and n > 1 and wait):
                        raise
                    log.info("upload %s: photo %s of %s waits %s s for the rate limit", upload["id"], n,
                             len(parts), wait)
                    time.sleep(wait)
            page = readings[-1].page
            if not page.is_ledger_page:
                problem = which(n) + NOT_A_PAGE + (f" The model said: {page.problem}" if page.problem else "")
                with engine.begin() as conn:
                    scans.set_upload(conn, upload["id"], status="failed", problem=problem,
                                     model=readings[-1].model, seconds=sum(r.seconds for r in readings))
                    scans.finish_job(conn, job["id"], "failed", "not_a_page", problem)
                log.info("upload %s: photo %s is not a ledger page", upload["id"], n)
                return
    except ExtractionFailed as e:
        e = type(e)(which(len(readings) + 1) + str(e), e.transient) if len(parts) > 1 else e
        with engine.begin() as conn:
            if e.transient and job["attempts"] < MAX_ATTEMPTS:
                wait = WAITS[job["attempts"] - 1]
                scans.retry_job_later(conn, job["id"], wait, str(e))
                scans.set_upload(conn, upload["id"], status="queued",
                                 problem=f"{e} Trying again in {wait} seconds.")
                log.info("upload %s: transient failure, try %s again in %s s", upload["id"], job["attempts"], wait)
                return
            scans.set_upload(conn, upload["id"], status="failed", problem=str(e))
            scans.finish_job(conn, job["id"], "failed", "extraction", str(e))
        log.info("upload %s: reading failed (%s)", upload["id"], "transient" if e.transient else "refused")
        return
    except StepFailed as e:       # the file is not a usable image
        message = str(e).split(": ", 1)[-1]
        with engine.begin() as conn:
            scans.set_upload(conn, upload["id"], status="failed", problem=message)
            scans.finish_job(conn, job["id"], "failed", "image", message)
        return

    frames = scan_service.merge_parts([page_to_frames(r.page, "upload") for r in readings])
    noted = [f"{which(n)}{r.page.problem}" for n, r in enumerate(readings, start=1) if r.page.problem]
    seconds = sum(r.seconds for r in readings)
    with engine.begin() as conn:
        scan_service.write_draft(conn, upload["id"], frames, upload["chama_id"])
        scans.set_upload(conn, upload["id"], status="ready", provider=provider, model=readings[-1].model,
                         seconds=seconds, problem=(f"The model noted: {' '.join(noted)}" if noted else None))
        scans.finish_job(conn, job["id"], "done")
    log.info("upload %s: ready for review (%s photos, %s statement lines, %.1f s)", upload["id"], len(parts),
             len(frames["statements"]), seconds)


def run_pipeline(engine, config: dict, job: dict, model, saver=None) -> None:
    try:
        pipeline_run.run_pipeline(engine, config, pseudonym_key(), job["upload_id"], model,
                                  log=lambda m: log.info("upload %s: %s", job["upload_id"], m))
    except StepFailed as e:
        with engine.begin() as conn:
            scans.finish_job(conn, job["id"], "failed", "pipeline", str(e)[:500])
        log.warning("upload %s: pipeline stopped (%s)", job["upload_id"], type(e).__name__)
        return
    with engine.begin() as conn:
        scans.finish_job(conn, job["id"], "done")
    if saver is not None:
        saver.save_now()          # the new page's records are the ones most worth keeping


class Heartbeat(threading.Thread):
    def __init__(self, engine, name: str):
        super().__init__(daemon=True)
        self.engine, self.name_, self.run_id, self.loaded = engine, name, None, False
        self.stop = threading.Event()

    def beat(self) -> None:
        try:
            with self.engine.begin() as conn:
                scans.heartbeat(conn, self.name_, self.run_id, self.loaded)
        except Exception:  # noqa: BLE001 - the database may be restarting; try again next beat
            log.warning("heartbeat: database not answering")

    def run(self) -> None:
        while not self.stop.wait(10):
            self.beat()


def main() -> None:
    from chama.web.services.scoring import LoadedModel

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    config = load_config()
    engine = web_engine()
    create_schemas(engine)
    heartbeat = Heartbeat(engine, f"worker@{socket.gethostname()}")
    heartbeat.beat()
    heartbeat.start()

    log.info("loading the model with the alias champion from the registry")
    model = LoadedModel.load(config)
    heartbeat.run_id, heartbeat.loaded = model.run_id, True
    heartbeat.beat()
    log.info("model version %s loaded (run %s, checksum %s); waiting for jobs",
             model.version, model.run_id[:8], (model.checksum or "")[:12])

    from chama.release_storage import Saver, base_dir

    saver = None
    if base_dir() is not None:
        saver = Saver(engine, base_dir(), log=log.info)
        saver.start()
        log.info("saving the database to the storage bucket at %s when it changes", base_dir())

    with engine.begin() as conn:
        released = scans.release_stuck_jobs(conn, minutes=0)
    if released:
        log.info("queued %s jobs again that a stopped worker left running", released)

    try:
        while True:
            with engine.begin() as conn:
                job = scans.claim_job(conn)
            if job is None:
                time.sleep(1)
                continue
            log.info("job %s: %s for upload %s (try %s)", job["id"], job["kind"], job["upload_id"], job["attempts"])
            try:
                if job["kind"] == "read_photo":
                    read_photo(engine, config, job)
                else:
                    run_pipeline(engine, config, job, model, saver)
            except Exception as e:  # noqa: BLE001 - one bad job must not stop the worker
                # where it stopped, without the error's text, which could hold a value from the page
                where = "".join(traceback.format_tb(e.__traceback__)[-4:])
                log.error("job %s stopped unexpectedly (%s) at %s", job["id"], type(e).__name__, where)
                with engine.begin() as conn:
                    scans.finish_job(conn, job["id"], "failed", "unexpected",
                                     "The worker stopped on this job. Try again; if it happens again, tell the admin.")
                    if job["kind"] == "read_photo":
                        scans.set_upload(conn, job["upload_id"], status="failed",
                                         problem="Reading stopped unexpectedly. Try again.")
    except KeyboardInterrupt:
        log.info("worker stopped")
    finally:
        heartbeat.stop.set()


if __name__ == "__main__":
    main()
