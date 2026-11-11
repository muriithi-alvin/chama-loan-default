"""The release (D-032 to D-034, D-036): only the chamas marked release: true, and a
bundle that never carries a real name, unless it is Humble Sister's, which then
never leaves the laptop. Made-up names only."""
import pandas as pd
import pytest

from chama import StepFailed
from chama.config import database_url, load_config
from chama.deploy import find_leaks
from chama.ingestion.raw_format import expected_columns, sheet_names


def workbook(path, member_names):
    """A raw workbook in the agreed layout with these names on its statement lines."""
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for table, sheet in sheet_names().items():
            df = pd.DataFrame(columns=expected_columns(table))
            if table == "statements":
                df = pd.DataFrame({c: [None] * len(member_names) for c in expected_columns(table)})
                df["member_name"] = member_names
            df.to_excel(writer, sheet_name=sheet, index=False)
    return path


def names_file(path, names):
    pd.DataFrame({"raw_name": [n.lower() for n in names], "canonical_name": names}).to_csv(path, index=False)
    return path


def test_the_bundle_check_finds_a_real_name_in_a_workbook(tmp_path):
    book = workbook(tmp_path / "2026.xlsx", ["Zawadi Mutua", "Imani Njoroge"])
    names = names_file(tmp_path / "aliases_chama_demo.csv", ["Zawadi Mutua"])
    leaks = find_leaks([book], names, ["Imani Njoroge"], "chama_demo")
    assert leaks == {"2026.xlsx statements.member_name": 1}


def test_the_bundle_check_passes_fictional_names_only(tmp_path):
    book = workbook(tmp_path / "2026.xlsx", ["Zawadi Mutua"])
    names = names_file(tmp_path / "aliases_chama_demo.csv", ["Zawadi Mutua"])
    assert find_leaks([book], names, ["Imani Njoroge"], "chama_demo") == {}


def test_the_bundle_check_reads_the_names_file_too(tmp_path):
    book = workbook(tmp_path / "2026.xlsx", ["Zawadi Mutua"])
    names = names_file(tmp_path / "aliases_chama_demo.csv", ["Imani Njoroge"])
    assert "aliases_chama_demo.csv names.canonical_name" in find_leaks([book], names, ["Imani Njoroge"], "chama_demo")


def test_the_release_keeps_only_the_demo_chama(monkeypatch):
    monkeypatch.setenv("CHAMA_ONLY", "chama_demo")
    assert [c["id"] for c in load_config()["chamas"]] == ["chama_demo"]
    monkeypatch.delenv("CHAMA_ONLY")
    assert len(load_config()["chamas"]) > 1


def test_a_changed_model_file_is_refused(tmp_path):
    import json

    from chama.models.registry import files_checksum, load_bundle

    (tmp_path / "files").mkdir()
    (tmp_path / "files" / "model.pkl").write_bytes(b"the model")
    (tmp_path / "champion.json").write_text(json.dumps({"checksum": files_checksum(tmp_path / "files")}))
    (tmp_path / "files" / "model.pkl").write_bytes(b"another model")
    with pytest.raises(StepFailed, match="do not match their checksum"):
        load_bundle(tmp_path)


SETTINGS = {"HF_TOKEN": "write-token", "HF_BUILD_TOKEN": "read-token", "GITHUB_READ_TOKEN": "github-token",
            "CLOUD_PSEUDONYM_KEY": "cloud-key", "GROQ_API_KEY": "groq-key", "SUPABASE_URL": "https://ref.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_x", "RELEASE_OFFICIAL_EMAIL": "official@example.com",
            "RELEASE_MEMBER_EMAIL": "member@example.com", "RELEASE_OFFICIAL_PHONE": "0700000001"}


class FakeHub:
    """Records what would be sent to Hugging Face; nothing leaves the test."""

    def __init__(self, private=True, bucket_private=True):
        self.calls, self.private, self.bucket_private = [], private, bucket_private

    def create_bucket(self, bucket_id, **kw):
        self.calls.append(("bucket", bucket_id, kw))

    def bucket_info(self, bucket_id):
        return type("Info", (), {"private": self.bucket_private})

    def set_space_volumes(self, repo_id, volumes):
        self.calls.append(("volumes", repo_id, volumes))

    def whoami(self):
        return {"name": "someone"}

    def create_repo(self, repo_id, **kw):
        self.calls.append(("create", repo_id, kw))

    def repo_info(self, repo_id, **kw):
        return type("Info", (), {"private": self.private})

    def space_info(self, repo_id):
        return type("Info", (), {"host": "https://someone-kibaba.hf.space"})

    def upload_folder(self, **kw):
        self.calls.append(("folder", kw["repo_id"], kw))

    def add_space_variable(self, repo_id, key, value):
        self.calls.append(("variable", key, value))

    def add_space_secret(self, repo_id, key, value):
        self.calls.append(("secret", key, value))

    def upload_file(self, **kw):
        self.calls.append(("file", kw["path_in_repo"], kw))

    def restart_space(self, repo_id, factory_reboot=False):
        self.calls.append(("restart", repo_id, factory_reboot))


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    for key, value in SETTINGS.items():
        monkeypatch.setenv(key, value)
    (tmp_path / "MANIFEST.json").write_text("{}")
    return tmp_path


