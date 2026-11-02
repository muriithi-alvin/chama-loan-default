"""What the officials' Overview, Members list and Member page show (OFF-1 to OFF-3).

Everything is read from saved scores (app.risk_scores) and the records; no
model runs while a page loads (X9). Each score carries where it came from:
the meeting, the model run and when it was scored (G4). No raw score or
percentage is ever returned (G3).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.engine import Connection

from chama.web.data import records
from chama.web.services.names import display_name, member_names
from chama.web.settings import chama_name

BAND_ORDER = {"high": 0, "medium": 1, "low": 2}

# Each band in everyday words, as the pages name them: "Follow up now",
# "Keep an eye on", "Less likely to miss" (Sprint II feedback). How often each
# band missed in testing (35% / 24% / 12%, Milestone 2 report section 14.2)
# is on the About page only.
BAND_MEANING = {
    "high": "More likely than others to miss a repayment in the next 3 meetings. Talk to them first.",
    "medium": "Could miss a repayment in the next 3 meetings. Check in when you can.",
    "low": "Less likely to miss a repayment in the next 3 meetings.",
}
FOLLOW_UP_NOTE = "This is a prompt to follow up, not a decision."


def model_label(model_name: str, run_id: str) -> str:
    return f"{model_name.replace('_', ' ')} {run_id[:8]}"


def _source(score: dict) -> dict:
    return {
        "page_no": score["page_no"],
        "meeting_month": score["meeting_month"],
        "meeting_date": score["meeting_date"],
        "model_run_id": score["model_run_id"],
        "model_label": model_label(score["model_name"], score["model_run_id"]),
        "model_version": score.get("model_version"),
        "model_checksum": score.get("model_checksum"),
        "scored_at": score["scored_at"],
    }


def _meeting(row: dict | None) -> dict | None:
    if not row:
        return None
    return {"page_no": row["page_no"], "meeting_month": row["meeting_month"],
            "meeting_date": row["meeting_date"]}


def current_scores(conn: Connection, chama_id: str) -> tuple[list[dict], dict | None]:
    page = records.latest_scored_page(conn, chama_id)
    if page is None:
        return [], None
    scores = records.scores_at(conn, chama_id, page)
    newest = max(scores, key=lambda s: s["scored_at"]) if scores else None
    return scores, (_source(newest) if newest else None)


def overview(conn: Connection, chama_id: str) -> dict:
    names = member_names(conn, chama_id)
    last = records.latest_meeting(conn, chama_id)
    scores, source = current_scores(conn, chama_id)
    before = records.previous_bands(conn, chama_id, source["page_no"]) if source else {}

    scores.sort(key=lambda s: (BAND_ORDER[s["band"]], display_name(names, s["member_code"])))
    strand = [{
        "code": s["member_code"],
        "name": display_name(names, s["member_code"]),
        "band": s["band"],
        "moved_from": before.get(s["member_code"]) if before.get(s["member_code"], s["band"]) != s["band"]
        else None,
    } for s in scores]
    follow_up = [{
        "code": s["member_code"],
        "name": display_name(names, s["member_code"]),
        "band": s["band"],
        "reason": next((r for r in s["reasons"] if r["effect"] == "raises risk"), s["reasons"][0]),
    } for s in scores if s["band"] in ("high", "medium")]

    loans = records.running_loans(conn, chama_id)
    missed = records.missed_at_meeting(conn, chama_id, last["page_no"]) if last else {"running": 0, "missed": 0}
    counts = {b: sum(1 for s in scores if s["band"] == b) for b in BAND_ORDER}
    counts["no_loan"] = max(0, len(names) - len(scores))
    return {
        "chama": {"id": chama_id, "name": chama_name(chama_id)},
        "last_meeting": _meeting(last),
        "scores": source,
        "scores_behind": bool(source and last and last["page_no"] > source["page_no"]),
        "counts": counts,
        "strand": strand,
        "follow_up": follow_up,
        "health": {
            "open_loans": len(loans),
            "outstanding": float(sum(l["last_balance"] or 0 for l in loans)),
            "running_last_meeting": missed["running"],
            "missed_last_meeting": missed["missed"],
        },
    }


def members_list(conn: Connection, chama_id: str) -> dict:
    names = member_names(conn, chama_id)
    scores, source = current_scores(conn, chama_id)
    band_of = {s["member_code"]: s["band"] for s in scores}
    months = records.member_months_at(conn, chama_id, source["page_no"]) if source else {}
    loans = records.running_loans(conn, chama_id)
    rows = []
    for code in records.member_codes(conn, chama_id):
        own = [l for l in loans if l["member_code"] == code]
        rows.append({
            "code": code,
            "name": display_name(names, code),
            "band": band_of.get(code),
            "open_loans": len(own),
            "outstanding": float(sum(l["last_balance"] or 0 for l in own)),
            "missed_last_3": months.get(code, {}).get("missed_last_3_meetings"),
        })
    return {"members": rows, "scores": source}


def _interest(line: dict) -> float | None:
    if line["interest_amount"] is not None:
        return float(line["interest_amount"])
    if line["interest_rate_pct"] is not None and line["opening_balance"] is not None:
        return round(float(line["opening_balance"]) * float(line["interest_rate_pct"]) / 100)
    return None


def _num(value) -> float | None:
    return None if value is None else float(value)


def member_page(conn: Connection, chama_id: str, code: str) -> dict:
    names = member_names(conn, chama_id)
    scores, source = current_scores(conn, chama_id)
    score = next((s for s in scores if s["member_code"] == code), None)
    first: date | None = records.member_first_month(conn, chama_id, code)
    loans = records.member_loans(conn, chama_id, code)
    return {
        "code": code,
        "name": display_name(names, code),
        "member_since": first.year if first else None,
        "band": score["band"] if score else None,
        "meaning": BAND_MEANING[score["band"]] if score else None,
        "note": FOLLOW_UP_NOTE,
        "reasons": score["reasons"] if score else [],
        "source": _source(score) if score else source,
        "loans": [{
            "type": l["loan_type"],
            "issued_month": l["issued_month"],
            "due_month": l["due_month"],
            "status": l["status"],
            "running": bool(l["running"]),
            "outstanding": float(l["last_balance"] or 0) if l["running"] else 0.0,
            "amount": _num(l["amount_given"]),
            "rolled_into_month": l["rolled_into_month"],
        } for l in loans],
        "repayments": [{
            "page_no": line["page_no"],
            "meeting_month": line["meeting_month"],
            "meeting_date": line["meeting_date"],
            "loan_type": line["loan_type"] or "normal",
            "balance_before": _num(line["opening_balance"]),
            "repaid": _num(line["repayment"]),
            "interest": _interest(line),
            "balance_after": _num(line["closing_balance"]),
            "missed": line["line_kind"] == "balance" and not line["repayment"],
        } for line in records.member_lines(conn, chama_id, code)],
        "contributions": [{
            "page_no": c["page_no"],
            "meeting_month": c["meeting_month"],
            "amount": _num(c["amount"]),
            "paid": bool(c["amount"] and c["amount"] > 0),
        } for c in records.member_contributions(conn, chama_id, code)],
    }


def my_summary(conn: Connection, chama_id: str, code: str) -> dict:
    """A member's own money (MEM-1): loans, the next due month, contributions and
    repayments. Never a band, a reason or another member (R2, MEM-3)."""
    page = member_page(conn, chama_id, code)
    running = [loan for loan in page["loans"] if loan["running"]]
    due = sorted(loan["due_month"] for loan in running if loan["due_month"])
    return {
        "name": page["name"],
        "member_since": page["member_since"],
        "balance": sum(loan["outstanding"] for loan in running),
        "next_due_month": due[0] if due else None,
        "loans": page["loans"],
        "repayments": page["repayments"],
        "contributions": page["contributions"],
    }
