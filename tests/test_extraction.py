"""Extraction tests with made-up rows and a fake API client. No real Chama data
is used and no API call is made."""
import io
import json
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image

from chama import StepFailed
from chama.extraction.checks import check_page, interest_parts, parse_amount
from chama.extraction.evaluate import align, same_value, sample_photos, score_page
from chama.extraction.extractor import (
    ClaudeExtractor,
    ExtractionFailed,
    OpenAICompatibleExtractor,
    make_extractor,
)
from chama.extraction.images import UnusableImage, prepare_image
from chama.extraction.schema import PAGE_TABLES, LedgerPage, page_schema, page_to_frames
from chama.ingestion.raw_format import SHEETS, expected_columns

SETTINGS = {"model": "test-model", "effort": "medium", "max_tokens": 1000}


def statement(name, before="", repaid="", interest="", after="", unclear=False, **other):
    values = {c: "" for c in SHEETS["statements"][1]}
    values.update(member_name=name, loan_before=before, repayment=repaid, interest=interest,
                  loan_after=after, unclear=unclear, **other)
    return values


def page(statements, new_loans=(), is_ledger_page=True, **meeting):
    blank_meeting = {c: "" for c in SHEETS["meetings"][1]} | {"unclear": False} | meeting
    return LedgerPage.model_validate({
        "is_ledger_page": is_ledger_page, "problem": "", "meeting": blank_meeting,
        "statements": list(statements), "new_loans": list(new_loans),
    })


# --- schema ---------------------------------------------------------------

def test_row_models_have_the_raw_columns_plus_unclear():
    fields = LedgerPage.model_json_schema()["$defs"]
    for table in PAGE_TABLES:
        sheet = SHEETS[table][0]
        assert set(fields[f"{sheet}Row"]["properties"]) == set(SHEETS[table][1]) | {"unclear"}


def test_page_becomes_raw_layout_frames():
    frames = page_to_frames(page([statement("Test Member A", "23,475", "5000", "2%", "18,815",
                                            unclear=True, remarks="could be 18,315")],
                                 meeting_date="8/6/14"), "chama_t_p001.jpg")
    for table in PAGE_TABLES:
        assert list(frames[table].columns) == expected_columns(table)
    row = frames["statements"].iloc[0]
    assert row["loan_before"] == "23,475"  # exactly as written
    assert row["unclear"] == "Y" and row["source_photo"] == "chama_t_p001.jpg"
    assert row["due"] is None  # blank cells are empty, as in the typed files
    assert frames["meetings"].iloc[0]["unclear"] is None


# --- checks ---------------------------------------------------------------

@pytest.mark.parametrize("written, value", [
    ("40,000", 40000), ("46 000", 46000), ("59,000/=", 59000), ("92,400/-", 92400),
    ("Ksh. 43,571", 43571), ("300k", 300000), ("5500 + 776", 6276), ("-", 0), ("nil", 0),
    ("Cleared", 0), ("SF", None), ("", None), (None, None), (float("nan"), None),
])
def test_parse_amount_reads_like_the_dbt_macro(written, value):
    assert parse_amount(written) == value


def test_interest_is_a_rate_with_percent_or_up_to_20_otherwise_an_amount():
    assert interest_parts("2%") == (2, 0)
    assert interest_parts("1.5") == (1.5, 0)
    assert interest_parts("2,100") == (0, 2100)
    assert interest_parts("") == (0, 0)


def rules(frames):
    return {(f.table, f.row, f.rule) for f in check_page(frames)}


def test_a_line_that_adds_up_is_not_flagged():
    frames = page_to_frames(page([
        statement("A", "23,475", "5000", "", "18,475"),        # before - repaid
        statement("B", "100,000", "10,000", "2,000", "92,000"),  # plus an interest amount
        statement("C", "40000", "5000", "2%", "35800"),          # rate on the balance before
        statement("D", "12,000", "12,000", "", "Cleared"),
    ]), "p.jpg")
    assert rules(frames) == set()


def test_flags_point_at_the_lines_to_check():
    frames = page_to_frames(page([
        statement("Jump", "20,000", "", "", "35,000"),
        statement("Misread", "20,000", "5,000", "", "16,000"),
        statement("Letters", "2O,000", "5,000", "", "15,000"),
        statement("Unsure", "10,000", "1,000", "", "9,000", unclear=True, remarks="could be 9,600"),
    ], new_loans=[{"loan_date": "", "member_name": "A", "amount": "3O,000", "loan_type": "",
                   "remarks": "", "unclear": False}]), "p.jpg")
    flags = check_page(frames)
    assert rules(frames) == {
        ("statements", 0, "balance_jump"),
        ("statements", 1, "does_not_add_up"),
        ("statements", 2, "unreadable_amount"),
        ("statements", 3, "marked_unclear"),
        ("new_loans", 0, "unreadable_amount"),
    }
    assert {f.rule: f.severity for f in flags}["does_not_add_up"] == "hint"
    assert "could be 9,600" in next(f.message for f in flags if f.rule == "marked_unclear")


