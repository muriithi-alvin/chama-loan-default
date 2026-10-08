# Chama Loan Default Prediction

Predicting loan default in Kenyan Chama groups using behavioural and financial
indicators: a multi-source data engineering and MLOps framework.

The system gives Chama officials a **risk score, a risk category and an
explanation** for each loan request. It does **not** approve or reject loans;
the final decision stays with the officials.

## Project phases

| Milestone | Focus | Status |
| --- | --- | --- |
| M1 | Data pipeline: ingest, anonymise, validate, clean | In progress |
| M2 | Features and models (Logistic Regression, Random Forest, XGBoost, SHAP) | Planned |
| M3 | MLOps: MLflow tracking, monitoring with Evidently, Docker | Planned |
| M4 | Dashboard for officials (Streamlit) | Planned |
| M5 | Report and defence | Planned |

## Folder structure

```
chama-loan-default/
├── config/            Pipeline settings (pipeline.yaml)
├── data/              PRIVATE - never committed (see .gitignore)
│   ├── photos/        Ledger photos
│   ├── raw/           Excel extracted from the photos, as recorded
│   ├── interim/       Working files, incl. the name review files (keep these)
│   └── processed/     Outputs ready for modelling
├── docs/              Documentation and PlantUML diagrams
├── notebooks/         Exploration only; final code lives in src/
├── sql/               Database schema (runs automatically in Docker)
├── src/chama/         The pipeline code
│   ├── ingestion/     Step 1: Excel -> raw tables
│   ├── anonymisation/ Steps 2-3: name matching, names -> member codes
│   ├── cleaning/      Step 4: runs the dbt project in transform/
│   ├── validation/    Data quality report
│   └── features/      Indicators for modelling (M2)
├── transform/         dbt project: staging -> analytics (clean tables, loans, checks)
└── tests/             Automated tests (pytest)
```

## Data protection

- Raw data holds real member names, so `data/` and `.env` are never committed.
- Names are replaced with codes (e.g. `M-3f9a1c2b`) inside the pipeline using
  HMAC-SHA256 and a secret key. Everything after the anonymisation step,
  including models and the dashboard, sees only codes.
- The name-to-code link lives in the restricted `private` database schema.
- Data is used with the written permission of each Chama's officials.

## Setup (Windows, PowerShell)

```powershell
# 1. Create and activate the conda environment (Miniconda)
conda create -n chama python=3.11 -y
conda activate chama

# 2. Install the project and dev tools
pip install -e ".[dev]"

# 3. Create your .env from the example and fill it in
Copy-Item .env.example .env

# 4. Start PostgreSQL (needs Docker Desktop)
docker compose up -d

# 5. Run the tests
pytest
```

## Raw data layout

Ledger photos and the Excel files extracted from them stay on this computer only:

```
data/photos/chama_b/chama_b_p001.jpg        pages numbered in ledger order (+ photo_manifest.csv)
data/raw/chama_b/2014.xlsx                  one Excel file per Chama per year
```

Each raw file has four sheets that mirror the ledger: **Statements**, **Meetings**,
**NewLoans** and **Attendance**. Create an empty template with
`python scripts/make_raw_template.py`.

## Documentation

- [CHANGELOG.md](CHANGELOG.md) — every change, newest first
- [docs/decisions.md](docs/decisions.md) — design decisions and why
- [docs/git_workflow.md](docs/git_workflow.md) — branches and how to push and merge
- [docs/data_dictionary.md](docs/data_dictionary.md) — raw sheets, columns and extraction rules
- [docs/extraction_log.md](docs/extraction_log.md) — what was extracted each year and what to check
- [docs/diagrams/](docs/diagrams/) — PlantUML diagrams

## Running the pipeline

Inside the `chama` conda environment, with Postgres running (`docker compose up -d`),
one command runs every step in order:

```powershell
python -m chama.pipeline all
```

| Step | What it does | Run on its own |
| --- | --- | --- |
| 0 | Creates the schemas and private tables if missing (`sql/*.sql`) | |
| 1 | Copies the raw Excel files into the `raw` schema, exactly as written | `ingest` |
| 2 | Checks every name spelling has a reviewed alias; restores reviewed names into an empty database | `suggest-aliases`, `load-aliases` |
| 3 | Copies raw to `staging` with member codes instead of names | `anonymise` |
| 4 | Builds the clean tables and loans with dbt, runs the data checks, prints the quality report (saved to `data/processed/quality_report.csv`) | `clean` |

**When new names appear** (for example after adding a new year), step 2 writes
`data/interim/aliases_<chama>.csv` and stops, because matching names needs a
person:

```powershell
# 1. Open data/interim/aliases_<chama>.csv in Excel; check canonical_name, correct it, save
# 2. Load the reviewed names; every row in the file is then marked "reviewed"
python -m chama.pipeline load-aliases
# 3. Carry on
python -m chama.pipeline all
```

Each step can also be run on its own (`python -m chama.pipeline <step>`), and
`python -m chama.pipeline --help` lists them. Any other dbt command runs
through the pipeline so it picks up `.env`, for example
`python -m chama.pipeline dbt test` or `python -m chama.pipeline dbt run --select loans`.

### Starting again from an empty database

The review files in `data/interim/` are the record of the name review, so the
database can always be rebuilt from the Excel files and those files:

```powershell
# Deletes ALL database data (the Docker volume). Excel files, photos and
# review files are not touched.
docker compose down -v
docker compose up -d
python -m chama.pipeline all
```
