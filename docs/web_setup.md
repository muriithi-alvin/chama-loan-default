# Setting up and running the web interface (Milestone 4)

The web interface has three parts that run side by side (decision D-027):

| Part | What it does | Start it with |
| --- | --- | --- |
| PostgreSQL (Docker) | The records, scores, accounts and jobs | `docker compose up -d` |
| API (`src/chama/web/`) | Sign-in, roles, every rule, the data the pages show | `uvicorn chama.web.app:app --port 8000` |
| Worker (`src/chama/web/worker.py`) | Reads scanned photos, runs the pipeline after Accept, scores | `python -m chama.web.worker` |
| Pages (`frontend/`) | What officials and members see, at http://localhost:3000 | `cd frontend`, then `npm run dev` (or `npm run build` then `npm start`) |

Run the Python commands from the project folder and the npm commands from
`frontend/`, which has its own `package.json`.

Sign-in lives in Supabase Auth (free plan): passwords, Google and texted
codes (D-037). No chama data is sent to Supabase: only the email and password,
the Google round trip, or the phone number a code is texted to.

## 1. One-time setup

### Python packages

In the conda `chama` environment:

```powershell
pip install -e ".[dev,ml,extraction,web]"
```

### Node.js packages

Node.js 20.9 or later (this laptop has 24). From the project folder:

```powershell
cd frontend
npm install
cd ..
```

### Supabase (sign-in)

1. Go to https://supabase.com and sign in with GitHub. Click **New project**,
   name it `chama-web`, generate a database password (keep it; the project's
   database is not used) and pick the closest region.
2. **Authentication > Sign In / Providers**: keep **Email** on. Turn **off**
   "Allow new users to sign up", so only accounts you add can sign in, unless
   you use phone codes (step 7).
3. **Authentication > Users > Add user > Create new user**: enter the email
   and a password of 12 or more characters, and tick **Auto Confirm User**.
   Do this for each person, including the release's accounts. Google sign-in
   with the same email then opens the same Supabase user.
4. **Project Settings > API Keys**: copy the **Publishable key**
   (`sb_publishable_...`); on an older project, the **anon public** key. The
   project URL (`https://<ref>.supabase.co`) is under **Connect** or **Data API**.
5. Put both in `.env` (never the secret or service-role key):

   ```
   SUPABASE_URL=https://<ref>.supabase.co
   SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
   ```

6. **Google sign-in (D-037, free).** In https://console.cloud.google.com, make a
   project, then **APIs & Services > OAuth consent screen** (External, app name
   Kibaba, your email; while it is in Testing, add each person's Gmail under
   Test users). Then **Credentials > Create credentials > OAuth client ID**, type
   *Web application*, with the authorised redirect URI Supabase shows on its
   Google provider page (`https://<ref>.supabase.co/auth/v1/callback`). In
   Supabase, **Authentication > Sign In / Providers > Google**: turn it on and
   paste the client ID and secret. Then **Authentication > URL Configuration >
   Redirect URLs**: add every address the site is opened at, with the callback:

   ```
   http://localhost:3000/api/session/google/callback
   https://<your ngrok address>/api/session/google/callback
   ```

   The sign-in page shows "Continue with Google" only once Google is on.
7. **Phone codes (D-037).** Officials confirm every sign-in with a code texted to
   their phone, and members may sign in with a phone code alone. In Supabase,
   **Authentication > Sign In / Providers > Phone**: turn it on and choose an
   SMS provider. Twilio has a free trial (it texts only numbers you verify in
   Twilio, which is enough to test with your own phone); every real text is
   paid after that. Free for testing: under **Test Phone Numbers and OTPs**, add
   `254712345678=123456` (your number without the +, and a fixed code): Supabase
   then sends no text to that number and accepts that code. Supabase still needs
   a provider filled in before test numbers work.
   Supabase makes its own user for a phone the first time a code is sent, so
   for phone codes turn **on** "Allow new users to sign up" (step 2). This is
   safe here: Kibaba asks for a code only for a number that has an account in
   app.users, and the Supabase key stays on the server, so nobody else can ask
   Supabase for codes or sign in to Kibaba with a Supabase user of their own.

Officials without a phone cannot finish signing in. For development on this
laptop only, `TWO_STEP_FOR_OFFICIALS=false` in `.env` turns the second step off.

A free project pauses after a week without use: open its dashboard the day
before a demonstration.

Password resets by email are not set up (the free plan's email service is
limited): reset a password in **Authentication > Users**.

### Humble Sister in the interface (D-036)

