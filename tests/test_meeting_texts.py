"""The officials' text the day before each meeting (D-045).

When it is due, what it says in English and Kiswahili, and that each official
gets it once. The sending tests use a separate test database, `chama_test`
(skipped when PostgreSQL is not running), and a fake Africa's Talking, so
nothing is sent anywhere.
"""
from __future__ import annotations

from datetime import date, datetime
from urllib.parse import parse_qs

import httpx
import pytest
from sqlalchemy import text

from chama import StepFailed
from chama.web.services import meeting_texts as texts
from chama.web.services.sms_hook import SmsSettings

EAT = texts.NAIROBI


# ---- When ---------------------------------------------------------------------------


def test_meeting_days_are_read_as_the_ledger_shows_them():
    assert texts.parse_rule("first sunday") == (1, 6)
    assert texts.parse_rule("  Last Saturday ") == (-1, 5)
    for wrong in ("sunday", "fifth sunday", "first funday", "every week"):
        with pytest.raises(StepFailed, match="meets"):
            texts.parse_rule(wrong)


def test_the_meeting_in_a_month():
    assert texts.meeting_in_month(2026, 11, "first sunday") == date(2026, 11, 1)    # the 1st is a Sunday
    assert texts.meeting_in_month(2026, 12, "first sunday") == date(2026, 12, 6)
    assert texts.meeting_in_month(2026, 12, "second saturday") == date(2026, 12, 12)
    assert texts.meeting_in_month(2026, 12, "last sunday") == date(2026, 12, 27)
    assert texts.meeting_in_month(2027, 2, "fourth sunday") == date(2027, 2, 28)


def test_the_next_meeting_is_on_or_after_today_and_crosses_the_year():
    assert texts.next_meeting("first sunday", date(2026, 11, 12)) == date(2026, 12, 6)
    assert texts.next_meeting("first sunday", date(2026, 12, 6)) == date(2026, 12, 6)
    assert texts.next_meeting("first sunday", date(2026, 12, 7)) == date(2027, 1, 3)


def test_the_text_is_due_the_day_before_from_the_hour_in_nairobi():
    rule = "first sunday"                                          # 6 Dec 2026
    assert texts.due(rule, datetime(2026, 12, 5, 9, 0, tzinfo=EAT), 9) == date(2026, 12, 6)
    assert texts.due(rule, datetime(2026, 12, 5, 23, 59, tzinfo=EAT), 9) == date(2026, 12, 6)
    assert texts.due(rule, datetime(2026, 12, 5, 8, 59, tzinfo=EAT), 9) is None       # too early
    assert texts.due(rule, datetime(2026, 12, 6, 10, 0, tzinfo=EAT), 9) is None       # the meeting day itself
    assert texts.due(rule, datetime(2026, 12, 4, 12, 0, tzinfo=EAT), 9) is None       # two days before
    # 06:30 UTC is 09:30 in Nairobi: the clock is read in Kenya's time, wherever the server is
    utc = datetime.fromisoformat("2026-12-05T06:30:00+00:00")
    assert texts.due(rule, utc, 9) == date(2026, 12, 6)


# ---- What -------------------------------------------------------------------------

MEETING = date(2026, 12, 6)
SITE = "https://someone-kibaba.hf.space"
FRESH = date(2026, 11, 1)          # last month's page is in


def test_the_text_gives_counts_in_english():
    words = texts.message("en", MEETING, texts.Counts(3, 5, FRESH), SITE)
    assert words == ("Kibaba: before tomorrow's meeting (Sunday 6 Dec), 3 members to follow up now and 5 to keep "
                     "an eye on. See who and why: https://someone-kibaba.hf.space/o")
    assert "1 member to follow up now." in texts.message("en", MEETING, texts.Counts(1, 0, FRESH), None)
    assert "2 members to keep an eye on." in texts.message("en", MEETING, texts.Counts(0, 2, FRESH), None)
    assert "no member needs following up." in texts.message("en", MEETING, texts.Counts(0, 0, FRESH), None)
    assert "add the last meeting's page" in texts.message("en", MEETING, texts.Counts(0, 0, None), None)


def test_the_text_gives_counts_in_kiswahili():
    words = texts.message("sw", MEETING, texts.Counts(3, 5, FRESH), SITE)
    assert words == ("Kibaba: kabla ya mkutano wa kesho (Jumapili 6 Desemba), wanachama 3 wa kufuatilia sasa na 5 "
                     "wa kuangalia kwa karibu. Ona ni nani na kwa nini: https://someone-kibaba.hf.space/o")
    assert "mwanachama 1 wa kufuatilia sasa." in texts.message("sw", MEETING, texts.Counts(1, 0, FRESH), None)
    assert "hakuna mwanachama wa kufuatilia." in texts.message("sw", MEETING, texts.Counts(0, 0, FRESH), None)


def test_the_text_says_where_old_records_stop():
    old = texts.Counts(2, 0, date(2024, 7, 1))
    assert texts.message("en", MEETING, old, None).endswith(" The latest page is from July 2024.")
    assert texts.message("sw", MEETING, old, None).endswith(" Ukurasa wa mwisho ni wa Julai 2024.")
    assert "latest page" not in texts.message("en", MEETING, texts.Counts(2, 0, FRESH), None)
    assert texts.is_stale(MEETING, date(2026, 10, 1)) and not texts.is_stale(MEETING, date(2026, 11, 1))


def test_the_text_holds_no_names_and_fits_two_texts():
    for lang in ("en", "sw"):
        words = texts.message(lang, MEETING, texts.Counts(12, 14, date(2024, 7, 1)), SITE)
        assert len(words) <= 306, len(words)     # two joined texts of 153 characters at most
        assert words.isascii()                   # plain GSM letters: no character makes it cost more


