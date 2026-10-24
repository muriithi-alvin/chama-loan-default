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

Sign-in passwords live in Supabase Auth (free plan). No chama data is sent
to Supabase: only the email and password, when someone signs in.

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
   "Allow new users to sign up", so only accounts you add can sign in.
3. **Authentication > Users > Add user > Create new user**: enter the email
   and a password of 12 or more characters, and tick **Auto Confirm User**.
   Do this for each person, including the demo accounts.
4. **Project Settings > API Keys**: copy the **Publishable key**
   (`sb_publishable_...`); on an older project, the **anon public** key. The
   project URL (`https://<ref>.supabase.co`) is under **Connect** or **Data API**.
5. Put both in `.env` (never the secret or service-role key):

   ```
   SUPABASE_URL=https://<ref>.supabase.co
   SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
   ```

A free project pauses after a week without use: open its dashboard the day
before a demonstration.

Password resets by email are not set up (the free plan's email service is
limited): reset a password in **Authentication > Users**.

### The demo chama (D-028)

For any demonstration, use the demo chama: chama B's typed pages with
fictional names. Build it once, then whenever chama B's files change:

```powershell
python -m chama.pipeline demo-chama      # writes data/raw/chama_demo/ and its names file
python -m chama.pipeline all             # the pipeline, now for chama_demo too
python -m chama.pipeline score           # bands and reasons for every chama
```

For the demo scan, write a fictional ledger page by hand (open decision 1),
using names from `python -m chama.pipeline web-user codes --chama chama_demo`,
dated after the demo chama's last meeting.

### Accounts

After creating the person's sign-in in Supabase (step 3 above), say what the
email may open:

```powershell
# an official of the demo chama, shown as a fictional name
python -m chama.pipeline web-user add --email <official email> --role official --chama chama_demo --name "Grace Achieng" --position treasurer

# a member: first find their code
python -m chama.pipeline web-user codes --chama chama_demo
python -m chama.pipeline web-user add --email <member email> --role member --chama chama_demo --member M-xxxxxxxx

python -m chama.pipeline web-user list
python -m chama.pipeline web-user deactivate --email <email>
```

## 2. Running it

Four terminals, each in the project folder with the `chama` environment active:

```powershell
docker compose up -d                          # 1. the database
uvicorn chama.web.app:app --port 8000         # 2. the API
python -m chama.web.worker                    # 3. the worker (loads the model, about a minute)
cd frontend; npm run dev                      # 4. the pages: http://localhost:3000
```

For a demonstration, build the pages once and serve the fast version:

```powershell
cd frontend; npm run build; npm start
```

Check that everything is ready: http://localhost:3000/api/health shows
`ready` once the database answers and the worker has loaded the model.

Set `DEMO_MODE=true` in `.env` (then restart the API) before showing the
site on a projector: fictional names for any real chama, and no real ledger
photo. The demo chama's names are fictional already.

### Trying it from a phone on the same Wi-Fi

Find the laptop's address (`ipconfig`, e.g. 192.168.1.20), then in `.env`
set `COOKIE_SECURE=false` and add `http://192.168.1.20:3000` to
`WEB_ORIGINS`, restart the API, and open http://192.168.1.20:3000 on the
phone. Put `COOKIE_SECURE` back to `true` afterwards. (HTTPS deployment is
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
