"""Create an empty raw Excel template with one sheet per table and a README sheet.

Usage:
    python scripts/make_raw_template.py                  # -> data/raw/raw_template.xlsx
    python scripts/make_raw_template.py path/to/file.xlsx
"""
from __future__ import annotations

import sys
from pathlib import Path

from chama.config import PROJECT_ROOT
from chama.ingestion.template import build_template

if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "data/raw/raw_template.xlsx"
    print(f"Template written to {build_template(target)}")
