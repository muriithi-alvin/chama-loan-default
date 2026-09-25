"""Run the data pipeline step by step.

Usage:
    python -m chama.pipeline ingest      # Step 1: raw Excel -> raw schema
    python -m chama.pipeline anonymise   # Step 2: names -> codes   (next)
    python -m chama.pipeline clean       # Step 3: types and fixes  (next)
"""
from __future__ import annotations

import sys

from chama.config import load_config
from chama.db import get_engine


def main(step: str) -> None:
    config = load_config()
    engine = get_engine()
    if step == "ingest":
        from chama.ingestion.excel_loader import run

        run(config, engine)
    elif step in {"anonymise", "clean"}:
        print(f"Step '{step}' is not built yet - see the GitHub issues.")
    else:
        raise SystemExit(f"Unknown step '{step}'. Use: ingest | anonymise | clean")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ingest")
