"""Step 4 - Clean, link loans and check quality with dbt.

The dbt project lives in transform/. It reads the `staging` schema and builds
the `analytics` tables (see transform/models). Running dbt from here means the
database settings come from .env and the loan rules from config/pipeline.yaml.
"""
from __future__ import annotations

import json

from chama import StepFailed
from chama.config import PROJECT_ROOT

DBT_DIR = PROJECT_ROOT / "transform"
# Settings in config/pipeline.yaml that the dbt models use.
DBT_VARS = [
    "loan_term_days", "emergency_term_days", "default_statuses", "history_months",
    "warning_horizon_meetings",
]


def run_dbt(args: list[str], config: dict | None = None) -> None:
    """Run a dbt command on the project in transform/; stop if it fails."""
    from dbt.cli.main import dbtRunner

    full = [*args, "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]
    if config:
        rules = {k: config[k] for k in DBT_VARS if k in config}
        if rules:
            full += ["--vars", json.dumps(rules)]
    result = dbtRunner().invoke(full)
    if not result.success:
        raise StepFailed(f"dbt {' '.join(args)} failed - see the messages above.")
