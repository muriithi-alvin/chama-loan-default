# Deploying Kibaba over HTTPS (Sprint III)

The release runs on a free Hugging Face Docker Space. Its database runs inside
the same container, and sign-in uses the Supabase project that already handles it.
It holds the **demo chama only** (fictional names, D-028); real chamas stay on the
project laptop. Decisions D-032 and D-033.

| Part | Where | What it holds |
| --- | --- | --- |
| Pages, API, worker and database | Hugging Face Space `<user>/kibaba` (public, free CPU) | Only a Dockerfile and README are public; the image is built from the private repository |
| Sign-in | Supabase Auth (the existing project) | Emails and passwords |
| Code | GitHub, private | Cloned when the image is built, with a read-only token |
| Demo data and model | Hugging Face dataset `<user>/kibaba-data`, **private** | Built by `deploy-bundle`, checked for real names |
| Reading photos | Groq | As on the laptop |

Run the commands below in PowerShell from the project folder, with the `chama`
environment active. Allow about 45 minutes, most of it waiting for the first build.

## 1. Put the code on `main`

The image is built from `main`, so merge the milestone branch first
(see [git_workflow.md](git_workflow.md)).

## 2. Collect the settings

**Hugging Face.** Sign up at https://huggingface.co, then under **Settings >
Access Tokens > Create new token** make two tokens:

- `kibaba-publish`, type **Write**;
- `kibaba-build`, type **Fine-grained**, ticking only **Read contents of your
  repos** under **Repositories**.

**GitHub.** **Settings > Developer settings > Personal access tokens >
Fine-grained tokens > Generate new token**: **Only select repositories**:
`chama-loan-default`; **Repository permissions > Contents: Read-only**.

**The release's own pseudonym key:**

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**The demo accounts.** The emails of the official and the member, as they are in
Supabase **Authentication > Users**. Their passwords stay the same.

Add all of these to `.env`, which is never committed:

```
HF_TOKEN=<kibaba-publish token>
HF_BUILD_TOKEN=<kibaba-build token>
GITHUB_READ_TOKEN=<GitHub token>
CLOUD_PSEUDONYM_KEY=<the key from the command above>
RELEASE_OFFICIAL_EMAIL=<the official's email>
RELEASE_MEMBER_EMAIL=<the member's email>
```

`GROQ_API_KEY`, `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` are read from the
same file.

## 3. Build the bundle and publish

```powershell
pip install -e ".[deploy]"     # once: the Hugging Face library
python -m chama.pipeline deploy-bundle
python -m chama.pipeline deploy-publish
```

`deploy-bundle` writes the demo chama and the model to `data/deploy/bundle`,
refusing any file with a word of a real member's name. `deploy-publish` uploads
that folder to the private dataset (and stops if it is not private), creates the
public Space, sets its variables and secrets, and uploads the Dockerfile, which
starts the build. It prints the site's address,
`https://<user>-kibaba.hf.space`.

Follow the build in the Space's **Logs** tab. The first one takes about 15 minutes.
The container then loads the demo chama, scores it and adds the two accounts (about
two minutes) before the Space shows **Running**.

## 4. Check it

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
| Build log: authentication failed at `git clone` | `GITHUB_READ_TOKEN` wrong or without access | Make the token again, update `.env`, run `deploy-publish --rebuild` |
| Build log: `Remote branch main not found`, or a missing file under `deploy/` | Step 1 was skipped | Merge and push, then `deploy-publish --rebuild` |
| Build log: 401 or Repository Not Found while fetching the dataset | `HF_BUILD_TOKEN` cannot read your repositories | Fix the token's permissions, then `deploy-publish --rebuild` |
| Space shows **Runtime error** | The start-up stopped | Read the **Logs** tab, **Container**, and find the first error |
| `/api/health` is 503 | Still starting: the worker takes about a minute to load the model | Wait; it names the part that is not ready |
| Blank page on huggingface.co | The site refuses to be framed, and sign-in needs its own cookies | Open `https://<user>-kibaba.hf.space` directly |
| Sign-in: "no access to a chama yet" | The email differs from `RELEASE_*_EMAIL` | Correct `.env`, then run `deploy-publish` again |
| Sign-in: email and password do not match | No such user in Supabase, or a wrong password | Check **Authentication > Users** in Supabase |
| "Changes can only be made from this site" | `WEB_ORIGINS` differs from the address in use | Open the address `deploy-publish` printed |
| A scan: "Could not reach the extraction service" | Groq unavailable, or a wrong `GROQ_API_KEY` | Check the key, then **Try again** on the scan |

## Limits of the free release

- **Every restart returns the release to its starting state.** The database and
  uploaded photos live on the container's own disk, so scanned pages, edit records
  and uploads last only until the next restart. This suits a demonstration: a
  restart resets it. A lasting service would use a managed database (future work).
  A restart comes from a rebuild, a settings change, or the Space waking from sleep.
- The Space sleeps after 48 hours without visits; the next visit wakes it in a
  few minutes. Open it before a demonstration.
- The free Supabase project pauses after a week without use: open its dashboard
  before a demonstration, or sign-in stops working.
