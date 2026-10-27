"""The reason sentences (S-4): every model feature has one, in plain words."""
import math

import pytest

from chama.models.data import MISSED_REPAYMENT
from chama.web.services import reasons

FORBIDDEN = ["reject", "approve", "defaulter", "bad member", "credit score", "probability",
             "percent chance", "ai decision", "%"]

# Values each feature can take, including the edges of each wording.
SAMPLES = {
    "open_loans": [1, 2, 3],
    "outstanding_vs_chama_median": [0.2, 0.6, 1.0, 1.3, 2.4],
    "oldest_open_loan_months": [0, 1, 14],
    "loan_started_this_meeting": [0, 1],
    "has_emergency_loan": [0, 1],
    "has_school_fees_loan": [0, 1],
    "months_in_records": [0, 1, 11, 12, 30, 125],
    "loans_so_far": [1, 4],
    "prior_rolled_over": [0, 1, 2],
    "missed_last_3_meetings": [0, 1, 2, 3],
    "recent_missed": [0, 1, 5],
    "recent_missed_share": [0, 0.1, 0.25, 0.5, 0.8, 1],
    "repayment_ratio_last_3_meetings": [0, 0.01, 0.1, 0.27, 0.5, 0.95],
    "months_since_last_miss": [0, 1, 7],
    "recent_contribution_rate": [0, 0.5, 0.9, 1],
    "chama_missed_share": [0, 0.1, 0.3, 0.5, 1],
    "month_of_year": [1, 3, 5, 9, 12],
}


def test_every_feature_of_the_model_has_a_template():
    missing = [f for f in MISSED_REPAYMENT.features if not reasons.has_template(f)]
    assert missing == []
    assert set(SAMPLES) == set(MISSED_REPAYMENT.features)


@pytest.mark.parametrize("feature", MISSED_REPAYMENT.features)
def test_sentences_are_plain_and_never_use_forbidden_words(feature):
    for value in SAMPLES[feature]:
        text = reasons.sentence(feature, {feature: value})
        assert text and text[0].isupper() and not text.endswith(".")
        assert not any(word in text.lower() for word in FORBIDDEN), text


@pytest.mark.parametrize("feature", sorted(reasons.MISSING))
def test_missing_values_have_their_own_sentences(feature):
    missing = reasons.sentence(f"missingindicator_{feature}", {feature: None})
    present = reasons.sentence(f"missingindicator_{feature}", {feature: 0.5})
    assert missing != present
    assert reasons.sentence(feature, {feature: math.nan}) == missing


def test_sentences_use_the_members_own_values():
    assert reasons.sentence("missed_last_3_meetings", {"missed_last_3_meetings": 2.0}) == \
        "Missed a repayment at 2 of the last 3 meetings"
    assert reasons.sentence("months_since_last_miss", {"months_since_last_miss": 1}) == \
        "Last missed a repayment 1 month ago"
    assert reasons.sentence("months_since_last_miss", {"months_since_last_miss": 107}) == \
        "Last missed a repayment about 9 years ago"
    assert reasons.sentence("oldest_open_loan_months", {"oldest_open_loan_months": 30}) == \
        "Oldest running loan started about 2 years ago"
    assert reasons.sentence("months_in_records", {"months_in_records": 125}) == \
        "Has been in the records for 10 years"
    assert reasons.sentence("outstanding_vs_chama_median", {"outstanding_vs_chama_median": 2.4}) == \
        "Owes about 2.4 times a typical loan in the chama"
    assert reasons.sentence("month_of_year", {"month_of_year": 9}) == "School fees fall due this month (September)"


def test_share_words():
    assert reasons.share_words(0) == "none"
    assert reasons.share_words(0.25) == "about 1 in 4"
    assert reasons.share_words(0.12) == "about 1 in 8"
    assert reasons.share_words(0.5) == "about half"
    assert reasons.share_words(0.75) == "most"
    assert reasons.share_words(1) == "all"
