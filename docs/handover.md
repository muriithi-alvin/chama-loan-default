# Kibaba handover

Everything needed to run, publish and look after Kibaba without help: what it is,
where each part lives, every setting, the everyday tasks, and what is still open.
Written on 12 Nov 2026. The other documents go deeper; each section says which.

## 1. What Kibaba is

Kibaba tells a chama's officials which members to follow up before the next
meeting, and why. Officials photograph or type each month's ledger page; Kibaba
reads it, the official checks every row, and after Accept the records are updated
and each member with a loan gets a colour (Follow up now, Keep an eye on, Less likely
to miss) with the main reasons. Members see only their own loans and contributions.
It never approves or refuses a loan (G2).

Humble Sister (chama B in the code) is the first chama to use it, under an MOU that
allows its real names on screen and its records on Hugging Face (D-036, D-041). Its
interface copy (`chama_demo`) holds the ledger to page 128 (July 2024); pages 129 to
149 are for the officials to enter. Chama A is still deciding and is only a test
chama for the model (D-029).

## 2. How it fits together

```
Officials' and members' browsers
        |  HTTPS
  Next.js pages (frontend/)  -- forwards /api/* -->  FastAPI API (src/chama/web/)
                                                        |  sign-in checks
                                                        +--> Supabase Auth (passwords, Google, texted codes)
                                                        |       '--> Send SMS hook --> Kibaba --> Africa's Talking
                                                        |
                                    PostgreSQL  <-------+-------  worker (src/chama/web/worker.py)
                                (records, scores,                 reads photos with Groq,
                                 accounts, jobs)                  runs the pipeline after Accept,
                                                                  scores with the registered model
```

The pipeline (`python -m chama.pipeline ...`) is the same code the worker runs:
Excel or accepted pages -> `raw` -> names to codes -> `staging` -> dbt -> `analytics`
-> scores in `app.risk_scores`. See [decisions.md](decisions.md) D-026, D-027.

## 3. Where everything lives

| What | Where |
| --- | --- |
| Code | GitHub, private: `muriithi-alvin/chama-loan-default`. Work goes on `m4-web-interface`, merged into `main` ([git_workflow.md](git_workflow.md)) |
| Ledger photos, typed Excel, names | `data/` on the project laptop only, never committed |
| Laptop database | Docker PostgreSQL (`docker compose up -d`): `chama` (all chamas, for the pipeline and training), `kibaba_release` (the laptop release) |
| Models | MLflow runs and registry, in `DRIVE_DIR/mlruns` (Google Drive) or `./mlruns`; the champion is version 1 of `chama-missed-repayment` (D-030) |
| Sign-in | Supabase project (the one in `SUPABASE_URL`): users, Google and Phone providers, test numbers, Send SMS hook |
| Google sign-in | Google Cloud project `Kibaba`: OAuth client (its ID and secret are only in Supabase) |
| Texted codes | Africa's Talking app (username and API key in `.env`); Twilio only to satisfy Supabase's form |
| Reading photos | Groq (key `GROQ_API_KEY`, Zero Data Retention on). Its free plan refuses most pages since Nov 2026; the paid Developer plan (about US$0.01 a page) reads them (D-043) |
| Live site | Hugging Face, account `alvin-muriithi`, PRO: Space `kibaba`, private dataset `kibaba-data`, private bucket `kibaba-storage` |
| Laptop release over the internet | ngrok (free), started by hand |

## 4. Settings (`.env`)

Copy `.env.example` to `.env`; it explains each line. Never commit `.env`.

