"""The cloud release keeps its records in a storage bucket across restarts (D-041).

pg_dump and pg_restore are replaced by fakes; the bucket is a temporary folder.
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from chama import StepFailed
from chama import release_storage as storage


@pytest.fixture(autouse=True)
def database(monkeypatch):
    for key, value in {"POSTGRES_HOST": "127.0.0.1", "POSTGRES_PORT": "5432", "POSTGRES_USER": "kibaba",
                       "POSTGRES_DB": "kibaba", "POSTGRES_PASSWORD": "secret"}.items():
        monkeypatch.setenv(key, value)


def fake_dump(calls):
    def run(cmd, env, **kw):
        calls.append(cmd)
        out = cmd[cmd.index("-f") + 1]
        with open(out, "wb") as f:
            f.write(b"PGDMP")
        assert env["PGPASSWORD"] == "secret" and "secret" not in cmd     # the password never on the command line
        return SimpleNamespace(returncode=0, stderr="")
    return run


def test_a_save_is_a_new_file_and_only_the_last_three_are_kept(tmp_path):
    calls = []
    saved = [storage.save(tmp_path, run=fake_dump(calls)) for _ in range(5)]
    assert [p.name for p in storage.dumps(tmp_path)] == [p.name for p in reversed(saved[-3:])]
    assert not list((tmp_path / "db").glob(".*.part"))
    last = json.loads((tmp_path / "db" / "LAST_SAVED.json").read_text())
    assert last["file"] == saved[-1].name
    assert calls[0][:1] == ["pg_dump"] and "-Fc" in calls[0]


def test_a_failed_save_leaves_the_earlier_copies(tmp_path):
    good = storage.save(tmp_path, run=fake_dump([]))
    with pytest.raises(StepFailed, match="could not be saved"):
        storage.save(tmp_path, run=lambda cmd, env, **kw: SimpleNamespace(returncode=1, stderr="disk full"))
    assert storage.dumps(tmp_path) == [good]


def dumps_named(tmp_path, *names):
    (tmp_path / "db").mkdir()
    for name in names:
        (tmp_path / "db" / name).write_bytes(b"PGDMP")


def test_the_newest_copy_that_restores_is_used(tmp_path):
    dumps_named(tmp_path, "kibaba-20261110T080000Z.dump", "kibaba-20261111T080000Z.dump")
    tried, emptied = [], []

    def run(cmd, env, **kw):
        tried.append(os.path.basename(cmd[-1]))
        return SimpleNamespace(returncode=1 if "20261111" in cmd[-1] else 0, stderr="broken")

    found = storage.restore(tmp_path, run=run, fresh=lambda: emptied.append(1))
    assert found.name == "kibaba-20261110T080000Z.dump"
    assert tried == ["kibaba-20261111T080000Z.dump", "kibaba-20261110T080000Z.dump"] and emptied == [1]


def test_an_empty_bucket_means_a_first_start(tmp_path):
    assert storage.restore(tmp_path, run=lambda *a, **k: pytest.fail("nothing to restore")) is None


def test_it_refuses_to_start_afresh_over_copies_it_could_not_restore(tmp_path):
    dumps_named(tmp_path, "kibaba-20261111T080000Z.dump")
    with pytest.raises(StepFailed, match="did not start"):
        storage.restore(tmp_path, run=lambda cmd, env, **kw: SimpleNamespace(returncode=1, stderr="x"),
                        fresh=lambda: None)
    assert storage.dumps(tmp_path)                                    # untouched


def test_the_health_check_says_whether_pages_are_kept(tmp_path, monkeypatch):
    monkeypatch.delenv("BACKUP_DIR", raising=False)
    monkeypatch.delenv("SPACE_ID", raising=False)
    assert storage.status() == "kept in this computer's database"
    monkeypatch.setenv("SPACE_ID", "someone/kibaba")
    assert storage.status().startswith("not kept")
    assert storage.status(tmp_path) == "kept in the storage bucket; not saved yet"
    storage.save(tmp_path, run=fake_dump([]))
    assert "database last saved" in storage.status(tmp_path)


def can_link(tmp_path) -> bool:
    try:
        (tmp_path / "probe-link").symlink_to(tmp_path, target_is_directory=True)
        return True
    except OSError:
        return False


def test_pages_photos_and_names_are_written_into_the_bucket(tmp_path, monkeypatch):
    if not can_link(tmp_path):
        pytest.skip("this Windows account cannot make symbolic links (the Space runs Linux)")
    project, bucket = tmp_path / "app", tmp_path / "bucket"
    monkeypatch.setattr(storage, "PROJECT_ROOT", project)
    (project / "data" / "interim").mkdir(parents=True)
    (project / "data" / "interim" / "aliases_chama_demo.csv").write_text("from the bundle")
    (project / "data" / "photos" / "chama_demo").mkdir(parents=True)
    (project / "data" / "photos" / "chama_demo" / "already.jpg").write_bytes(b"jpg")
    config = {"chamas": [{"id": "chama_demo", "release": True, "raw_dir": "data/raw/chama_demo",
                          "photos_dir": "data/photos/chama_demo"},
                         {"id": "chama_b", "raw_dir": "data/raw/chama_b", "photos_dir": "data/photos/chama_b"}]}

    storage.attach(bucket, config)
    scans = project / "data" / "raw" / "chama_demo" / "scans"
    (scans / "scan-0001.xlsx").write_bytes(b"xlsx")
    assert (bucket / "chama_demo" / "scans" / "scan-0001.xlsx").exists()
    assert (bucket / "chama_demo" / "photos" / "already.jpg").exists()     # moved in, not lost
    assert (bucket / "chama_demo" / "aliases_chama_demo.csv").read_text() == "from the bundle"
    assert not (project / "data" / "raw" / "chama_b").exists()             # only release chamas

    (bucket / "chama_demo" / "aliases_chama_demo.csv").write_text("names learned")
    (project / "data" / "interim" / "aliases_chama_demo.csv").unlink()
    (project / "data" / "interim" / "aliases_chama_demo.csv").write_text("from a new bundle")
    storage.attach(bucket, config)                                          # the next start
    assert (project / "data" / "interim" / "aliases_chama_demo.csv").read_text() == "names learned"


def test_the_saver_saves_only_after_a_change(tmp_path, monkeypatch):
    counts = iter([5, 5, 5, 9, 9])
    monkeypatch.setattr(storage, "change_count", lambda conn: next(counts))
    saved = []
    monkeypatch.setattr(storage, "save", lambda base: saved.append(base) or base / "db" / "x.dump")

    class Engine:
        def connect(self):
            from contextlib import nullcontext
            return nullcontext()

    saver = storage.Saver(Engine(), tmp_path, log=lambda m: None)
    assert saver.changed()            # nothing saved yet
    saver.save_now()                  # count 5
    assert not saver.changed()        # still 5
    assert saver.changed()            # 9: something was written
    assert saved == [tmp_path]
