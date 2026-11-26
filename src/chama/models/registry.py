"""The model registry (S-8, decision D-030).

The chosen early-warning model (D-023) is registered in MLflow's model
registry as `chama-missed-repayment`, and the version in use carries the
alias `champion`. Scoring loads `models:/chama-missed-repayment@champion`,
so which model the pages use is decided by moving the alias, not by
searching runs, and each saved score records the version and a SHA-256
checksum of the model's files: anyone can check later which exact model
gave a colour.

The registry lives beside the runs (`mlruns/models/`, on Drive when
DRIVE_DIR is set), as plain files like the rest of MLflow here (D-019). The
cloud release cannot reach Drive: `export_bundle` copies the champion's files
and its details into a folder, and `load_bundle` loads such a folder only if
the files still match the checksum (D-032).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from chama import StepFailed
from chama.config import load_config, mlflow_dir

REGISTERED_NAMES = {"missed_repayment": "chama-missed-repayment"}
ALIAS = "champion"


@dataclass
class Champion:
    name: str            # registered model name
    version: str
    run_id: str
    model_name: str      # e.g. random_forest
    model: object
    cutoffs: dict
    checksum: str        # SHA-256 of the model's files


def files_checksum(folder: Path) -> str:
    """SHA-256 over every file in consistent, case-insensitive name order."""
    folder = Path(folder)
    digest = hashlib.sha256()

    paths = sorted(
        (p for p in folder.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(folder).as_posix().casefold(),
    )

    for path in paths:
        digest.update(path.relative_to(folder).as_posix().encode())
        digest.update(path.read_bytes())

    return digest.hexdigest()


def _mlflow(config: dict, target_name: str, tracking_dir: Path | None):
    from chama.models.train import setup_mlflow, target_settings

    settings = target_settings(config, target_name)
    return setup_mlflow(Path(tracking_dir or mlflow_dir()), settings["experiment"])


def register(target_name: str = "missed_repayment", config: dict | None = None,
             tracking_dir: Path | None = None) -> tuple[str, str]:
    """Register the chosen run's model as a new version and give it the alias.
    Returns (registered name, version)."""
    from chama.models.chosen import chosen_run

    config = config or load_config()
    run = chosen_run(target_name, config, tracking_dir)
    mlflow = _mlflow(config, target_name, tracking_dir)
    name = REGISTERED_NAMES[target_name]
    version = mlflow.register_model(f"runs:/{run['run_id']}/model", name)
    client = mlflow.MlflowClient()
    client.set_registered_model_alias(name, ALIAS, version.version)
    client.set_model_version_tag(name, version.version, "training_batch", str(run.get("tags.training_batch")))
    return name, str(version.version)


def load_champion(target_name: str = "missed_repayment", config: dict | None = None,
                  tracking_dir: Path | None = None) -> Champion:
    """The model with the alias, its run's band cut-offs and its checksum."""
    config = config or load_config()
    mlflow = _mlflow(config, target_name, tracking_dir)
    from mlflow.exceptions import MlflowException

    name = REGISTERED_NAMES[target_name]
    client = mlflow.MlflowClient()
    try:
        version = client.get_model_version_by_alias(name, ALIAS)
    except MlflowException as e:
        raise StepFailed(f"No {name}@{ALIAS} in the model registry. Run "
                         "python -m chama.pipeline register-model first.") from e
    uri = f"models:/{name}@{ALIAS}"
    model = mlflow.sklearn.load_model(uri)
    run = client.get_run(version.run_id)
    metrics = run.data.metrics
    folder = Path(mlflow.artifacts.download_artifacts(uri))
    return Champion(
        name=name, version=str(version.version), run_id=version.run_id,
        model_name=run.data.params.get("model", "model"), model=model,
        cutoffs={"medium": float(metrics["band_cutoff_medium"]), "high": float(metrics["band_cutoff_high"])},
        checksum=files_checksum(folder),
    )


def export_bundle(folder: Path, target_name: str = "missed_repayment", config: dict | None = None,
                  tracking_dir: Path | None = None) -> Champion:
    """Copy the champion's files to folder/files and its details to folder/champion.json."""
    config = config or load_config()
    champion = load_champion(target_name, config, tracking_dir)
    mlflow = _mlflow(config, target_name, tracking_dir)
    folder = Path(folder)
    if (folder / "files").exists():
        shutil.rmtree(folder / "files")
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(mlflow.artifacts.download_artifacts(f"models:/{champion.name}@{ALIAS}", dst_path=tmp))
        shutil.copytree(local, folder / "files")
    if files_checksum(folder / "files") != champion.checksum:
        raise StepFailed("The exported model files do not match the registered model's checksum.")
    details = {"name": champion.name, "alias": ALIAS, "version": champion.version, "run_id": champion.run_id,
               "model_name": champion.model_name, "cutoffs": champion.cutoffs, "checksum": champion.checksum}
    (folder / "champion.json").write_text(json.dumps(details, indent=1), encoding="utf-8")
    return champion


def load_bundle(folder: Path) -> Champion:
    """A model exported by export_bundle, refused if its files were changed."""
    import mlflow

    folder = Path(folder)
    details = json.loads((folder / "champion.json").read_text(encoding="utf-8"))
    checksum = files_checksum(folder / "files")
    if checksum != details["checksum"]:
        raise StepFailed(f"The model files in {folder} do not match their checksum; export the model again.")
    return Champion(name=details["name"], version=str(details["version"]), run_id=details["run_id"],
                    model_name=details["model_name"], model=mlflow.sklearn.load_model(str(folder / "files")),
                    cutoffs=details["cutoffs"], checksum=checksum)

