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
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install the project and dev tools
pip install -e ".[dev]"

# 3. Create your .env from the example and fill it in
Copy-Item .env.example .env

# 4. Start PostgreSQL (needs Docker Desktop)
docker compose up -d

# 5. Run the tests
pytest
```

## Running the pipeline

```powershell
python -m chama.pipeline ingest
```
