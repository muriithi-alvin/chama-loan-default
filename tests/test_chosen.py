"""Finding the chosen model's run; MLflow runs here are made up, with no data."""
import os

import pytest

from chama import StepFailed
from chama.models.chosen import chosen_run

CONFIG = {"modelling": {"targets": {"missed_repayment": {
    "experiment": "test-chosen",
    "chosen": {"model": "random_forest", "imbalance": "class_weight"},
}}}}


def log_run(mlflow, model, imbalance, batch):
    with mlflow.start_run(run_name=f"{model} + {imbalance}"):
        mlflow.log_params({"model": model, "imbalance": imbalance})
        if batch:
            mlflow.set_tag("training_batch", batch)


@pytest.fixture
def tracking(tmp_path):
    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    import mlflow

    mlflow.set_tracking_uri((tmp_path / "mlruns").resolve().as_uri())
    mlflow.set_experiment("test-chosen")
    return mlflow, tmp_path / "mlruns"


def test_the_chosen_model_from_the_latest_batch(tracking):
    mlflow, folder = tracking
    log_run(mlflow, "random_forest", "class_weight", "2026-10-20T10:00:00Z")
    log_run(mlflow, "random_forest", "class_weight", "2026-10-21T10:00:00Z")
    log_run(mlflow, "random_forest", "none", "2026-10-21T10:00:00Z")
    log_run(mlflow, "random_forest", "class_weight", None)   # from before batches were tagged

    run = chosen_run("missed_repayment", CONFIG, folder)
    assert run["params.imbalance"] == "class_weight"
    assert run["tags.training_batch"] == "2026-10-21T10:00:00Z"


def test_no_run_of_the_chosen_model_stops_with_a_message(tracking):
    mlflow, folder = tracking
    log_run(mlflow, "xgboost", "none", "2026-10-21T10:00:00Z")
    with pytest.raises(StepFailed, match="Run python -m chama.pipeline train"):
        chosen_run("missed_repayment", CONFIG, folder)
