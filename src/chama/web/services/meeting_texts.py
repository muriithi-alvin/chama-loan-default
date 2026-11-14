"""The text before each meeting (D-045).

The day before a chama meets, each of its active officials with a phone gets
one text saying how many members to follow up, in the official's language
(D-044), with the site's address. The interface comes to the officials instead
of waiting to be opened.

    worker, once a minute -> send_due(): tomorrow is a meeting day and it is past
    MEETING_TEXT_HOUR in Nairobi -> one app.meeting_texts row per official, written
    before sending -> Africa's Talking (sms_hook.send_text)

- When: `meets` in config/pipeline.yaml, the chama's meeting day as the ledger
  shows it ("first sunday": Humble Sister's, on 69 of the 84 meetings with a
  written date). A chama without it gets no text.
- What: counts only, never a member's name or code. A text can be read on a
  locked phone and passes through Africa's Talking; who and why stay on the
  signed-in pages. If last month's page is not in the records yet, the text
  says where they stop, since the counts are then from that older page.
- Once: the row for (chama, meeting, official) is written before the text is
  sent, so a restarted worker, or two workers, never send it twice. A failed
  text is recorded with Africa's Talking's answer and not tried again.

Off unless MEETING_TEXTS=true, so a laptop test or a second copy of the
release texts nobody. Logs hold the last three digits of a number only.
"""
from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from chama import StepFailed
from chama.web.data import records, users
from chama.web.services import sms_hook
from chama.web.services.reasons import MONTHS_SW
from chama.web.settings import chamas, web_settings

log = logging.getLogger("chama.web")

NAIROBI = timezone(timedelta(hours=3), "EAT")     # Kenya keeps East Africa Time all year
ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "last": -1}
WEEKDAYS = {name.lower(): i for i, name in enumerate(calendar.day_name)}
WEEKDAYS_SW = ("Jumatatu", "Jumanne", "Jumatano", "Alhamisi", "Ijumaa", "Jumamosi", "Jumapili")


# ---- When ---------------------------------------------------------------------------


def parse_rule(rule: str) -> tuple[int, int]:
    """'first sunday' -> (1, 6); 'last saturday' -> (-1, 5)."""
    words = str(rule).strip().lower().split()
    if len(words) != 2 or words[0] not in ORDINALS or words[1] not in WEEKDAYS:
        raise StepFailed(f"meets: {rule!r} is not a meeting day such as 'first sunday' or 'last saturday' "
                         "(config/pipeline.yaml).")
    return ORDINALS[words[0]], WEEKDAYS[words[1]]


def meeting_in_month(year: int, month: int, rule: str) -> date:
    nth, weekday = parse_rule(rule)
    if nth > 0:
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (nth - 1))
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def next_meeting(rule: str, today: date) -> date:
    """The first meeting day on or after `today`."""
    this = meeting_in_month(today.year, today.month, rule)
    if this >= today:
        return this
    year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    return meeting_in_month(year, month, rule)


def due(rule: str, now: datetime, hour: int) -> date | None:
    """Tomorrow's date, if tomorrow is a meeting day and it is `hour` or later
    today in Nairobi; else None."""
    local = now.astimezone(NAIROBI)
    tomorrow = local.date() + timedelta(days=1)
    return tomorrow if next_meeting(rule, tomorrow) == tomorrow and local.hour >= hour else None


# ---- What -------------------------------------------------------------------------


@dataclass(frozen=True)
class Counts:
    high: int                  # Follow up now
    medium: int                # Keep an eye on
    records_to: date | None    # the month of the latest page in the records


def _people_en(n: int, rest: str, first: bool) -> str:
    return f"{n} {'member' if n == 1 else 'members'} {rest}" if first else f"{n} {rest}"


def _people_sw(n: int, rest: str, first: bool) -> str:
    return f"{'mwanachama 1' if n == 1 else f'wanachama {n}'} {rest}" if first else f"{n} {rest}"


def message(lang: str, meeting: date, counts: Counts, site: str | None) -> str:
    """The text, in English or Kiswahili. Counts only: no names (D-045)."""
    sw = lang == "sw"
    people = _people_sw if sw else _people_en
    parts = []
    if counts.high:
        parts.append(people(counts.high, "wa kufuatilia sasa" if sw else "to follow up now", True))
    if counts.medium:
        parts.append(people(counts.medium, "wa kuangalia kwa karibu" if sw else "to keep an eye on", not parts))
    if sw:
        when = f"{WEEKDAYS_SW[meeting.weekday()]} {meeting.day} {MONTHS_SW[meeting.month]}"
        if counts.records_to is None:
            body = f"Kibaba: kabla ya mkutano wa kesho ({when}), ongeza ukurasa wa mkutano uliopita ili kuona wa kufuatilia."
        elif parts:
            body = f"Kibaba: kabla ya mkutano wa kesho ({when}), {' na '.join(parts)}."
        else:
            body = f"Kibaba: kabla ya mkutano wa kesho ({when}), hakuna mwanachama wa kufuatilia."
        stale = f" Ukurasa wa mwisho ni wa {MONTHS_SW[counts.records_to.month]} {counts.records_to.year}." \
            if counts.records_to else ""
        link = f" Ona ni nani na kwa nini: {site}/o" if site else ""
    else:
        when = f"{calendar.day_name[meeting.weekday()]} {meeting.day} {calendar.month_abbr[meeting.month]}"
        if counts.records_to is None:
            body = f"Kibaba: before tomorrow's meeting ({when}), add the last meeting's page to see who to follow up."
        elif parts:
            body = f"Kibaba: before tomorrow's meeting ({when}), {' and '.join(parts)}."
        else:
            body = f"Kibaba: before tomorrow's meeting ({when}), no member needs following up."
        stale = f" The latest page is from {calendar.month_name[counts.records_to.month]} {counts.records_to.year}." \
            if counts.records_to else ""
        link = f" See who and why: {site}/o" if site else ""
    return body + (stale if is_stale(meeting, counts.records_to) else "") + link