# --- images ---------------------------------------------------------------

def image_bytes(size, fmt="PNG", exif=None):
    out = io.BytesIO()
    Image.new("RGB", size, "white").save(out, format=fmt, **({"exif": exif} if exif else {}))
    return out.getvalue()


def test_large_photo_is_shrunk_to_a_jpeg_without_exif():
    exif = Image.Exif()
    exif[0x0110] = "Test phone"  # camera model
    jpeg = prepare_image(image_bytes((4000, 3000), "JPEG", exif.tobytes()), max_edge=2576)
    with Image.open(io.BytesIO(jpeg)) as out:
        assert out.format == "JPEG" and max(out.size) == 2576
        assert not out.getexif()


def test_small_photo_is_not_enlarged():
    with Image.open(io.BytesIO(prepare_image(image_bytes((1600, 1200)), max_edge=2576))) as out:
        assert out.size == (1600, 1200)


def test_photo_is_turned_upright_from_its_exif_orientation():
    exif = Image.Exif()
    exif[0x0112] = 6  # taken sideways: rotate 90 degrees
    jpeg = prepare_image(image_bytes((1600, 1200), "JPEG", exif.tobytes()), max_edge=2576)
    with Image.open(io.BytesIO(jpeg)) as out:
        assert out.size == (1200, 1600)


@pytest.mark.parametrize("data", [b"not an image at all", b"%PDF-1.7 fake", b""])
def test_files_that_are_not_images_are_refused(data):
    with pytest.raises(UnusableImage):
        prepare_image(data, max_edge=2576)


def test_gif_is_refused_with_the_accepted_types():
    with pytest.raises(UnusableImage, match="JPEG, PNG or WebP"):
        prepare_image(image_bytes((10, 10), "GIF"), max_edge=2576)


# --- extractor --------------------------------------------------------------

class FakeMessages:
    def __init__(self, response):
        self.response, self.calls = response, []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def fake_client(stop_reason="end_turn", parsed=None):
    response = SimpleNamespace(
        stop_reason=stop_reason, parsed_output=parsed, model="test-model",
        usage=SimpleNamespace(input_tokens=1500, output_tokens=900),
    )
    return SimpleNamespace(messages=FakeMessages(response))


def test_extractor_sends_the_photo_and_returns_the_page():
    client = fake_client(parsed=page([statement("A", "1,000", "", "", "1,000")]))
    extraction = ClaudeExtractor(SETTINGS, client).extract(b"jpeg bytes")
    call = client.messages.calls[0]
    assert call["output_format"] is LedgerPage
    assert call["messages"][0]["content"][0]["source"]["media_type"] == "image/jpeg"
    assert call["extra_body"] == {"fallbacks": "default"}
    assert extraction.page.statements[0].member_name == "A"
    assert (extraction.input_tokens, extraction.output_tokens) == (1500, 900)


@pytest.mark.parametrize("stop_reason, parsed, message", [
    ("refusal", None, "declined"),
    ("max_tokens", None, "cut off"),
    ("end_turn", None, "no ledger page"),
])
def test_extractor_explains_an_unusable_answer(stop_reason, parsed, message):
    with pytest.raises(ExtractionFailed, match=message):
        ClaudeExtractor(SETTINGS, fake_client(stop_reason, parsed)).extract(b"jpeg bytes")


GROQ = {"base_url": "https://api.example.test/openai/v1", "api_key_env": "TEST_EXTRACTION_KEY",
        "model": "open-model", "max_tokens": 3500, "request_options": {"reasoning_effort": "none"}}