def test_publishing_keeps_the_data_private_and_starts_the_build_last(bundle):
    from chama.deploy import publish

    hub = FakeHub()
    assert publish(api=hub, bundle=bundle) == "https://someone-kibaba.hf.space"
    kinds = [c[0] for c in hub.calls]
    assert hub.calls[0] == ("create", "someone/kibaba-data", {"repo_type": "dataset", "private": True, "exist_ok": True})
    assert kinds.index("folder") < kinds.index("variable") < kinds.index("secret") < kinds.index("file")
    assert kinds.index("volumes") < kinds.index("file")             # the bucket is attached before the build
    assert [c[1] for c in hub.calls if c[0] == "file"] == ["README.md", "Dockerfile"]
    assert "restart" not in kinds


def test_secrets_are_never_sent_as_visible_variables(bundle):
    from chama.deploy import publish

    hub = FakeHub()
    publish(api=hub, bundle=bundle)
    variables = {c[1]: c[2] for c in hub.calls if c[0] == "variable"}
    secrets = {c[1]: c[2] for c in hub.calls if c[0] == "secret"}
    assert variables["WEB_ORIGINS"] == "https://someone-kibaba.hf.space" and variables["GIT_REF"] == "main"
    assert secrets["HF_TOKEN"] == "read-token" and secrets["PSEUDONYM_KEY"] == "cloud-key"
    assert secrets["RELEASE_MEMBER_EMAIL"] == "member@example.com"
    for private in ("write-token", "read-token", "github-token", "cloud-key", "groq-key", "member@example.com"):
        assert private not in variables.values()
    assert "write-token" not in secrets.values()


def test_a_dataset_that_is_not_private_gets_no_upload(bundle):
    from chama.deploy import publish

    hub = FakeHub(private=False)
    with pytest.raises(StepFailed, match="not private"):
        publish(api=hub, bundle=bundle)
    assert "folder" not in [c[0] for c in hub.calls]


def test_real_names_go_to_hugging_face_only_when_the_hosting_is_agreed(bundle):
    import json

    from chama.deploy import publish

    (bundle / "MANIFEST.json").write_text(json.dumps({"real_names": True}))
    hub = FakeHub()
    with pytest.raises(StepFailed, match="hosting: agreed"):
        publish(api=hub, bundle=bundle)
    assert hub.calls == []
    (bundle / "MANIFEST.json").write_text(json.dumps({"real_names": True, "hosting_agreed": True}))
    assert publish(api=hub, bundle=bundle) == "https://someone-kibaba.hf.space"


def test_humble_sisters_settings_record_the_hosting_agreement():
    from chama.deploy import hosting_agreed

    chamas = {c["id"]: c for c in load_config()["chamas"]}
    assert hosting_agreed(chamas["chama_demo"]) and not hosting_agreed(chamas["chama_b"])


def test_the_space_keeps_its_records_in_a_private_bucket_at_data(bundle):
    from chama.deploy import publish

    hub = FakeHub()
    publish(api=hub, bundle=bundle)
    bucket = next(c for c in hub.calls if c[0] == "bucket")
    assert bucket[1] == "someone/kibaba-storage" and bucket[2]["private"] is True
    (volume,) = next(c for c in hub.calls if c[0] == "volumes")[2]
    assert (volume.type, volume.source, volume.mount_path) == ("bucket", "someone/kibaba-storage", "/data")
    assert not volume.read_only
    variables = {c[1]: c[2] for c in hub.calls if c[0] == "variable"}
    assert variables["BACKUP_DIR"] == "/data/kibaba" and variables["CHAMA_ONLY"] == "chama_demo"


def test_a_bucket_that_is_not_private_is_not_attached(bundle):
    from chama.deploy import publish

    hub = FakeHub(bucket_private=False)
    with pytest.raises(StepFailed, match="kibaba-storage is not private"):
        publish(api=hub, bundle=bundle)
    assert "volumes" not in [c[0] for c in hub.calls] and "file" not in [c[0] for c in hub.calls]


def test_the_treasurers_phone_goes_up_as_a_secret(bundle, monkeypatch):
    from chama.deploy import publish

    monkeypatch.setenv("TWO_STEP_FOR_OFFICIALS", "true")
    hub = FakeHub()
    publish(api=hub, bundle=bundle)
    secrets = {c[1]: c[2] for c in hub.calls if c[0] == "secret"}
    assert secrets["RELEASE_OFFICIAL_PHONE"] == "0700000001"
    assert "0700000001" not in [c[2] for c in hub.calls if c[0] == "variable"]
    monkeypatch.delenv("RELEASE_OFFICIAL_PHONE")
    with pytest.raises(StepFailed, match="RELEASE_OFFICIAL_PHONE"):
        publish(api=FakeHub(), bundle=bundle)


