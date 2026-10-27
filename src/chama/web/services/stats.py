"""Page speed from the request log (X9): `python -m chama.pipeline web-stats`.

The API appends one line per request to data/logs/requests.jsonl with the
route, the status and the time on the server in milliseconds. This prints
the median and the 95th percentile per route, against the 100 ms target.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from chama import StepFailed
from chama.config import shown_path

TARGET_MS = 100


def request_times(path: Path, last: int | None = None) -> pd.DataFrame:
    if not path.exists():
        raise StepFailed(f"No request log yet at {shown_path(path)}. Open some pages first.")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    df = pd.DataFrame(rows)
    if last:
        df = df.tail(last)
    return df


def summary(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby(["method", "route"])["ms"]
    out = pd.DataFrame({
        "requests": grouped.size(),
        "median_ms": grouped.median().round(1),
        "p95_ms": grouped.quantile(0.95).round(1),
    }).reset_index().sort_values("p95_ms", ascending=False)
    out["within_target"] = out["p95_ms"] <= TARGET_MS
    return out


def run_stats(log_dir: Path, last: int | None = None) -> None:
    df = request_times(log_dir / "requests.jsonl", last)
    table = summary(df)
    print(table.to_string(index=False))
    every = df["ms"]
    print(f"\nAll {len(df)} requests: median {every.median():.1f} ms, 95th percentile "
          f"{every.quantile(0.95):.1f} ms (target: under {TARGET_MS} ms on the server)")
