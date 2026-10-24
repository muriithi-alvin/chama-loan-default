"""Plain-word reasons for a member's band (S-4).

Each of the chosen model's three strongest SHAP factors is turned into one
sentence filled with the member's own value at that meeting, and marked
"raises risk" or "lowers risk" from the SHAP sign. Meanings follow
transform/models/features/member_months.yml; "the past year" is the
history_months look-back (12 months) in config/pipeline.yaml.

Prepared features named `missingindicator_<feature>` are 1 when the feature
had no value (for example no missed repayment yet), so they get their own
sentences. A test fails if any feature of the model has no template.

Wording for Alvin to check (open decision 4). Never use: reject, approve,
defaulter, bad member, credit score, probability, percent chance, AI decision.
"""
from __future__ import annotations

import calendar
import math
from collections.abc import Callable

INDICATOR = "missingindicator_"
SCHOOL_FEES_MONTHS = {1, 5, 9}


def _n(value) -> int:
    return round(float(value))


def _times(n: int, one: str, many: str) -> str:
    return one if n == 1 else many.format(n=n)


def share_words(share: float) -> str:
    """0.25 -> "about 1 in 4"; 0.5 -> "about half"; 0.8 -> "most"."""
    if share <= 0.02:
        return "none"
    if share >= 0.95:
        return "all"
    if share >= 0.6:
        return "most"
    if share >= 0.4:
        return "about half"
    return f"about 1 in {max(2, round(1 / share))}"


FRACTIONS = [(0.05, "a twentieth"), (0.1, "a tenth"), (0.2, "a fifth"), (0.25, "a quarter"),
             (1 / 3, "a third"), (0.5, "half"), (0.75, "three quarters"), (1.0, "all")]


def fraction_words(share: float) -> str:
    return min(FRACTIONS, key=lambda f: abs(f[0] - share))[1]


def _ago(n: int) -> str:
    """12 -> "12 months ago"; 107 -> "about 9 years ago"."""
    if n < 24:
        return _times(n, "1 month ago", "{n} months ago")
    return f"about {round(n / 12)} years ago"


def _months_since_last_miss(v) -> str:
    n = _n(v)
    if n == 0:
        return "Missed a repayment at this meeting"
    return f"Last missed a repayment {_ago(n)}"


def _missed_last_3(v) -> str:
    n = _n(v)
    if n == 0:
        return "Repaid at each of the last 3 meetings"
    return f"Missed a repayment at {n} of the last 3 meetings"


def _recent_missed(v) -> str:
    n = _n(v)
    if n == 0:
        return "No missed repayments in the past year"
    return _times(n, "Missed a repayment at 1 meeting in the past year",
                  "Missed repayments at {n} meetings in the past year")


def _recent_missed_share(v) -> str:
    words = share_words(float(v))
    if words == "none":
        return "Repaid at every meeting with a loan running in the past year"
    return f"Missed a repayment at {words} of their meetings with a loan running in the past year"


def _repayment_ratio(v) -> str:
    share = float(v)
    if share < 0.03:
        return "Repaid almost nothing of the balance over the last 3 meetings"
    if share >= 0.9:
        return "Repaid the whole balance over the last 3 meetings"
    return f"Repaid about {fraction_words(share)} of the balance per meeting over the last 3 meetings"


def _months_in_records(v) -> str:
    n = _n(v)
    if n < 12:
        return _times(n, "Has been in the records for 1 month", "Has been in the records for {n} months")
    years = n // 12
    return _times(years, "Has been in the records for 1 year", "Has been in the records for {n} years")


def _outstanding_vs_median(v) -> str:
    ratio = float(v)
    if ratio >= 1.5:
        return f"Owes about {ratio:.1f} times a typical loan in the chama"
    if ratio >= 1.15:
        return "Owes a little more than a typical loan in the chama"
    if ratio >= 0.85:
        return "Owes about as much as a typical loan in the chama"
    if ratio >= 0.4:
        return "Owes less than a typical loan in the chama"
    return "Owes much less than a typical loan in the chama"


def _oldest_open_loan(v) -> str:
    n = _n(v)
    if n == 0:
        return "Oldest running loan started this month"
    return f"Oldest running loan started {_ago(n)}"


