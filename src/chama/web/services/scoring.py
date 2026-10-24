"""The scoring step (S-4): bands and reasons for every member owing at each
chama's latest meeting, saved to app.risk_scores for the pages to read.

1. The chosen early-warning model, its run and band cut-offs (D-022, D-023).
2. The rows of analytics.member_months at each chama's latest recorded
   meeting: one per member who owes on a loan after it.
3. Band from the cut-offs: High at or above `high`, Medium at or above
   `medium`, otherwise Low. The score itself is never saved (G3).
4. The three strongest SHAP factors, each as a sentence (reasons.py).

Run by `python -m chama.pipeline score` and by the worker after a scan is
accepted. Scores for earlier meetings are kept, so bands can be compared.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import text

from chama import StepFailed
from chama.models.data import MISSED_REPAYMENT, xy
from chama.web.services.reasons import sentence

TARGET = "missed_repayment"


@dataclass
class LoadedModel:
    run_id: str
    model_name: str
    model: object
    cutoffs: dict

    @classmethod
    def load(cls, config: dict) -> LoadedModel:
        from chama.models.chosen import chosen_model

        run, model, cutoffs = chosen_model(TARGET, config)
        return cls(run_id=run["run_id"], model_name=str(run.get("params.model", "model")),
                   model=model, cutoffs=cutoffs)


@dataclass
class ChamaScores:
    chama_id: str
    page_no: int | None
    members: int
    bands: dict


def band_of(score: float, cutoffs: dict) -> str:
    if score >= cutoffs["high"]:
        return "high"
    if score >= cutoffs["medium"]:
        return "medium"
    return "low"


def latest_rows(conn, chama_id: str) -> pd.DataFrame:
    """member_months at the chama's latest recorded meeting, with its date."""
    return pd.read_sql(text(
        "SELECT mm.*, m.meeting_date FROM analytics.member_months mm "
        "JOIN analytics.meetings m ON m.chama_id = mm.chama_id AND m.page_no = mm.page_no "
        "WHERE mm.chama_id = :c AND mm.page_no = "
        "(SELECT max(page_no) FROM analytics.meetings WHERE chama_id = :c)"
    ), conn, params={"c": chama_id})


def reasons_for(model, X: pd.DataFrame, n: int = 3) -> list[list[dict]]:
    from chama.models.explain import shap_values, top_factors

    contributions = shap_values(model, X)
    out = []
    for i in range(len(X)):
        values = X.iloc[i].to_dict()
        factors = top_factors(contributions.iloc[i], n=n)
        out.append([
            {"feature": f.factor, "sentence": sentence(f.factor, values), "effect": f.effect}
            for f in factors.itertuples()
        ])
    return out


def score_chama(engine, loaded: LoadedModel, chama_id: str) -> ChamaScores:
    with engine.connect() as conn:
        rows = latest_rows(conn, chama_id)
    if rows.empty:
        return ChamaScores(chama_id, None, 0, {})
    X, _ = xy(rows, MISSED_REPAYMENT)
    scores = loaded.model.predict_proba(X)[:, 1]
    bands = [band_of(s, loaded.cutoffs) for s in scores]
    reasons = reasons_for(loaded.model, X)

    records = [
        {"c": chama_id, "m": row.member_code, "p": int(row.page_no), "mm": row.meeting_month,
         "md": row.meeting_date if pd.notna(row.meeting_date) else None, "b": band,
         "r": json.dumps(why), "run": loaded.run_id, "name": loaded.model_name}
        for row, band, why in zip(rows.itertuples(), bands, reasons)
    ]
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO app.risk_scores (chama_id, member_code, page_no, meeting_month, meeting_date, "
            "band, reasons, model_run_id, model_name) "
            "VALUES (:c, :m, :p, :mm, :md, :b, CAST(:r AS jsonb), :run, :name) "
            "ON CONFLICT (chama_id, member_code, page_no, model_run_id) DO UPDATE SET "
            "band = EXCLUDED.band, reasons = EXCLUDED.reasons, meeting_month = EXCLUDED.meeting_month, "
            "meeting_date = EXCLUDED.meeting_date, model_name = EXCLUDED.model_name, scored_at = now()"
        ), records)
    counts = pd.Series(bands).value_counts().to_dict()
    return ChamaScores(chama_id, int(rows["page_no"].iloc[0]), len(rows), counts)


def run_score(config: dict, engine, chama_ids: list[str] | None = None,
              loaded: LoadedModel | None = None) -> list[ChamaScores]:
    from chama.db import create_schemas, table_exists

    create_schemas(engine)
    with engine.connect() as conn:
        if not table_exists(conn, "analytics.member_months"):
            raise StepFailed("analytics.member_months not found. Run python -m chama.pipeline all first.")
    loaded = loaded or LoadedModel.load(config)
    ids = chama_ids or [c["id"] for c in config["chamas"]]
    results = []
    for chama_id in ids:
        result = score_chama(engine, loaded, chama_id)
        results.append(result)
        if result.page_no is None:
            print(f"[{chama_id}] no member owes at the latest meeting - nothing to score")
        else:
            bands = ", ".join(f"{b}: {result.bands.get(b, 0)}" for b in ("high", "medium", "low"))
            print(f"[{chama_id}] ledger page {result.page_no}: {result.members} members scored ({bands}) "
                  f"with run {loaded.run_id[:8]}")
    return results