The interface shows Humble Sister (chama B) by its members' real names, which
its officials agreed to. It is a copy of chama B's typed pages (`chama_demo` in
config/pipeline.yaml), made from the copy's settings there: `names: real`,
`renames` (Beth Wamae is shown as Alvin Muriithi and Esther Mwangi as Alvin Wise,
in the copy only) and `records_until: 2024-07` (pages 1 to 128). Pages 129 to
149, August 2024 to April 2026, are for entering in the interface, by photo
(chama B's photos are `data/photos/chama_b/chama_b_p129.jpg` onwards) or by
typing. Build it once, then whenever chama B's files or these settings change:

```powershell
python -m chama.pipeline demo-chama      # writes data/raw/chama_demo/ and its names file
python -m chama.pipeline all             # the pipeline, now for chama_demo too
python -m chama.pipeline score           # bands and reasons for every chama
```

An earlier copy, with any pages scanned into it, is moved to
`data/interim/replaced/`. Pages must be added in date order: page 129 first.

### Accounts

After creating the person's sign-in in Supabase (step 3 above), say what the
email or phone may open. Officials need a phone (the second step, D-037):

```powershell
# the treasurer
python -m chama.pipeline web-user add --email <your email> --phone 07XXXXXXXX --role official --chama chama_demo --name "Alvin Muriithi" --position treasurer

# a member: first find their code (Alvin Wise is Esther Mwangi's record)
python -m chama.pipeline web-user codes --chama chama_demo
python -m chama.pipeline web-user add --email <member email> --phone 07XXXXXXXX --role member --chama chama_demo --member M-xxxxxxxx
# a member with a phone only, who signs in with texted codes
python -m chama.pipeline web-user add --phone 07XXXXXXXX --role member --chama chama_demo --member M-xxxxxxxx

python -m chama.pipeline web-user list
python -m chama.pipeline web-user deactivate --email <email or phone>
```

An email or phone has one account, in one chama.

## 2. Running it

Four terminals, each in the project folder with the `chama` environment active:

```powershell
docker compose up -d                          # 1. the database
uvicorn chama.web.app:app --port 8000         # 2. the API
python -m chama.web.worker                    # 3. the worker (loads the model, about a minute)
cd frontend; npm run build; npm start         # 4. the pages: http://localhost:3000
```

Step 4 builds the pages once (a few minutes) and serves the fast version;
build again after changing anything in `frontend/`. Use this for trying the
site and for every demonstration. `npm run dev` instead serves pages that
update as you edit the code, but each page loads about 5.6 MB of unminified
scripts and is compiled the first time it opens, which is slow on this
laptop. In that mode open http://localhost:3000 or http://127.0.0.1:3000
only: at any other address the page shows but its buttons do nothing.

Check that everything is ready: http://localhost:3000/api/health shows
`ready` once the database answers and the worker has loaded the model.

Set `DEMO_MODE=true` in `.env` (then restart the API) before showing the
site on a projector: fictional names for any real chama, and no real ledger
photo. It does not change the interface copy (`chama_demo`): Humble Sister's
names are shown there as its officials agreed (D-036).

### Trying it from a phone on the same Wi-Fi

Find the laptop's address (`ipconfig`, e.g. 192.168.1.20), then in `.env`
set `COOKIE_SECURE=false` and add `http://192.168.1.20:3000` to
`WEB_ORIGINS`, restart the API, serve the built pages (`npm start`, not
`npm run dev`) and open http://192.168.1.20:3000 on the phone. Put `COOKIE_SECURE` back to `true` afterwards. (HTTPS deployment is
Sprint III.)

## 3. Checks

```powershell
ruff check src tests
pytest                                         # the database tests use chama_test and skip without Docker
cd frontend; npm run typecheck; npm run build
python -m chama.pipeline web-stats             # median and 95th percentile time per API route
```

## 4. When something goes wrong

| What you see | What to do |
| --- | --- |
| "The chama server is not answering" on sign-in | Start the API (terminal 2) |
| "Sign-in is not set up on this server yet" | Add `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` to `.env`, restart the API |
| "That email and password do not match" | Check the account in Supabase > Authentication > Users |
| "This account has no access to a chama yet" | Run `web-user add` for that email |
| A scan stays "Waiting for its turn" | Start the worker (terminal 3) |
| A scan fails with the rate limit | Groq's free plan allows about one page a minute; it retries by itself |
| `/api/health` says the worker is not running | Start the worker, wait for "model run ... loaded" |
| Docker or the laptop is very slow | Close other programs (browsers, chat apps); the laptop has 7.4 GB |