def _yes_no(yes: str, no: str) -> Callable[[object], str]:
    return lambda v: yes if bool(_n(v)) else no


def _contribution_rate(v) -> str:
    words = share_words(float(v))
    if words == "all":
        return "Paid the monthly contribution at every meeting in the past year"
    if words == "none":
        return "Paid no monthly contributions in the past year"
    return f"Paid the monthly contribution at {words} of the meetings in the past year"


def _chama_missed_share(v) -> str:
    words = share_words(float(v))
    if words == "none":
        return "Every running loan in the chama got a repayment at this meeting"
    if words == "all":
        return "No running loan in the chama got a repayment at this meeting"
    return f"{words[0].upper()}{words[1:]} of the chama's running loans got no repayment at this meeting"


def _month_of_year(v) -> str:
    n = _n(v)
    name = calendar.month_name[n] if 1 <= n <= 12 else "this month"
    if n in SCHOOL_FEES_MONTHS:
        return f"School fees fall due this month ({name})"
    return f"The time of year ({name})"


TEMPLATES: dict[str, Callable[[object], str]] = {
    "months_since_last_miss": _months_since_last_miss,
    "missed_last_3_meetings": _missed_last_3,
    "recent_missed": _recent_missed,
    "recent_missed_share": _recent_missed_share,
    "repayment_ratio_last_3_meetings": _repayment_ratio,
    "months_in_records": _months_in_records,
    "loans_so_far": lambda v: _times(_n(v), "Has taken 1 loan so far", "Has taken {n} loans so far"),
    "prior_rolled_over": lambda v: (
        "Has not rolled an earlier loan into a bigger one" if _n(v) == 0
        else _times(_n(v), "Rolled 1 earlier loan into a bigger one", "Rolled {n} earlier loans into bigger ones")),
    "open_loans": lambda v: _times(_n(v), "Has 1 loan running", "Has {n} loans running"),
    "outstanding_vs_chama_median": _outstanding_vs_median,
    "oldest_open_loan_months": _oldest_open_loan,
    "loan_started_this_meeting": _yes_no("Took a new loan at this meeting", "Took no new loan at this meeting"),
    "has_emergency_loan": _yes_no("Has an emergency loan running", "Has no emergency loan running"),
    "has_school_fees_loan": _yes_no("Has a school-fees loan running", "Has no school-fees loan running"),
    "recent_contribution_rate": _contribution_rate,
    "chama_missed_share": _chama_missed_share,
    "month_of_year": _month_of_year,
}

# Sentences for "this value was missing" (missingindicator_<feature> = 1) and
# for "it was there" (= 0).
MISSING: dict[str, tuple[str, str]] = {
    "months_since_last_miss": ("Has never missed a repayment in the records", "Has missed a repayment before"),
    "recent_missed_share": ("Loan too new for a repayment record in the past year",
                            "Has a repayment record for the past year"),
    "repayment_ratio_last_3_meetings": ("Loan too new for a repayment record over the last 3 meetings",
                                        "Has a repayment record over the last 3 meetings"),
    "recent_contribution_rate": ("No contribution record for the past year",
                                 "Has a contribution record for the past year"),
    "outstanding_vs_chama_median": ("No typical loan size in the chama to compare with yet",
                                    "Compared with a typical loan in the chama"),
    "chama_missed_share": ("No other running loans in the chama at this meeting",
                           "Other running loans in the chama at this meeting"),
}


def base_feature(factor: str) -> str:
    return factor.removeprefix(INDICATOR)


def has_template(factor: str) -> bool:
    if factor.startswith(INDICATOR):
        return base_feature(factor) in MISSING
    return factor in TEMPLATES


def sentence(factor: str, values: dict) -> str:
    """The sentence for one prepared feature, from the member's own values.

    `values` holds the member's unprepared features at the meeting (None or
    NaN where a value is missing).
    """
    base = base_feature(factor)
    value = values.get(base)
    missing = value is None or (isinstance(value, float) and math.isnan(value))
    if factor.startswith(INDICATOR) or missing:
        if base not in MISSING:
            return "Part of the record is missing at this meeting"
        return MISSING[base][0] if missing else MISSING[base][1]
    return TEMPLATES[base](value)
