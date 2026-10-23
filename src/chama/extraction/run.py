"""The extract and extract-eval commands.

Extractions are saved as JSON in data/interim/extractions/<provider>/ (names
included, so they stay on this computer like the rest of data/). extract-eval
reuses a saved extraction unless told to refresh, so a page is read once per
provider, and two providers can be compared on the same pages.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from chama import StepFailed
from chama.config import PROJECT_ROOT, shown_path
from chama.extraction.checks import check_page
from chama.extraction.evaluate import sample_photos, score_page, summary_row
from chama.extraction.extractor import Extraction, make_extractor, provider_settings
from chama.extraction.images import UnusableImage, prepare_image
from chama.extraction.schema import LedgerPage, page_to_frames

EXTRACTIONS_DIR = PROJECT_ROOT / "data" / "interim" / "extractions"


def read_photo(path: Path, settings: dict, extractor) -> Extraction:
    try:
        jpeg = prepare_image(path.read_bytes(), settings["max_image_edge_px"], settings["jpeg_quality"])
    except UnusableImage as e:
        raise StepFailed(f"{path.name}: {e}") from e
    return extractor.extract(jpeg)


def save_extraction(extraction: Extraction, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "model": extraction.model, "seconds": extraction.seconds,
        "input_tokens": extraction.input_tokens, "output_tokens": extraction.output_tokens,
        "page": extraction.page.model_dump(),
    }
    path.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")


def load_extraction(path: Path) -> Extraction:
    record = json.loads(path.read_text(encoding="utf-8"))
    page = LedgerPage.model_validate(record.pop("page"))
    return Extraction(page=page, **record)


def cost(extraction: Extraction, prices: dict) -> float:
    return (extraction.input_tokens * prices["input"] + extraction.output_tokens * prices["output"]) / 1e6


def print_page(photo: str, extraction: Extraction, prices: dict) -> None:
    page = extraction.page
    print(f"\n=== {photo}: {extraction.seconds}s, {extraction.input_tokens:,} in / "
          f"{extraction.output_tokens:,} out tokens, about US${cost(extraction, prices):.3f}, "
          f"{extraction.model}")
    if not page.is_ledger_page:
        print(f"Not read as a ledger page: {page.problem}")
        return
    if page.problem:
        print(f"Note: {page.problem}")
    frames = page_to_frames(page, photo)
    for table, df in frames.items():
        shown = df.drop(columns=["source_photo"]).dropna(axis=1, how="all")
        print(f"\n{table} ({len(df)} rows)")
        if not shown.empty:
            print(shown.fillna("").to_string(index=False))
    flags = check_page(frames)
    print(f"\n{len(flags)} flag(s)")
    for f in flags:
        print(f"  [{f.severity}] {f.table} row {f.row + 1}: {f.message}")


def run_extract(paths: list[Path], config: dict, provider: str | None) -> None:
    settings = config["extraction"]
    name, options = provider_settings(settings, provider)
    extractor = make_extractor(settings, name)
    for path in paths:
        extraction = read_photo(path, settings, extractor)
        out = EXTRACTIONS_DIR / name / f"{path.stem}.json"
        save_extraction(extraction, out)
        print_page(path.name, extraction, options["price_per_mtok"])
        print(f"\nSaved to {shown_path(out)}")


def answer_key(chama: dict) -> dict[str, pd.DataFrame]:
    from chama.ingestion.excel_loader import read_folder

    frames, _ = read_folder(PROJECT_ROOT / chama["raw_dir"], chama["id"])
    if not frames:
        raise StepFailed(f"No typed Excel files in {chama['raw_dir']} to compare with.")
    return frames


def run_evaluate(config: dict, chama_id: str, pages: list[int] | None, sample: int | None,
                 refresh: bool, provider: str | None = None) -> pd.DataFrame:
    settings = config["extraction"]
    name, options = provider_settings(settings, provider)
    chama = next((c for c in config["chamas"] if c["id"] == chama_id), None)
    if chama is None:
        raise StepFailed(f"No chama '{chama_id}' in config/pipeline.yaml.")
    key = answer_key(chama)
    typed_photos = sorted(set(key["statements"]["source_photo"].dropna()))
    if pages:
        photos = [p for p in typed_photos if any(p.endswith(f"_p{n:03d}.jpg") for n in pages)]
    else:
        photos = sample_photos(typed_photos, sample or settings["eval_sample"])
    if not photos:
        raise StepFailed("None of those pages has typed rows to compare with.")

    extractor = make_extractor(settings, name)
    photos_dir = PROJECT_ROOT / chama["photos_dir"]
    rows, mismatches = [], []
    for photo in photos:
        cached = EXTRACTIONS_DIR / name / chama_id / f"{Path(photo).stem}.json"
        if cached.exists() and not refresh:
            extraction = load_extraction(cached)
        else:
            extraction = read_photo(photos_dir / photo, settings, extractor)
            save_extraction(extraction, cached)
        got = page_to_frames(extraction.page, photo)
        expected = {t: df[df["source_photo"] == photo] for t, df in key.items()}
        score = score_page(photo, expected, got, check_page(got))
        rows.append(summary_row(score, {
            "seconds": extraction.seconds, "input_tokens": extraction.input_tokens,
            "output_tokens": extraction.output_tokens,
            "cost_usd": round(cost(extraction, options["price_per_mtok"]), 4),
            "is_ledger_page": extraction.page.is_ledger_page,
        }))
        mismatches += score.mismatches
        print(f"{photo}: {score.accuracy:.1%} of {sum(score.cells.values())} cells right, "
              f"{extraction.seconds}s")

    table = pd.DataFrame(rows).fillna(0)
    print(f"\nProvider: {name} ({extraction.model})")
    print_summary(table)
    out = PROJECT_ROOT / "data" / "processed" / f"extraction_eval_{name}.csv"
    table.to_csv(out, index=False)
    detail = PROJECT_ROOT / "data" / "interim" / f"extraction_mismatches_{name}.csv"
    pd.DataFrame(mismatches).to_csv(detail, index=False)
    print(f"\nPer-page results: {shown_path(out)}")
    print(f"Every wrong cell (names included, stays local): {shown_path(detail)}")
    return table


def _share(part: float, whole: float) -> str:
    return f"{part / whole:.1%} ({int(part)} of {int(whole)})" if whole else "n/a"


def print_summary(t: pd.DataFrame) -> None:
    s = t.sum(numeric_only=True)
    print(f"\n--- {len(t)} pages ---")
    print(f"Cells right:            {_share(s['cells_right'], s['cells'])}")
    print(f"  amounts:              {_share(s['amount_right'], s['amount_cells'])}")
    print(f"  names:                {_share(s['name_right'], s['name_cells'])}")
    print(f"Statement lines found:  {_share(s['statements_expected'] - s.get('statements_missing', 0), s['statements_expected'])}"
          f", {int(s.get('statements_extra', 0))} extra")
    wrong, right = s.get("wrong_rows", 0), s.get("right_rows", 0)
    print(f"Lines with a wrong cell: {_share(wrong, wrong + right)}")
    print(f"  of those, flagged 'check':      {_share(s.get('wrong_rows_checked', 0), wrong)}")
    print(f"  of those, flagged at all:       {_share(s.get('wrong_rows_flagged_any', 0), wrong)}")
    print(f"Right lines flagged 'check':      {_share(s.get('right_rows_checked', 0), right)}")
    print(f"Time per page: median {t['seconds'].median():.0f}s, max {t['seconds'].max():.0f}s")
    print(f"Cost: about US${s['cost_usd']:.2f} in total, US${t['cost_usd'].mean():.3f} per page")
