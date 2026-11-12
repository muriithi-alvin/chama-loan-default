# Milestone 3 report: MLOps

Branch `m3-mlops`, continued on `m4-web-interface` (the registry, drift and the
releases were built with the web interface that uses them). Decisions D-024,
D-025, D-030 to D-035, D-039, D-041 and D-043.

## 1. What Milestone 3 had to do

| Objective | Built in | Status |
| --- | --- | --- |
| **M3-1** Read ledger photos into the raw layout | `src/chama/extraction/` | Done |
| **M3-2** Serve the chosen model | the web worker and API | Done |
| **M3-3** A model registry | `src/chama/models/registry.py` | Done |
| **M3-4** Monitoring | `src/chama/models/drift.py` (Evidently) | Done |
| **M3-5** Containers | Docker Compose; the release image (`deploy/huggingface/`) | Partly: the image's first build runs at the first publish |

The tests for each are listed in [traceability.md](traceability.md).

## 2. Reading ledger photos (D-024, D-025, D-035, D-039)

**How.** A photo is checked (it must really be an image), turned upright, shrunk to
the model's largest useful size and re-saved without EXIF data such as location
(`images.py`). A vision model reads it into the raw layout: the same columns and the
same typing rules as the hand-typed Excel files (`schema.py`, `prompt.py`), values
exactly as written, so every later step reads its rows unchanged. The default model
is the open-weight Qwen 3.8 27B on Groq's free plan; the Claude API is a second,
paid provider for comparison (`extract-eval --provider claude`). When the free model
answers under other field names, the answer is put under the right names rather than
lost (D-035). A meeting photographed in two or three parts is read one part at a
time and joined (D-039).

**Nothing is trusted as it stands.** Checks flag the lines to look at (`checks.py`):
an amount that is not a number or a balance that grows by more than a month's
interest is a "check"; a line whose before - repaid (+ interest) is not after is a
"hint", because 13% of correct lines do not add up in the ledger itself. On the typed
pages taken as a perfect reading, 3.1% of lines get a "check". In the web interface
an official compares every row with the photo and matches every name before Accept
(OFF-10).

**Measured (12 Nov 2026).** `python -m chama.pipeline extract-eval` set out to read
10 pages spread evenly through the ledger (pages 1, 17, 34, 50, 67, 84, 100, 116, 133
and 149) with Groq's free model and compare each cell with the typed Excel files. Four
were read (pages 1, 17, 34 and 50, from 2014 to 2018) before it became clear that
Groq's free plan now refuses most pages (D-043, below):

| Measure | Result |
| --- | --- |
| Cells right | 67.5% (366 of 542) |
| Amounts right | 78.3% (217 of 277) |
| Names spelled exactly as typed | 22.6% (12 of 53) |
| Member lines found | 98.1% (51 of 52), none invented |
| Lines with at least one wrong cell | 90.2% (46 of 51) |
| Of those, flagged by the checks | 23.9% (11 of 46); 6.5% as a "check" |
| Right lines wrongly flagged "check" | 0 of 5 |
| Time per page | median 25 s, at most 43 s |
| Cost | US$0 (free plan) |

By page: 89.6% of cells right on page 1 (2014), 50.0% on page 17, 65.1% on page 34 and
61.0% on page 50.

Per-page counts are in `data/processed/extraction_eval_groq.csv`; every wrong cell,
with names, is in `data/interim/extraction_mismatches_groq.csv` (both on the laptop
only).

**What it means.** The model finds the lines reliably and gets most amounts right,
but on these older pages nine lines in ten have at least one cell to correct, and the
checks flag only a quarter of them. So a scan saves typing, not checking: the review,
where an official compares every row with the photo, is essential, as D-024 planned.
Some of the "wrong" cells are not reading errors: the typed files repeat the meeting
date on member lines where the model gives it once per page (39 of the 176 wrong
cells), and line numbers the model added where none were written. Names are mostly
near misses ("Jane Kenbo", "Grace Kanga"), which the review's name matching resolves by
suggesting the right member; a misread name never reaches the records unmatched.
Four pages from 2014 to 2018 are too few to generalise, and later pages, written more
neatly, may score higher (page 1, the neatest, scored 89.6%).

**The free plan's limit (D-043).** Groq now allows Qwen 3.8 27B about 1,000 answer
tokens a minute on its free plan, and a page's answer needs about 1,200 to 2,000, so
most pages are refused. Kibaba now says so at once and points the official to typing
the page in; reading photos as designed needs Groq's paid Developer plan (about
US$0.01 a page). The remaining six pages can be measured then with
`python -m chama.pipeline extract-eval` (pages already read are reused).

**Limits.** The free plan allows about 8,000 tokens a minute, so about one page a
minute; three photos of one meeting take about three minutes. Photos leave the
laptop for Groq, with the officials' permission (23 Oct 2026); Zero Data Retention is
on, so Groq keeps no copy.

## 3. Serving the model

