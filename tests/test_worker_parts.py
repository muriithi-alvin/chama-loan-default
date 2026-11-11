"""The worker reads a meeting in several photos one at a time and joins them (D-039).

The model, the database and the clock are replaced by fakes: nothing is sent
anywhere, and a rate-limit wait takes no time.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest

from chama.extraction.extractor import Extraction, ExtractionFailed
from chama.extraction.schema import LedgerPage, MeetingRow, StatementRow
from chama.web import worker


def page(name: str, date_written: str = "", ledger: bool = True) -> LedgerPage:
    blank = {f: "" for f in MeetingRow.model_fields if f != "unclear"}
    line = {f: "" for f in StatementRow.model_fields if f != "unclear"}
    return LedgerPage(is_ledger_page=ledger, problem="" if ledger else "a shopping list",
                      meeting=MeetingRow(**{**blank, "meeting_date": date_written}, unclear=False),
                      statements=[StatementRow(**{**line, "member_name": name}, unclear=False)] if ledger else [],
                      new_loans=[])


class FakeEngine:
    @contextmanager
    def begin(self):
        yield None


@pytest.fixture
def run(monkeypatch):
    """Runs read_photo on an upload with the given photos; the model answers from `answers`."""
    state = {"upload": {}, "job": [], "draft": None, "slept": [], "reads": []}

    def fake_read(path, settings, extractor, notes=""):
        state["reads"].append(path.name)
        answer = state["answers"][path.name].pop(0)
        if isinstance(answer, Exception):
            raise answer
        return Extraction(page=answer, model="fake", seconds=2.0, input_tokens=0, output_tokens=0)

    monkeypatch.setattr("chama.extraction.run.read_photo", fake_read)
    monkeypatch.setattr("chama.extraction.extractor.make_extractor", lambda settings: object())
    monkeypatch.setattr(worker.time, "sleep", lambda s: state["slept"].append(s))
    monkeypatch.setattr(worker.scans, "upload_row", lambda conn, i: {"id": i, "chama_id": "chama_demo"})
    monkeypatch.setattr(worker.scans, "photo_parts", lambda conn, upload: state["photos"])
    monkeypatch.setattr(worker.scans, "set_upload", lambda conn, i, **v: state["upload"].update(v))
    monkeypatch.setattr(worker.scans, "set_job_step", lambda conn, i, step: None)
    monkeypatch.setattr(worker.scans, "finish_job", lambda conn, i, status, *a: state["job"].append(status))
    monkeypatch.setattr(worker.scans, "retry_job_later", lambda conn, i, s, m: state["job"].append(f"later {s}"))
    monkeypatch.setattr(worker.scan_service, "write_draft", lambda conn, i, frames, chama: state.update(draft=frames))

    def go(photos, answers, attempts=1):
        state.update(photos=photos, answers=answers)
        worker.read_photo(FakeEngine(), {"extraction": {"provider": "groq", "providers": {"groq": {}}}},
                          {"id": 1, "upload_id": 7, "attempts": attempts})
        return state

    return go


def test_three_photos_become_one_draft_in_order(run):
    state = run(["a.jpg", "b.jpg", "c.jpg"], {"a.jpg": [page("Anne Kiende", "4/8/2024")],
                                              "b.jpg": [page("Alvin Wise")], "c.jpg": [page("Grace Kanja")]})
    assert list(state["draft"]["statements"]["member_name"]) == ["Anne Kiende", "Alvin Wise", "Grace Kanja"]
    assert state["draft"]["meetings"].iloc[0]["meeting_date"] == "4/8/2024"
    assert state["upload"]["status"] == "ready" and state["upload"]["seconds"] == 6.0
    assert state["job"] == ["done"]


def test_a_rate_limit_on_a_later_photo_is_waited_out_without_reading_again(run):
    limit = ExtractionFailed("The reading service is busy.", transient=True)
    state = run(["a.jpg", "b.jpg"], {"a.jpg": [page("Anne Kiende", "4/8/2024")],
                                     "b.jpg": [limit, limit, page("Alvin Wise")]})
    assert state["reads"] == ["a.jpg", "b.jpg", "b.jpg", "b.jpg"]      # the first photo is read once
    assert state["slept"] == worker.PART_WAITS[:2] and state["upload"]["status"] == "ready"


def test_a_photo_that_is_not_a_page_is_named(run):
    state = run(["a.jpg", "b.jpg"], {"a.jpg": [page("Anne Kiende")], "b.jpg": [page("", ledger=False)]})
    assert state["upload"]["status"] == "failed"
    assert state["upload"]["problem"].startswith("Photo 2 of 2: This photo does not look like a page")
    assert state["draft"] is None and state["job"] == ["failed"]


def test_a_refused_photo_fails_the_scan_with_its_number(run):
    state = run(["a.jpg", "b.jpg"], {"a.jpg": [page("Anne Kiende")],
                                     "b.jpg": [ExtractionFailed("The page could not be read.")]})
    assert state["upload"]["status"] == "failed" and state["upload"]["problem"].startswith("Photo 2 of 2:")


def test_one_photo_reads_as_before(run):
    limit = ExtractionFailed("The reading service is busy.", transient=True)
    state = run(["a.jpg"], {"a.jpg": [limit]})
    assert state["slept"] == [] and state["job"] == ["later 20"]       # the job is tried again later, as before
    assert state["upload"]["problem"].startswith("The reading service is busy.")