def openai_client(status=200, content=None, finish_reason="stop", headers=None, sent=None):
    """An httpx client whose requests never leave the test: answers like an
    OpenAI-style chat completions API."""
    def handler(request):
        if sent is not None:
            sent.append(request)
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "limit reached"}},
                                  headers=headers or {})
        return httpx.Response(200, json={
            "model": "open-model",
            "choices": [{"finish_reason": finish_reason, "message": {"content": content}}],
            "usage": {"prompt_tokens": 4300, "completion_tokens": 1600},
        })
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openai_style_extractor_sends_the_photo_and_layout(monkeypatch):
    monkeypatch.setenv("TEST_EXTRACTION_KEY", "secret")
    sent = []
    content = page([statement("A", "1,000", "", "", "1,000")]).model_dump_json()
    extraction = OpenAICompatibleExtractor(GROQ, openai_client(content=content, sent=sent)).extract(b"jpeg")
    request = sent[0]
    body = json.loads(request.content)
    assert str(request.url) == "https://api.example.test/openai/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer secret"
    assert body["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert body["response_format"]["json_schema"]["schema"] == page_schema()
    assert body["reasoning_effort"] == "none" and body["max_tokens"] == 3500
    assert extraction.page.statements[0].member_name == "A"
    assert (extraction.input_tokens, extraction.output_tokens) == (4300, 1600)


@pytest.mark.parametrize("client_args, message", [
    ({"status": 401}, "TEST_EXTRACTION_KEY in .env"),
    ({"status": 429, "headers": {"retry-after": "12"}}, "12 s"),
    ({"status": 413}, "too large"),
    ({"status": 503}, "unavailable"),
    ({"content": '{"is_ledger_page": tru', "finish_reason": "length"}, "cut off"),
    ({"content": "not json"}, "could not be read"),
])
def test_openai_style_extractor_explains_failures(monkeypatch, client_args, message):
    monkeypatch.setenv("TEST_EXTRACTION_KEY", "secret")
    with pytest.raises(ExtractionFailed, match=message):
        OpenAICompatibleExtractor(GROQ, openai_client(**client_args)).extract(b"jpeg")


def test_a_missing_key_is_named(monkeypatch):
    monkeypatch.delenv("TEST_EXTRACTION_KEY", raising=False)
    with pytest.raises(ExtractionFailed, match="TEST_EXTRACTION_KEY is missing"):
        OpenAICompatibleExtractor(GROQ, openai_client()).extract(b"jpeg")


def test_layout_schema_is_written_out_in_full_with_closed_objects():
    schema = page_schema()
    assert "$ref" not in json.dumps(schema) and "$defs" not in schema
    row = schema["properties"]["statements"]["items"]
    assert schema["additionalProperties"] is False and row["additionalProperties"] is False
    assert set(row["required"]) == set(SHEETS["statements"][1]) | {"unclear"}


def test_provider_is_chosen_from_the_settings():
    settings = {"provider": "groq", "providers": {"groq": {"kind": "openai_compatible", **GROQ},
                                                  "claude": {"kind": "claude", **SETTINGS}}}
    assert isinstance(make_extractor(settings), OpenAICompatibleExtractor)
    assert isinstance(make_extractor(settings, "claude"), ClaudeExtractor)
    with pytest.raises(StepFailed, match="known: groq, claude"):
        make_extractor(settings, "other")


# --- evaluation -------------------------------------------------------------

def test_same_value_ignores_spacing_case_commas_and_name_dots():
    assert same_value("loan_before", "40,000", "40000")
    assert same_value("repayment", "5500 + 776", "6,276")
    assert same_value("member_name", "Test M. Member", "test m member")
    assert same_value("due", None, "")
    assert not same_value("loan_after", "35,000", "36,000")
    assert not same_value("due", "Jan 2015", "Jun 2015")


def test_align_pairs_rows_and_finds_missing_and_extra_ones():
    pairs = align(["a", "b", "c", "d"], ["a", "c", "x", "d", "e"])
    assert (0, 0) in pairs and (2, 1) in pairs and (3, 3) in pairs
    assert (1, None) in pairs  # b was missed
    assert (None, 2) in pairs and (None, 4) in pairs  # x and e were added


def test_score_page_counts_right_cells_and_flag_catches():
    typed = page_to_frames(page([
        statement("A", "20,000", "5,000", "", "15,000"),
        statement("B", "10,000", "1,000", "", "9,000"),
        statement("C", "8,000", "", "", "8,000"),
    ]), "p.jpg")
    got = page_to_frames(page([
        statement("A", "20000", "5,000", "", "15,000"),
        statement("B", "10,000", "1,000", "", "6,000"),  # misread, does not add up
    ]), "p.jpg")
    score = score_page("p.jpg", typed, got, check_page(got))
    assert score.rows["statements_missing"] == 1
    assert score.cells["loan_after"] == 2 and score.right["loan_after"] == 1
    assert score.flags["wrong_rows"] == 1 and score.flags["wrong_rows_flagged_any"] == 1
    assert score.flags["right_rows"] == 1 and score.flags["right_rows_flagged_any"] == 0
    assert [m["column"] for m in score.mismatches] == ["loan_after"]


def test_sample_is_spread_through_the_ledger():
    photos = [f"p{n:03d}.jpg" for n in range(1, 101)]
    sample = sample_photos(photos, 5)
    assert sample[0] == "p001.jpg" and sample[-1] == "p100.jpg" and len(sample) == 5
    assert sample_photos(photos[:3], 10) == photos[:3]