The worker (`python -m chama.web.worker`) loads the model with the alias `champion`
from the MLflow registry once, at start, and tells the health check it is alive every
10 seconds. After an official accepts a page, the worker runs the pipeline on the
chama (ingest, names, names to codes, dbt models and tests) and then scores every
member with a running loan at the latest meeting (`web/services/scoring.py`). Each
score is saved in `app.risk_scores` as a band and its reasons, with the model's
registry version and a SHA-256 of its files; no raw score is stored or shown (G3).
Pages read the saved scores, so no model runs while a page loads (X9). The reasons
are SHAP values turned into plain sentences (`web/services/reasons.py`).

In the releases the model comes from an exported copy of the champion
(`MODEL_BUNDLE`), loaded only if its files match the checksum.

## 4. The model registry (D-030)

`python -m chama.pipeline register-model` registers the chosen run's model as a new
version of `chama-missed-repayment` and moves the alias `champion` to it. Version 1 is
the random forest of run fc6ae3fe (checksum `adcca567db3f…`), the model chosen in
Milestone 2 (D-023). Moving to a new model is: train, `register-model`, restart the
worker; rolling back is moving the alias to an earlier version. The member page shows
the version and checksum under "Technical details".

## 5. Monitoring data drift (D-031)

`python -m chama.pipeline drift --chama <id> --months 12` compares each of the model's
17 inputs in a chama's recent meetings with the rows the model learned from, using
Evidently's data drift preset (open source, telemetry off). The report goes to
`data/reports/drift/` and to the MLflow experiment `chama-missed-repayment-drift`. It
runs on demand, after a batch of new pages or before retraining. The first report
(30 Oct 2026) found 11 of 17 inputs drifted in chama B's last 12 months. Inputs that
only grow (months in the records, loans so far) always drift against earlier years;
the behaviour inputs (recent misses, repayment ratios) are the real signal, and their
drift matches missed repayments becoming more common in 2024 and 2025.

## 6. Containers and releases (D-033, D-034, D-041)

- **The laptop.** PostgreSQL 16 runs in Docker Compose (`docker compose up -d`, port
  5432). The rest runs in the `chama` conda environment.
- **The laptop release** (`serve-release`, D-034): its own database
  (`kibaba_release`), only the chamas marked `release: true`, its own pseudonym key and
  the exported model; ngrok gives it an HTTPS address.
- **The live release** (D-032, D-033, D-041): one container on a Hugging Face Docker
  Space (PRO, free CPU Basic hardware) runs PostgreSQL, the API, the worker and the
  pages (`deploy/huggingface/Dockerfile`, `start.sh`). The image clones the code from
  the private GitHub repository and fetches the bundle (Humble Sister's pages, names
  and the model) from a private dataset, with build secrets. A private storage bucket
  is mounted at `/data`: pages, photos and learned names are written there, and the
  database is saved there with `pg_dump` within two minutes of a change, after each
  records update and when the Space stops; the newest copy that restores whole is
  restored at start (`src/chama/release_storage.py`).

**Checked.** A dump of the release database restored with the Space's flags gave
every table the same rows (11 Nov 2026, PostgreSQL 16 in Docker). Every one of the 259
package versions pinned for the image (the versions the model was saved with) has a
Linux build for Python 3.11 on PyPI, and a `pip install --dry-run` in
`python:3.11-slim-bookworm` resolved 188 packages without a conflict before it was
stopped to free the laptop's memory (12 Nov 2026). The database
start-up inside the image and the first start were rehearsed on 2 Nov 2026. The image
as a whole is first built by Hugging Face at the first publish; its log is the test.

## 7. Tests

| File | Tests | What they check |
| --- | --- | --- |
| `test_extraction.py` | 55 | images, the layout schema, the checks, both extractors with fake services, repaired answers, a page too long for the free plan |
| `test_worker_parts.py` | 5 | a meeting in several photos, rate limits between photos, refusals |
| `test_registry.py` | 4 | registering, the alias, the checksum |
| `test_drift.py` | 4 | the drift comparison |
| `test_deploy.py` | 24 | the bundle, publishing (private dataset and bucket), the laptop release |
| `test_release_storage.py` | 8 | saving, keeping three copies, restoring the newest good one, refusing to start over copies it cannot restore, the bucket links |

All run on every push (GitHub Actions).

## 8. Commands

```powershell
python -m chama.pipeline extract <photos>            # read photos, print rows and flags
python -m chama.pipeline extract-eval                # accuracy on 10 pages (--pages 12,48 / --provider claude)
python -m chama.pipeline register-model              # the chosen run becomes the champion
python -m chama.pipeline drift --chama chama_b --months 12
python -m chama.pipeline deploy-bundle               # the release's data and model
python -m chama.pipeline deploy-publish              # the live Space (docs/deployment.md)
python -m chama.pipeline serve-release --address https://...   # the laptop release
```

## 9. Known limits

- A vision model can return a plausible but wrong number without warning; the
  review before Accept is part of the design, not an extra.
- Groq's free plan refuses most pages (D-043); its paid Developer plan reads them,
  about one a minute or faster. Typing a page needs no outside service.
- The live Space sleeps after 48 hours without visitors (two to three minutes to wake),
  and a change made in the last moments before a crash can be lost.
- Drift is checked on demand, not on a schedule (a chama adds one page a month).
- The model was trained on one chama; chama A's test (D-029) waits for its pages.