def test_the_release_serves_the_chamas_marked_for_it():
    from chama.deploy import names_are_real, release_chamas

    config = load_config()
    assert release_chamas(config) == ["chama_demo"]
    assert names_are_real(next(c for c in config["chamas"] if c["id"] == "chama_demo"))
    with pytest.raises(StepFailed, match="release: true"):
        release_chamas({"chamas": [{"id": "chama_b"}]})


def test_missing_settings_are_named_before_anything_is_sent(bundle, monkeypatch):
    from chama.deploy import publish

    monkeypatch.delenv("CLOUD_PSEUDONYM_KEY")
    hub = FakeHub()
    with pytest.raises(StepFailed, match="CLOUD_PSEUDONYM_KEY"):
        publish(api=hub, bundle=bundle)
    assert hub.calls == []


def test_a_password_with_special_characters_stays_in_one_piece(monkeypatch):
    from sqlalchemy.engine import make_url

    for key, value in {"POSTGRES_USER": "postgres.ref", "POSTGRES_PASSWORD": "p@ss/w:rd", "POSTGRES_DB": "postgres",
                       "POSTGRES_HOST": "pooler.example.test", "POSTGRES_PORT": "5432"}.items():
        monkeypatch.setenv(key, value)
    url = make_url(database_url())
    assert (url.username, url.password, url.host) == ("postgres.ref", "p@ss/w:rd", "pooler.example.test")


@pytest.fixture
def laptop(tmp_path, monkeypatch):
    for key, value in SETTINGS.items():
        monkeypatch.setenv(key, value)
    (tmp_path / "model").mkdir()
    (tmp_path / "model" / "champion.json").write_text("{}")
    return tmp_path


def test_the_laptop_release_cannot_reach_real_chamas(laptop, monkeypatch):
    from chama.deploy import LAPTOP_DB, laptop_settings

    monkeypatch.setenv("POSTGRES_DB", "chama")
    monkeypatch.setenv("PSEUDONYM_KEY", "laptop-key")
    settings = laptop_settings("https://Name.ngrok-free.app/", laptop)
    assert settings["POSTGRES_DB"] == LAPTOP_DB != "chama"
    assert settings["CHAMA_ONLY"] == "chama_demo"
    assert settings["PSEUDONYM_KEY"] == "cloud-key"
    assert settings["MODEL_BUNDLE"].endswith("model")
    assert settings["WEB_ORIGINS"].split(",")[0] == "https://name.ngrok-free.app"
    assert settings["COOKIE_SECURE"] == "true"


@pytest.mark.parametrize("address", ["http://name.ngrok-free.app", "name.ngrok-free.app", "https://a.test/path", ""])
def test_the_laptop_release_needs_the_tunnels_https_address(laptop, address):
    from chama.deploy import laptop_settings

    with pytest.raises(StepFailed, match="https address"):
        laptop_settings(address, laptop)


def test_the_laptop_release_names_missing_settings_and_bundle(laptop, monkeypatch, tmp_path):
    from chama.deploy import laptop_settings

    with pytest.raises(StepFailed, match="deploy-bundle"):
        laptop_settings("https://name.ngrok-free.app", tmp_path / "nothing")
    monkeypatch.delenv("RELEASE_MEMBER_EMAIL")
    with pytest.raises(StepFailed, match="RELEASE_MEMBER_EMAIL"):
        laptop_settings("https://name.ngrok-free.app", laptop)


def test_the_treasurers_phone_is_needed_while_officials_confirm_by_text(laptop, monkeypatch):
    from chama.deploy import laptop_settings

    monkeypatch.delenv("RELEASE_OFFICIAL_PHONE")
    monkeypatch.setenv("TWO_STEP_FOR_OFFICIALS", "true")
    with pytest.raises(StepFailed, match="RELEASE_OFFICIAL_PHONE"):
        laptop_settings("https://name.ngrok-free.app", laptop)
    monkeypatch.setenv("TWO_STEP_FOR_OFFICIALS", "false")
    assert laptop_settings("https://name.ngrok-free.app", laptop)["CHAMA_ONLY"] == "chama_demo"


def test_a_fresh_start_removes_the_demo_chamas_scans_and_photos(tmp_path, monkeypatch):
    from chama import deploy

    monkeypatch.setattr(deploy, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("PHOTO_DIR", raising=False)
    files = {name: tmp_path / name for name in (
        "data/raw/chama_demo/scans/scan-1.xlsx", "data/interim/uploads/chama_demo/page.jpg",
        "data/interim/uploads/chama_b/page.jpg", "data/interim/aliases_chama_demo.csv",
        "data/deploy/bundle/data/interim/aliases_chama_demo.csv")}
    for path in files.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("learned" if path.parent.name == "interim" and "bundle" not in str(path) else "start")

    deploy._reset_demo_files()

    assert not files["data/raw/chama_demo/scans/scan-1.xlsx"].exists()
    assert not files["data/interim/uploads/chama_demo/page.jpg"].exists()
    assert files["data/interim/uploads/chama_b/page.jpg"].exists()
    assert files["data/interim/aliases_chama_demo.csv"].read_text() == "start"
