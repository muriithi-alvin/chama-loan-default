# Deploying Kibaba over HTTPS (Sprint III)

The release runs on a free Hugging Face Docker Space, with the free PostgreSQL
database of the Supabase project that already handles sign-in. It holds the
**demo chama only** (fictional names, D-028); real chamas stay on the project
laptop. Decision D-032.

| Part | Where | What it holds |
| --- | --- | --- |
| Pages, API and worker | Hugging Face Space `<user>/kibaba` (public, free CPU) | Only a Dockerfile and README; the image is built from the private repository |
| Database | Supabase PostgreSQL (free) | The demo chama's records, scores, accounts and scans |
| Sign-in | Supabase Auth (the existing project) | Emails and passwords |
| Code | GitHub, private | Cloned when the image is built, with a read-only token |
| Demo data and model | Hugging Face dataset `<user>/kibaba-data`, **private** | Built by `deploy-bundle`, checked for real names |
| Reading photos | Groq | As on the laptop |

Run the commands below in PowerShell from the project folder, with the `chama`
environment active. Allow about an hour, most of it waiting for the first build.

## 1. Put the code on `main`

The image is built from `main`, so merge the milestone branch first
(see [git_workflow.md](git_workflow.md)).

## 2. Collect the settings

**Supabase database.** In the project's dashboard click **Connect**, then choose
**Session pooler**. The address looks like
`postgresql://postgres.<ref>:[YOUR-PASSWORD]@aws-1-<region>.pooler.supabase.com:5432/postgres`.
The password is the one made with the project; if it is lost, use **Project
Settings > Database > Reset database password**. Leave **Project Settings > Data
API > Exposed schemas** as they are: Kibaba's schemas must not be added.

**Hugging Face.** Sign up at https://huggingface.co, then under **Settings >
Access Tokens > Create new token** make two tokens:

- `kibaba-publish`, type **Write**;
- `kibaba-build`, type **Fine-grained**, ticking only **Read access to contents
  of all repos under your personal namespace**.

**GitHub.** **Settings > Developer settings > Personal access tokens >
Fine-grained tokens > Generate new token**: **Only select repositories**:
`chama-loan-default`; **Repository permissions > Contents: Read-only**.

**The release's own pseudonym key:**

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add all of these to `.env`, which is never committed. Keep the key once it is
made: a new one changes every member code in the release.

```
HF_TOKEN=<kibaba-publish token>
HF_BUILD_TOKEN=<kibaba-build token>
GITHUB_READ_TOKEN=<GitHub token>
CLOUD_POSTGRES_HOST=aws-1-<region>.pooler.supabase.com
CLOUD_POSTGRES_USER=postgres.<ref>
CLOUD_POSTGRES_PASSWORD=<database password>
CLOUD_PSEUDONYM_KEY=<the key from the command above>
```

`GROQ_API_KEY`, `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` are read from the
same file.

## 3. Build the bundle and fill the database

```powershell
python -m chama.pipeline deploy-bundle
python -m chama.pipeline --cloud first-start
```

`deploy-bundle` writes the demo chama and the model to `data/deploy/bundle`,
refusing any file with a word of a real member's name. `--cloud` points that one
command at Supabase instead of the laptop's database, with the demo chama only.
`first-start` loads and scores the demo chama; it took 79 s on a local database
and takes longer over the internet. It ends with:

```
[chama_demo] ledger page 149: 8 members scored (high: 5, medium: 1, low: 2) with model version 1 ...
```

A wrong host or password shows up here within a minute, not after a long build.

## 4. Add the accounts

Sign-in uses the same Supabase users as the laptop; the release only needs to
know each email's chama and role. Member codes differ from the laptop's, so look
them up first.

```powershell
python -m chama.pipeline --cloud web-user codes --chama chama_demo
python -m chama.pipeline --cloud web-user add --email <official email> --role official --chama chama_demo --name "Grace Achieng" --position treasurer
python -m chama.pipeline --cloud web-user add --email <member email> --role member --chama chama_demo --member <code of Muthoni Ndegwa>
python -m chama.pipeline --cloud web-user list
```

## 5. Publish

