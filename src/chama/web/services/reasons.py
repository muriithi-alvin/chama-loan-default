"""Plain-word reasons for a member's band (S-4).

Each of the chosen model's three strongest SHAP factors is turned into one
sentence filled with the member's own value at that meeting, and marked
"raises risk" or "lowers risk" from the SHAP sign. Meanings follow
transform/models/features/member_months.yml; "the past year" is the
history_months look-back (12 months) in config/pipeline.yaml.

Prepared features named `missingindicator_<feature>` are 1 when the feature
had no value (for example no missed repayment yet), so they get their own
sentences. A test fails if any feature of the model has no template.

Every sentence is also written in Kiswahili (D-044), from templates of its
own, not by a translation model: the same values always give the same words.

Wording for Alvin to check (open decision 4). Never use: reject, approve,
defaulter, bad member, credit score, probability, percent chance, AI decision;
in Kiswahili: kataa, idhinisha, mdaiwa sugu, alama ya mkopo, asilimia.
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


# ---- Kiswahili (D-044) ---------------------------------------------------------------
# Meetings (mikutano) and loans (mikopo) are both of the m-mi class, so a share
# of them is written out whole here, with the noun, to keep the agreement right.

MONTHS_SW = ("", "Januari", "Februari", "Machi", "Aprili", "Mei", "Juni", "Julai", "Agosti", "Septemba",
             "Oktoba", "Novemba", "Desemba")


def _times_sw(n: int, one: str, many: str) -> str:
    return one if n == 1 else many.format(n=n)


def _ago_sw(n: int) -> str:
    """12 -> "miezi 12 iliyopita"; 107 -> "takriban miaka 9 iliyopita"."""
    if n < 24:
        return _times_sw(n, "mwezi 1 uliopita", "miezi {n} iliyopita")
    return f"takriban miaka {round(n / 12)} iliyopita"


def _meetings_share_sw(words: str, running: bool = False) -> str:
    """share_words() of a set of meetings, with the noun: "takriban nusu ya mikutano"."""
    one, many = ("wenye mkopo unaoendelea", "yenye mkopo unaoendelea") if running else ("", "")
    if words.startswith("about 1 in "):
        return " ".join(filter(None, [f"takriban mkutano 1 kati ya kila {words.rsplit(' ', 1)[1]}", one]))
    phrase = {"about half": "takriban nusu ya mikutano", "most": "mingi ya mikutano", "all": "mikutano yote"}[words]
    return " ".join(filter(None, [phrase, many]))


def _loans_share_sw(words: str) -> str:
    if words.startswith("about 1 in "):
        return f"takriban mkopo 1 kati ya kila {words.rsplit(' ', 1)[1]} unaoendelea"
    return {"about half": "takriban nusu ya mikopo inayoendelea", "most": "mingi ya mikopo inayoendelea"}[words]


FRACTIONS_SW = {"a twentieth": "sehemu moja ya ishirini ya deni", "a tenth": "sehemu moja ya kumi ya deni",
                "a fifth": "sehemu moja ya tano ya deni", "a quarter": "robo ya deni",
                "a third": "theluthi moja ya deni", "half": "nusu ya deni", "three quarters": "robo tatu ya deni",
                "all": "deni lote"}


def _months_since_last_miss_sw(v) -> str:
    n = _n(v)
    if n == 0:
        return "Hakulipa marejesho katika mkutano huu"
    return f"Mara ya mwisho kukosa kulipa marejesho ilikuwa {_ago_sw(n)}"


def _missed_last_3_sw(v) -> str:
    n = _n(v)
    if n == 0:
        return "Alilipa marejesho katika kila moja ya mikutano 3 iliyopita"
    if n >= 3:
        return "Hakulipa marejesho katika mikutano yote 3 iliyopita"
    return _times_sw(n, "Hakulipa marejesho katika mkutano 1 kati ya mikutano 3 iliyopita",
                     "Hakulipa marejesho katika mikutano {n} kati ya mikutano 3 iliyopita")


def _recent_missed_sw(v) -> str:
    n = _n(v)
    if n == 0:
        return "Hakukosa kulipa marejesho hata mara moja ndani ya mwaka uliopita"
    return _times_sw(n, "Alikosa kulipa marejesho katika mkutano 1 ndani ya mwaka uliopita",
                     "Alikosa kulipa marejesho katika mikutano {n} ndani ya mwaka uliopita")


def _recent_missed_share_sw(v) -> str:
    words = share_words(float(v))
    if words == "none":
        return "Alilipa marejesho katika kila mkutano wenye mkopo unaoendelea ndani ya mwaka uliopita"
    return f"Alikosa kulipa marejesho katika {_meetings_share_sw(words, running=True)}, ndani ya mwaka uliopita"


def _repayment_ratio_sw(v) -> str:
    share = float(v)
    if share < 0.03:
        return "Hakulipa karibu chochote cha deni katika mikutano 3 iliyopita"
    if share >= 0.9:
        return "Alilipa deni lote katika mikutano 3 iliyopita"
    return f"Alilipa takriban {FRACTIONS_SW[fraction_words(share)]} kila mkutano, katika mikutano 3 iliyopita"


def _months_in_records_sw(v) -> str:
    n = _n(v)
    if n < 12:
        return _times_sw(n, "Amekuwa kwenye rekodi kwa mwezi 1", "Amekuwa kwenye rekodi kwa miezi {n}")
    return _times_sw(n // 12, "Amekuwa kwenye rekodi kwa mwaka 1", "Amekuwa kwenye rekodi kwa miaka {n}")


def _outstanding_vs_median_sw(v) -> str:
    ratio = float(v)
    if ratio >= 1.5:
        return f"Anadaiwa takriban mara {ratio:.1f} ya mkopo wa kawaida katika chama"
    if ratio >= 1.15:
        return "Anadaiwa kidogo zaidi ya mkopo wa kawaida katika chama"
    if ratio >= 0.85:
        return "Anadaiwa takriban sawa na mkopo wa kawaida katika chama"
    if ratio >= 0.4:
        return "Anadaiwa chini ya mkopo wa kawaida katika chama"
    return "Anadaiwa kidogo sana kuliko mkopo wa kawaida katika chama"


def _oldest_open_loan_sw(v) -> str:
    n = _n(v)
    if n == 0:
        return "Mkopo wake wa zamani zaidi unaoendelea ulianza mwezi huu"
    return f"Mkopo wake wa zamani zaidi unaoendelea ulianza {_ago_sw(n)}"


def _contribution_rate_sw(v) -> str:
    words = share_words(float(v))
    if words == "all":
        return "Alilipa mchango wa kila mwezi katika kila mkutano ndani ya mwaka uliopita"
    if words == "none":
        return "Hakulipa mchango wowote wa kila mwezi ndani ya mwaka uliopita"
    return f"Alilipa mchango wa kila mwezi katika {_meetings_share_sw(words)}, ndani ya mwaka uliopita"


def _chama_missed_share_sw(v) -> str:
    words = share_words(float(v))
    if words == "none":
        return "Kila mkopo unaoendelea katika chama ulipata marejesho katika mkutano huu"
    if words == "all":
        return "Hakuna mkopo unaoendelea katika chama uliopata marejesho katika mkutano huu"
    return f"Katika mkutano huu, marejesho hayakulipwa kwa {_loans_share_sw(words)} katika chama"


def _month_of_year_sw(v) -> str:
    n = _n(v)
    name = MONTHS_SW[n] if 1 <= n <= 12 else "mwezi huu"
    if n in SCHOOL_FEES_MONTHS:
        return f"Karo za shule zinadaiwa mwezi huu ({name})"
    return f"Wakati huu wa mwaka ({name})"


TEMPLATES_SW: dict[str, Callable[[object], str]] = {
    "months_since_last_miss": _months_since_last_miss_sw,
    "missed_last_3_meetings": _missed_last_3_sw,
    "recent_missed": _recent_missed_sw,
    "recent_missed_share": _recent_missed_share_sw,
    "repayment_ratio_last_3_meetings": _repayment_ratio_sw,
    "months_in_records": _months_in_records_sw,
    "loans_so_far": lambda v: _times_sw(_n(v), "Amechukua mkopo 1 hadi sasa", "Amechukua mikopo {n} hadi sasa"),
    "prior_rolled_over": lambda v: (
        "Hajaingiza mkopo wa awali kwenye mkopo mkubwa zaidi" if _n(v) == 0
        else _times_sw(_n(v), "Aliingiza mkopo 1 wa awali kwenye mkopo mkubwa zaidi",
                       "Aliingiza mikopo {n} ya awali kwenye mikopo mikubwa zaidi")),
    "open_loans": lambda v: _times_sw(_n(v), "Ana mkopo 1 unaoendelea", "Ana mikopo {n} inayoendelea"),
    "outstanding_vs_chama_median": _outstanding_vs_median_sw,
    "oldest_open_loan_months": _oldest_open_loan_sw,
    "loan_started_this_meeting": _yes_no("Alichukua mkopo mpya katika mkutano huu",
                                         "Hakuchukua mkopo mpya katika mkutano huu"),
    "has_emergency_loan": _yes_no("Ana mkopo wa dharura unaoendelea", "Hana mkopo wa dharura unaoendelea"),
    "has_school_fees_loan": _yes_no("Ana mkopo wa karo unaoendelea", "Hana mkopo wa karo unaoendelea"),
    "recent_contribution_rate": _contribution_rate_sw,
    "chama_missed_share": _chama_missed_share_sw,
    "month_of_year": _month_of_year_sw,
}

MISSING_SW: dict[str, tuple[str, str]] = {
    "months_since_last_miss": ("Hajawahi kukosa kulipa marejesho kwenye rekodi",
                               "Amewahi kukosa kulipa marejesho hapo awali"),
    "recent_missed_share": ("Mkopo ni mpya mno kuwa na rekodi ya marejesho ya mwaka uliopita",
                            "Ana rekodi ya marejesho ya mwaka uliopita"),
    "repayment_ratio_last_3_meetings": ("Mkopo ni mpya mno kuwa na rekodi ya marejesho ya mikutano 3 iliyopita",
                                        "Ana rekodi ya marejesho ya mikutano 3 iliyopita"),
    "recent_contribution_rate": ("Hakuna rekodi ya michango ya mwaka uliopita",
                                 "Ana rekodi ya michango ya mwaka uliopita"),
    "outstanding_vs_chama_median": ("Bado hakuna mkopo wa kawaida katika chama wa kulinganisha nao",
                                    "Imelinganishwa na mkopo wa kawaida katika chama"),
    "chama_missed_share": ("Hakuna mikopo mingine inayoendelea katika chama katika mkutano huu",
                           "Kuna mikopo mingine inayoendelea katika chama katika mkutano huu"),
}

LANGUAGES = ("en", "sw")
_BY_LANGUAGE = {
    "en": (TEMPLATES, MISSING, "Part of the record is missing at this meeting"),
    "sw": (TEMPLATES_SW, MISSING_SW, "Sehemu ya rekodi haipo katika mkutano huu"),
}


def base_feature(factor: str) -> str:
    return factor.removeprefix(INDICATOR)


def has_template(factor: str, lang: str = "en") -> bool:
    templates, missing, _ = _BY_LANGUAGE[lang]
    if factor.startswith(INDICATOR):
        return base_feature(factor) in missing
    return factor in templates


def sentence(factor: str, values: dict, lang: str = "en") -> str:
    """The sentence for one prepared feature, from the member's own values.

    `values` holds the member's unprepared features at the meeting (None or
    NaN where a value is missing). `lang` is "en" or "sw".
    """
    templates, missing_words, gap = _BY_LANGUAGE[lang]
    base = base_feature(factor)
    value = values.get(base)
    missing = value is None or (isinstance(value, float) and math.isnan(value))
    if factor.startswith(INDICATOR) or missing:
        if base not in missing_words:
            return gap
        return missing_words[base][0] if missing else missing_words[base][1]
    return templates[base](value)