# ---- Once ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine(fresh_db):
    with fresh_db.begin() as conn:
        conn.execute(text("INSERT INTO analytics.meetings VALUES ('chama_demo', 149, '2026-11-01', '2026-11-01', "
                          "'written', 'chama_demo_p149.jpg', '2026.xlsx')"))
        conn.execute(text(
            "INSERT INTO app.users (email, role, chama_id, member_code, display_name, position, phone, language) "
            "VALUES ('t@example.com', 'official', 'chama_demo', NULL, 'Treasurer', 'treasurer', '+254700000001', 'en'), "
            "('c@example.com', 'official', 'chama_demo', NULL, 'Chair', 'chair', '+254700000003', 'sw'), "
            "('s@example.com', 'official', 'chama_demo', NULL, 'Secretary', 'secretary', NULL, 'en'), "
            "('m@example.com', 'member', 'chama_demo', 'M-1', NULL, NULL, '+254700000002', 'en')"))
        conn.execute(text(
            "INSERT INTO app.risk_scores (chama_id, member_code, page_no, meeting_month, band, reasons, "
            "model_run_id, model_name) VALUES "
            "('chama_demo', 'M-1', 149, '2026-11-01', 'high', '[]', 'run', 'rf'), "
            "('chama_demo', 'M-2', 149, '2026-11-01', 'medium', '[]', 'run', 'rf'), "
            "('chama_demo', 'M-3', 149, '2026-11-01', 'low', '[]', 'run', 'rf')"))
    return fresh_db


class FakeAT:
    """Africa's Talking: records each text and answers that it was sent, or refuses."""

    def __init__(self, refuse: bool = False):
        self.sent, self.refuse = [], refuse

    def client(self) -> httpx.Client:
        def handler(request: httpx.Request) -> httpx.Response:
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            self.sent.append(form)
            if self.refuse:
                return httpx.Response(401, text="The supplied authentication is invalid")
            return httpx.Response(201, json={"SMSMessageData": {"Recipients": [
                {"statusCode": 101, "number": form["to"], "status": "Success", "cost": "KES 0.8000"}]}})
        return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture
def only_the_demo_chama(monkeypatch):
    from chama.web import settings as settings_module

    monkeypatch.setattr(texts, "chamas", lambda: {"chama_demo": {"id": "chama_demo", "meets": "first sunday"},
                                                  "chama_a": {"id": "chama_a"}})
    monkeypatch.setenv("WEB_ORIGINS", SITE)
    settings_module.web_settings.cache_clear()
    yield
    settings_module.web_settings.cache_clear()


SMS = SmsSettings("", "kibaba", "at-key")
SATURDAY = datetime(2026, 12, 5, 9, 30, tzinfo=EAT)


def test_each_official_with_a_phone_is_texted_once_in_their_language(engine, only_the_demo_chama):
    fake = FakeAT()
    done = texts.send_due(engine, SATURDAY, SMS, 9, fake.client())
    assert sorted(f["to"] for f in fake.sent) == ["+254700000001", "+254700000003"]   # officials with a phone only
    by_number = {f["to"]: f["message"] for f in fake.sent}
    assert "1 member to follow up now and 1 to keep an eye on" in by_number["+254700000001"]
    assert "mwanachama 1 wa kufuatilia sasa na 1 wa kuangalia kwa karibu" in by_number["+254700000003"]
    assert all(f"{SITE}/o" in m for m in by_number.values())
    assert {d["status"] for d in done} == {"sent"}

    # a restarted worker, a minute later or an hour later: nothing is sent again
    again = FakeAT()
    assert texts.send_due(engine, SATURDAY.replace(hour=10), SMS, 9, again.client()) == []
    assert again.sent == []
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT status, sent_at IS NOT NULL AS stamped FROM app.meeting_texts "
                                 "WHERE meeting_date = '2026-12-06'")).all()
    assert [tuple(r) for r in rows] == [("sent", True), ("sent", True)]


def test_nothing_is_sent_on_other_days_or_before_the_hour(engine, only_the_demo_chama):
    fake = FakeAT()
    assert texts.send_due(engine, datetime(2026, 12, 4, 12, 0, tzinfo=EAT), SMS, 9, fake.client()) == []
    assert texts.send_due(engine, datetime(2027, 1, 2, 8, 0, tzinfo=EAT), SMS, 9, fake.client()) == []
    assert fake.sent == []


def test_a_refused_text_is_recorded_and_not_tried_again(engine, only_the_demo_chama):
    saturday_before_january = datetime(2027, 1, 2, 9, 0, tzinfo=EAT)     # the meeting is Sunday 3 Jan 2027
    refusing = FakeAT(refuse=True)
    done = texts.send_due(engine, saturday_before_january, SMS, 9, refusing.client())
    assert {d["status"] for d in done} == {"failed"} and len(refusing.sent) == 2
    with engine.connect() as conn:
        details = conn.execute(text("SELECT detail FROM app.meeting_texts WHERE meeting_date = '2027-01-03'")).scalars()
        assert all("refused the request (401)" in d for d in details)
    later = FakeAT()
    assert texts.send_due(engine, saturday_before_january.replace(hour=15), SMS, 9, later.client()) == []
    assert later.sent == []


def test_the_preview_sends_nothing_and_names_no_member(engine, only_the_demo_chama):
    lines = texts.preview(engine, date(2026, 11, 12))
    shown = "\n".join(lines)
    assert "next on Sun 06 Dec 2026" in shown and "to 2 officials with a phone" in shown
    assert "number ending 001" in shown and "Kiswahili" in shown
    assert "M-1" not in shown
