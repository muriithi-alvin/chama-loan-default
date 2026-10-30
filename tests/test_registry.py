"""The model registry (S-8): register a model, load it by alias, checksum it.
Uses a throwaway MLflow folder and a tiny model; nothing from the real runs."""
import numpy as np
import pytest

from chama import StepFailed
from chama.models import registry


@pytest.fixture
def tracking(tmp_path, monkeypatch):
    """A folder with one 'chosen' run holding a small model and band cut-offs."""
    from sklearn.linear_model import LogisticRegression

    from chama.models.train import setup_mlflow

    config = {"modelling": {"targets": {"missed_repayment": {
        "experiment": "test-missed", "chosen": {"model": "logistic_regression", "imbalance": "none"}}}}}
    mlflow = setup_mlflow(tmp_path, "test-missed")
    with mlflow.start_run() as run:
        mlflow.set_tags({"training_batch": "2026-10-30"})
        mlflow.log_params({"model": "logistic_regression", "imbalance": "none"})
        mlflow.log_metrics({"band_cutoff_medium": 0.2, "band_cutoff_high": 0.4})
        model = LogisticRegression().fit(np.array([[0.0], [1.0], [0.0], [1.0]]), [0, 1, 0, 1])
        mlflow.sklearn.log_model(model, name="model")
    return tmp_path, config, run.info.run_id


def test_the_chosen_model_is_registered_and_loaded_by_alias(tracking):
    folder, config, run_id = tracking
    name, version = registry.register("missed_repayment", config, folder)
    champion = registry.load_champion("missed_repayment", config, folder)
    assert (name, version) == ("chama-missed-repayment", "1")
    assert champion.run_id == run_id and champion.version == "1"
    assert champion.cutoffs == {"medium": 0.2, "high": 0.4}
    assert champion.model.predict([[1.0]])[0] == 1
    assert len(champion.checksum) == 64


def test_the_checksum_is_the_same_each_time_and_changes_with_the_model(tracking, tmp_path):
    folder, config, _ = tracking
    registry.register("missed_repayment", config, folder)
    first = registry.load_champion("missed_repayment", config, folder).checksum
    assert registry.load_champion("missed_repayment", config, folder).checksum == first
    (tmp_path / "copy").mkdir()
    (tmp_path / "copy" / "model.pkl").write_bytes(b"another model")
    assert registry.files_checksum(tmp_path / "copy") != first


def test_scoring_without_a_registered_model_says_what_to_run(tracking):
    folder, config, _ = tracking
    with pytest.raises(StepFailed, match="register-model"):
        registry.load_champion("missed_repayment", config, folder)