| Setting | For | Where it comes from |
| --- | --- | --- |
| `POSTGRES_*` | the laptop database | your choice; Docker uses them |
| `PSEUDONYM_KEY` | names to codes on the laptop | made once; back it up: losing it changes every code |
| `DRIVE_DIR` | training data and MLflow on Google Drive | Drive for desktop's folder |
| `GROQ_API_KEY` | reading photos | console.groq.com/keys |
| `ANTHROPIC_API_KEY` | optional comparison reader | platform.claude.com |
| `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` | sign-in | Supabase > Project Settings > API Keys (never the secret key) |
| `TWO_STEP_FOR_OFFICIALS` | officials' texted code; leave `true` except for a laptop test | — |
| `PHONE_COUNTRY_CODE` | how 07... numbers are read | `254` |
| `SMS_HOOK_SECRET` | checking Supabase's texting requests | Supabase > Authentication > Hooks |
| `AFRICASTALKING_USERNAME`, `_API_KEY`, `_SENDER_ID` | sending texts | Africa's Talking dashboard (`sandbox` to test) |
| `HF_TOKEN`, `HF_BUILD_TOKEN` | publishing; the Space's build reading the dataset | Hugging Face > Settings > Access Tokens (write; read) |
| `GITHUB_READ_TOKEN` | the Space's build cloning the code | GitHub fine-grained token, this repository, Contents read-only |
| `CLOUD_PSEUDONYM_KEY` | names to codes in the releases | made once, different from `PSEUDONYM_KEY` |
| `RELEASE_OFFICIAL_EMAIL`, `RELEASE_OFFICIAL_PHONE` | the releases' treasurer, Alvin Muriithi | your Gmail and phone |
| `RELEASE_MEMBER_EMAIL`, `RELEASE_MEMBER_PHONE` | the releases' member, Alvin Wise | another email; a phone (optional) |

## 5. Everyday tasks

All commands run in PowerShell, in the project folder, after `conda activate chama`.

**See the site on the laptop.** Start Docker Desktop, then:

```powershell
python -m chama.pipeline serve-release --address https://preview.localhost
```

and open http://localhost:3000. Add `--fresh` to start again from page 128 (this
deletes pages added there and remakes the accounts from `.env`). For the internet,
run ngrok first (`.\ngrok http 127.0.0.1:3000`) and give its address instead
([deployment.md](deployment.md)). Ctrl+C stops it.

**Add a person.** Create their sign-in in Supabase (Authentication > Users > Add
user, Auto Confirm), then:

```powershell
# for the live Space, run these in the Space (Dev Mode) or set them up before publishing
python -m chama.pipeline web-user codes --chama chama_demo          # member codes and names
python -m chama.pipeline web-user add --email <email> --phone 07XXXXXXXX --role member --chama chama_demo --member M-xxxxxxxx
python -m chama.pipeline web-user add --email <email> --phone 07XXXXXXXX --role official --chama chama_demo --name "<name>" --position chair
python -m chama.pipeline web-user list
python -m chama.pipeline web-user deactivate --email <email or phone>
```

To work on the release's database instead of the laptop's main one, first run
`$env:POSTGRES_DB = "kibaba_release"` in that window (close the window afterwards).

**A month's page (officials, in the site).** Scan a page (1 to 3 photos of one
meeting) or Type a page (the members and carried balances are filled in). Each step
opens the next: reading, check the rows, Accept, the records update, the results.
Pages go in date order.

**Rebuild Humble Sister's copy** (after changing its settings in
`config/pipeline.yaml` or chama B's files): `demo-chama`, then `deploy-bundle`, then
start the laptop release with `--fresh`. The earlier copy is moved to
`data/interim/replaced/`.

**Model work.** `python -m chama.pipeline all` then `export` (codes-only tables to
Drive), train in Colab or `python -m chama.pipeline train`, then `register-model` to
make a run the champion, then restart the worker. `python -m chama.pipeline drift`
compares recent meetings with the training data (D-031).
[milestone_2_report.md](milestone_2_report.md), [milestone_3_report.md](milestone_3_report.md).

**Check health.** `https://<site>/api/health` shows the database, worker, model and,
on the live Space, where pages are kept ("kept in the storage bucket").

## 6. The live site on Hugging Face

Full steps: [deployment.md](deployment.md), last section. In short: PRO (US$9 a
month), check `.env`, merge into `main`, then `deploy-bundle` and `deploy-publish`;
watch the Space's Logs; add the Space's Google callback and Send SMS hook in Supabase.
After new code is on `main`: `deploy-publish --rebuild`.

What it keeps: pages, photos and learned names are written straight into the private
bucket, and the database is saved there within two minutes of any change, after each
records update and when the Space stops; the newest good copy is restored at start
(D-041). If copies exist but none restores, the Space refuses to start rather than
save over them: read the Logs. To start the live site again from page 128, delete the
bucket's `kibaba` folder and restart the Space (this deletes every page added there).