def is_stale(meeting: date, records_to: date | None) -> bool:
    """The records stop before last month's meeting: its page is not in yet."""
    if records_to is None:
        return False
    return (meeting.year * 12 + meeting.month) - (records_to.year * 12 + records_to.month) >= 2


def counts_for(conn: Connection, chama_id: str) -> Counts:
    from chama.db import table_exists
    from chama.web.services.early_warning import current_scores

    scores, _ = current_scores(conn, chama_id)
    last = records.latest_meeting(conn, chama_id) if table_exists(conn, "analytics.meetings") else None
    return Counts(high=sum(1 for s in scores if s["band"] == "high"),
                  medium=sum(1 for s in scores if s["band"] == "medium"),
                  records_to=last["meeting_month"] if last else None)


def site_address() -> str | None:
    """The site's public https address (the first of WEB_ORIGINS), or None on a laptop test."""
    first = web_settings().allowed_origins[0] if web_settings().allowed_origins else ""
    return first if first.startswith("https://") else None


# ---- Once ---------------------------------------------------------------------------


def claim(conn: Connection, chama_id: str, meeting: date, user_id: int) -> bool:
    """Write the official's row for this meeting; False if it was already there."""
    return conn.execute(text(
        "INSERT INTO app.meeting_texts (chama_id, meeting_date, user_id) VALUES (:c, :d, :u) "
        "ON CONFLICT DO NOTHING RETURNING user_id"), {"c": chama_id, "d": meeting, "u": user_id}).first() is not None


def finish(conn: Connection, chama_id: str, meeting: date, user_id: int, status: str, detail: str) -> None:
    conn.execute(text(
        "UPDATE app.meeting_texts SET status = :s, detail = :x, sent_at = CASE WHEN :s = 'sent' THEN now() END "
        "WHERE chama_id = :c AND meeting_date = :d AND user_id = :u"),
        {"s": status, "x": detail[:500], "c": chama_id, "d": meeting, "u": user_id})


def send_due(engine: Engine, now: datetime, sms: sms_hook.SmsSettings, hour: int,
             client: httpx.Client | None = None) -> list[dict]:
    """Send every text due at `now`; what happened to each, for the log and tests."""
    done = []
    for chama_id, chama in chamas().items():
        if not chama.get("meets"):
            continue
        meeting = due(chama["meets"], now, hour)
        if meeting is None:
            continue
        with engine.begin() as conn:
            officials = users.officials_with_phones(conn, chama_id)
            if not officials:
                continue
            counts = counts_for(conn, chama_id)
            claimed = [o for o in officials if claim(conn, chama_id, meeting, o.id)]
        for official in claimed:
            words = message(official.language, meeting, counts, site_address())
            try:
                answer = sms_hook.send_text(sms, official.phone, words, client)
                status, detail = "sent", f"{answer.get('status', 'sent')}, {answer.get('cost', 'cost not given')}"
            except sms_hook.HookRefused as e:
                status, detail = "failed", e.message
            with engine.begin() as conn:
                finish(conn, chama_id, meeting, official.id, status, detail)
            log.info("meeting text for %s on %s: %s to the number ending %s (%s)", chama_id, meeting, status,
                     official.phone[-3:], detail)
            done.append({"chama_id": chama_id, "meeting": meeting, "user_id": official.id, "status": status,
                         "message": words})
    return done


def preview(engine: Engine, today: date) -> list[str]:
    """For `python -m chama.pipeline meeting-texts`: each chama's next meeting,
    when its text goes, to whom and what it says. Sends nothing."""
    settings = web_settings()
    lines = [(f"Meeting texts are {'on' if settings.meeting_texts else 'off'} (MEETING_TEXTS); they go at "
              f"{settings.meeting_text_hour}:00 Nairobi time the day before a meeting.")]
    for chama_id, chama in chamas().items():
        if not chama.get("meets"):
            lines.append(f"[{chama_id}] no meeting day: add `meets` (for example first sunday) to config/pipeline.yaml")
            continue
        meeting = next_meeting(chama["meets"], today + timedelta(days=1))
        with engine.begin() as conn:
            officials = users.officials_with_phones(conn, chama_id)
            counts = counts_for(conn, chama_id)
        lines.append(f"[{chama_id}] meets {chama['meets']}: next on {meeting:%a %d %b %Y}, text on "
                     f"{meeting - timedelta(days=1):%a %d %b} to {len(officials)} officials with a phone")
        for official in officials:
            lines.append(f"  {official.position or 'official'}, number ending {official.phone[-3:]}, "
                         f"{'Kiswahili' if official.language == 'sw' else 'English'}:")
            lines.append(f"    {message(official.language, meeting, counts, site_address())}")
    return lines