```powershell
pip install -e ".[deploy]"     # once: the Hugging Face library
python -m chama.pipeline deploy-publish
```

This uploads the bundle to the private dataset (and stops if it is not private),
creates the public Space, sets its variables and secrets, and uploads the
Dockerfile, which starts the build. It prints the site's address,
`https://<user>-kibaba.hf.space`. Follow the build in the Space's **Logs** tab;
the first one takes about 15 minutes, and the Space shows **Running** when done.

## 6. Check it

1. `https://<user>-kibaba.hf.space/api/health` shows `"status":"ready"`.
2. The address opens the landing page, with a padlock in the browser.
3. Sign in as the official: the Overview shows 5 / 1 / 2 members by colour.
4. Open a member, then **Technical details**: model version 1.
5. Sign in as the member, on a phone: My summary shows KSh 460,000 still to repay.
6. Scan the handwritten demo page: it is read, reviewed, accepted and scored.

## Updating the release

- **New code:** merge to `main`, push, then
  `python -m chama.pipeline deploy-publish --rebuild`.
- **New model:** `train`, `register-model`, `deploy-bundle`, then
  `deploy-publish --rebuild`.
- **New library versions:** update `deploy/huggingface/constraints.txt` with
  `python -m pip freeze --exclude-editable`. The image installs exactly those
  versions, because a model saved under one scikit-learn may not load under another.

## If something goes wrong

| What you see | Likely cause | What to do |
| --- | --- | --- |
| `--cloud first-start`: password authentication failed, or could not translate host name | A wrong `CLOUD_POSTGRES_*` value | Copy them again from **Connect > Session pooler**; the user must include `.<ref>` |
| `--cloud first-start` times out, but the database details are right | This network blocks the connection from the laptop | Skip to step 5: the Space runs `first-start` itself. Add the accounts in Supabase's SQL Editor (below) |
| Build log: authentication failed at `git clone` | `GITHUB_READ_TOKEN` wrong or without access | Make the token again, update `.env`, run `deploy-publish --rebuild` |
| Build log: `Remote branch main not found`, or a missing file under `deploy/` | Step 1 was skipped | Merge and push, then `deploy-publish --rebuild` |
| Build log: 401 or Repository Not Found while fetching the dataset | `HF_BUILD_TOKEN` cannot read your repositories | Fix the token's permissions, then `deploy-publish --rebuild` |
| Space shows **Runtime error** | The start-up stopped | Read the **Logs** tab, **Container**; database errors mean the settings above |
| `/api/health` is 503 | Still starting: the worker takes about a minute to load the model | Wait; it names the part that is not ready |
| Blank page on huggingface.co | The site refuses to be framed, and sign-in needs its own cookies | Open `https://<user>-kibaba.hf.space` directly |
| Sign-in: "no access to a chama yet" | The email is not in the release's database | Step 4 |
| "Changes can only be made from this site" | `WEB_ORIGINS` differs from the address in use | Open the address `deploy-publish` printed |
| A scan: "Could not reach the extraction service" | Groq unavailable, or a wrong `GROQ_API_KEY` | Check the key, then **Try again** on the scan |

**Accounts without the laptop.** In Supabase's **SQL Editor**:

```sql
SELECT member_code, canonical_name FROM private.member_codes WHERE chama_id = 'chama_demo' ORDER BY 2;

INSERT INTO app.users (email, role, chama_id, display_name, position)
VALUES ('<official email>', 'official', 'chama_demo', 'Grace Achieng', 'treasurer');

INSERT INTO app.users (email, role, chama_id, member_code)
VALUES ('<member email>', 'member', 'chama_demo', '<code of Muthoni Ndegwa>');
```

## Limits of the free release

- The Space sleeps after 48 hours without visits; the next visit wakes it in a
  few minutes. Open it before a demonstration.
- Uploaded photos and the files of accepted scans live on the container's own
  disk and are lost when it restarts. The records already in the database stay,
  but a later scan reloads the raw records from files, so earlier scanned pages
  drop out. For a demonstration or test day this does not matter; a lasting
  service would keep these files in storage (future work).
- The free Supabase project pauses after a week without use: open its dashboard
  before a demonstration.
