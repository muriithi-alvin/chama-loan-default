# Changelog

All notable changes to this project are recorded here, newest first.
Each entry links to its issue or pull request where one exists.
Reasons behind the bigger choices are in [docs/decisions.md](docs/decisions.md).

## [Unreleased] — branch `feature/5-raw-format-and-loader`

### Changed
- **Raw Excel layout now mirrors the ledger** (decision D-006). The sheets are
  `Statements` (one row per member per meeting), `Meetings` (one row per page),
  `NewLoans` (one row per loan given) and `Attendance`. They replace the earlier
  `Loans`, `Repayments`, `Contributions` and `Notes` sheets, which did not match
  how the Chama records its data. Defined in `src/chama/ingestion/raw_format.py`;
  every column is described in [docs/data_dictionary.md](docs/data_dictionary.md).
- **One Excel file per Chama per year** (decision D-004). `config/pipeline.yaml`
  now gives each Chama a folder (`raw_dir`) instead of one file; the loader reads
  every `.xlsx` in that folder in name order and combines them.
- Chama B's records start in **2014** (previously noted as 2015).
- README setup uses **conda** (Miniconda) instead of `venv`.
- **Simpler git workflow** (decision D-007): one branch per milestone
  (`m1-data-pipeline` … `m5-report`) plus `housekeeping`, replacing one branch
  per issue. Pull request template now has an *Issues* section, a title
  convention and a CHANGELOG check. Steps in [docs/git_workflow.md](docs/git_workflow.md).
- Loader tests rewritten for the new layout (15 tests).

### Added
- `read_folder()` and `raw_files()` in the loader; skips Excel's `~$` temporary
  files and the empty template.
- Ledger photos for Chama B: 149 pages (early 2014 to April 2026) renamed in the
  order they were taken to `chama_b_p001.jpg` … `chama_b_p149.jpg`, with
  `data/photos/chama_b/photo_manifest.csv` linking each new name to its original
  WhatsApp file name (decision D-005). Photos stay local and are never committed.
- `CHANGELOG.md`, `docs/decisions.md`, `docs/data_dictionary.md`,
  `docs/extraction_log.md`.
- **2014 extracted** from photos p001–p012 into `data/raw/chama_b/2014.xlsx`
  (local only): 12 meetings, 167 statement rows, 22 new loans; 30 rows flagged
  unclear for checking against the paper. Details in the extraction log.

### Fixed
- Removed a duplicated `config = load_config()` line in `pipeline.py` and a stray
  blank line in `raw_format.py` (accidental edits).

## 2026-09-26 — Raw format, template and loader checks (PR for issues #5, #6)
### Added
- `raw_format.py`: single definition of sheets and columns, with tracking
  columns `source_photo` and `unclear` on every sheet.
- `template.py` and `scripts/make_raw_template.py`: generate an empty raw
  template with a README sheet.
- Loader reports missing and unexpected columns per sheet before loading, keeps
  all values as text and records each row's Excel row number.
### Note
- The commit message says `(#N, #M)` by mistake; the pull request description
  carries the correct issue links.

## 2026-09-26 — GitHub templates and M1 backlog (issue #3, PR #4)
### Added
- Pull request template with *Problem*, *Remedy* and *How I checked it* sections.
- Bug template with a *Remedy* section to fill in when closing.
- `scripts/create_m1_issues.ps1`: creates the nine Milestone 1 issues.
- Labels (`data-pipeline`, `modelling`, `mlops`, `dashboard`, `docs`, `chore`)
  and milestones M1–M5 on GitHub.

## 2026-09-26 — Safer database container (issue #1, PR #2)
### Changed
- `docker-compose.yml` passes only the database settings to PostgreSQL instead of
  the whole `.env` (which holds the pseudonym key), makes the port configurable
  and adds a health check.

## 2026-09-25 — Initial project structure
### Added
- Folder layout, `pyproject.toml`, `.gitignore` (blocks photos, Excel, CSV and
  `.env`), `.gitattributes`, `.env.example`, Docker Compose PostgreSQL 16.
- Database schemas `raw`, `private`, `staging`, `analytics` (`sql/01_schemas.sql`).
- Name-to-code step (`pseudonymise.py`) using HMAC-SHA256, with 7 tests.
- Excel loader, pipeline runner, PlantUML data-flow diagram, issue template.
