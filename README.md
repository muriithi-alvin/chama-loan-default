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
│   ├── interim/       Temporary working files
│   └── processed/     Outputs ready for modelling
├── docs/              Documentation and PlantUML diagrams
├── notebooks/         Exploration only; final code lives in src/
├── sql/               Database schema (runs automatically in Docker)
├── src/chama/         The pipeline code
│   ├── ingestion/     Step 1: Excel -> raw tables
│   ├── anonymisation/ Step 2: names -> member codes
│   ├── validation/    Data quality checks
│   ├── cleaning/      Step 3: types, dates, amounts
│   └── features/      Indicators for modelling (M2)
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

Inside the `chama` conda environment, with Postgres running (`docker compose up -d`):

```powershell
# 1. Copy the raw Excel files into the raw schema, exactly as written
python -m chama.pipeline ingest

# 2. Suggest which name spellings are the same member.
#    Writes data/interim/aliases_<chama>.csv: check canonical_name, correct it, save.
python -m chama.pipeline suggest-aliases

#    Load the reviewed file into private.member_aliases
python -m chama.pipeline load-aliases

# 3. Copy raw to staging with member codes instead of names
python -m chama.pipeline anonymise
```

`python -m chama.pipeline --help` lists every step.