The free CPU Basic hardware sleeps after 48 hours without visitors; the next visitor
waits two or three minutes.

## 7. Sign-in

[web_setup.md](web_setup.md), steps 1 to 8: passwords, Google (step 6), phone codes and
test numbers (step 7), real texts through Africa's Talking (step 8). Officials sign in
with Google or a password and then type a texted code; members may use a phone code
alone (D-037). Test numbers in Supabase accept a fixed code and send nothing: the
cheapest way to show the sign-in.

## 8. When something goes wrong

| What you see | What to do |
| --- | --- |
| Docker does not answer, or a command waits for minutes | Docker Desktop has frozen (low memory). Restart the laptop, close other apps |
| "Port 3000 (or 8000) is in use" | Another copy of the site runs; Ctrl+C it |
| "Add to .env first: ..." | Add the named setting (section 4) |
| Sign-in: "no access to a chama yet" | No account for that email or phone: `web-user add`; for the release's two, correct `.env` and start with `--fresh` |
| Google: "did not finish", or back at the home page | The callback is not in Supabase's Redirect URLs, or no Supabase user for that email |
| "Codes by text message are not set up yet" | Phone is off in Supabase, or no provider filled in (web_setup step 7) |
| A code never arrives | A test number never gets a text; otherwise see the API log line `sms hook: ...` and Africa's Talking's balance |
| A scan: "could not reach the extraction service" | Groq key or Groq down: Try again on the scan |
| A scan: "too long for the free reading service" | Groq's free plan (D-043): type the page in, or put Groq on its Developer plan (console.groq.com > Settings > Billing; same key, no code change) |
| The live Space does not start | Its Logs tab; copy the last lines. A first build may fail once |
| Health says "not kept" on the Space | The bucket is not mounted: run `deploy-publish` again, or attach it in the Space's settings |

## 9. Still open

| Item | Who | Notes |
| --- | --- | --- |
| First build and start of the live Space | you, tonight | never built before; `/api/health` must say "kept in the storage bucket" |
| Reading photos | you | Groq's free plan refuses most pages (D-043). Either type pages in (free), or put Groq on its Developer plan (about US$0.01 a page) and then finish the accuracy measurement: `python -m chama.pipeline extract-eval` (4 of 10 pages read so far) |
| Real texted codes | you | Africa's Talking account with credit, then web_setup step 8; tried only against a fake so far |
| Usability sessions with officials and members | you | [usability_test.md](usability_test.md) |
| Chama A test of the model | chama A's officials | needs their answers and more pages (D-029) |
| Grace Kanja's page 149 balance (23,000 or 230,000) | you, from the paper ledger | check before accepting page 149 |
| The laptop's `chama` database | you, when convenient | holds leftovers of the old Tumaini copy (scans to page 151). To rebuild it: `docker exec chama-postgres dropdb -U chama --force chama`, `docker exec chama-postgres createdb -U chama chama`, then `python -m chama.pipeline all`, `score`, and re-add accounts. `kibaba_release` is not touched |
| One person in two chamas | future work | an email or phone opens one account in one chama |
| M-Pesa and bank records | report | not built; the report must say so and why |

## 10. The documents

| Document | What it covers |
| --- | --- |
| [README.md](../README.md) | setup, the pipeline, milestones |
| [web_setup.md](web_setup.md) | sign-in setup, accounts, running the web interface |
| [deployment.md](deployment.md) | the laptop release and the live Space |
| [decisions.md](decisions.md) | every design decision, D-001 to D-042 |
| [milestone_1_report.md](milestone_1_report.md), [milestone_2_report.md](milestone_2_report.md), [milestone_3_report.md](milestone_3_report.md) | what each milestone built and found |
| [m4_master_prompt.md](m4_master_prompt.md) | the web interface's requirements |
| [m4_test_record.md](m4_test_record.md), [traceability.md](traceability.md) | tests and objectives |
| [usability_test.md](usability_test.md) | the usability test kit |
| [data_dictionary.md](data_dictionary.md), [extraction_log.md](extraction_log.md) | the raw layout and how the ledger was typed |
| [git_workflow.md](git_workflow.md) | branches, commits, merges |
| [CHANGELOG.md](../CHANGELOG.md) | every change, newest first |
