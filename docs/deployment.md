# Deploying Kibaba over HTTPS (Sprint III)

The live release runs on Hugging Face (see the last section, D-041). The release can
also run on the project laptop, and a free ngrok tunnel gives it an HTTPS
address. It holds only the chamas marked `release: true` in config/pipeline.yaml:
**Humble Sister**, by its members' real names, which its officials agreed to (D-036),
with records to July 2024. It has a database of its own, so chama B's own records (the
ones the model learned from) are out of its reach. Decision D-034.

| Part | Where | What it holds |
| --- | --- | --- |
| Pages, API and worker | The project laptop; only the pages listen, on 127.0.0.1 | The code |
| Database | `kibaba_release`, in the laptop's Docker PostgreSQL | Only Humble Sister's copy, the pages added to it and two accounts |
| Public address | ngrok (free), over port 443 | Nothing: it passes requests through |
| Sign-in | Supabase Auth (the existing project) | Emails, passwords, Google sign-in, texted codes (D-037) |
| Reading photos | Groq | As on the laptop |

**The site is up only while the laptop is on, awake and online**, with both windows
below left open.

## One-time setup

1. Add to `.env`, which is never committed:

   ```
   CLOUD_PSEUDONYM_KEY=<from: python -c "import secrets; print(secrets.token_urlsafe(32))">
   RELEASE_OFFICIAL_EMAIL=<the treasurer's email: Alvin Muriithi>
   RELEASE_OFFICIAL_PHONE=<the treasurer's phone, 07XXXXXXXX: each sign-in's code goes there>
   RELEASE_MEMBER_EMAIL=<the member's email: Alvin Wise>
   RELEASE_MEMBER_PHONE=<optional: the member's phone, for signing in with a code>
   ```

   `GROQ_API_KEY`, `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` are read from the
   same file. Set up Google sign-in and phone codes in Supabase as in
   docs/web_setup.md (steps 6 and 7), with
   `https://<your ngrok address>/api/session/google/callback` among the redirect URLs.
2. Build Humble Sister's copy and the bundle:

   ```powershell
   python -m chama.pipeline demo-chama
   python -m chama.pipeline deploy-bundle
   ```

   The bundle holds real names, so it stays on this laptop: `deploy-publish` refuses it.
3. Sign up at https://ngrok.com, download ngrok for Windows from
   https://ngrok.com/download, and unzip it to a folder outside this project. If you
   install it from the Microsoft Store instead, there is nothing to unzip: type `ngrok`
   rather than `.\ngrok` in the commands below.
4. Copy the command under **Your Authtoken** in ngrok's dashboard and run it once:

   ```powershell
   .\ngrok config add-authtoken <your token>
   ```

## Starting it

Plug the laptop in and stop it sleeping (**Settings > System > Power**), make sure
Docker Desktop is running, and close what you can: the laptop is short of memory.

**Window 1**, in the folder holding `ngrok.exe`:

```powershell
.\ngrok http 127.0.0.1:3000
```

The **Forwarding** line shows your `https://...` address, which stays the same each
time on the free plan, and the status should say **online**. Until window 2 is ready,
visitors see an ngrok error page.

**Window 2**, in the project folder with the `chama` environment active:

```powershell
python -m chama.pipeline serve-release --address https://<your address>
```

The first start loads Humble Sister's copy and builds the pages, about 3 minutes. After
`demo-chama` has changed the copy, start with `--fresh` (below). Later
starts only build the pages, so they are quicker. Wait for `Ready. Kibaba is at ...`.
To stop it, press Ctrl+C in both windows.

## Check it

1. On a phone, using mobile data rather than the laptop's Wi-Fi, open the address.
   ngrok shows a warning page on a browser's first visit: tap **Visit Site**.
2. The landing page opens, with a padlock in the browser.
3. `https://<your address>/api/health` shows `"status":"ready"`.
4. Sign in as the treasurer with Google or the password: a code is texted to
   `RELEASE_OFFICIAL_PHONE`; type it. The Overview's records end at ledger page 128
   (July 2024).
5. Sign in as the member (Alvin Wise): his records end at page 128, where the ledger
   shows a balance of KSh 40,000.
6. Add page 129 (August 2024): scan `data/photos/chama_b/chama_b_p129.jpg`, or use
   **Type a page**. Each step opens the next by itself, and the results open when the
   records are updated. Then page 130, and so on: pages go in date order.

The address is public, but every page except the landing page needs a sign-in, and
each account sees only its own chama (and a member only their own records).

## Starting again

To go back to page 128, for example to enter the test pages again: stop window 2,
then add `--fresh` to the command. It deletes the release's database and the pages
scanned or typed into it, with their photos, and leaves chama B alone. Use it too after
`demo-chama` and `deploy-bundle` have made a new copy.

## If something goes wrong

| What you see | Likely cause | What to do |
| --- | --- | --- |
| "Docker did not answer within 3 minutes" | Docker has frozen. `docker ps` can still answer while it is frozen | Restart the laptop, close other apps, try again |
| "Port 3000 is in use" or "Port 8000 is in use" | Another copy of the site is running | Press Ctrl+C in its window, then try again |
| "Add to .env first" | A setting is missing | Add it, using the setup above |
| ngrok: authentication failed | The authtoken was not added | Step 4 of the setup |
| ngrok: endpoint already online | ngrok is running elsewhere | Close the other window |
| The address shows an ngrok error page | Window 2 is not running or not ready yet | Wait for `Ready`, or start window 2 |
| "Changes can only be made from this site" | `--address` differs from the address in use | Restart window 2 with the Forwarding address |
| Sign-in: "no access to a chama yet" | The email differs from `RELEASE_*_EMAIL` | Correct `.env`, then restart with `--fresh` |
| Google: "did not finish" | The callback address is not in Supabase's redirect URLs | Add it (docs/web_setup.md, step 6) |
| "Codes by text message are not set up yet" | Phone is off in Supabase, or no SMS provider | docs/web_setup.md, step 7 |
| "Supabase does not allow new sign-ins" | Sign-ups are off and the phone has had no code before | Allow sign-ups (docs/web_setup.md, step 7) |
| A scan: "Could not reach the extraction service" | Groq unavailable, or a wrong `GROQ_API_KEY` | Check the key, then **Try again** on the scan |

## Limits

- The site stops when the laptop sleeps, shuts down or loses its connection.
- ngrok's free plan has monthly limits on requests and data; its dashboard shows the
  usage. A demonstration and usability tests should fit, but check it on the day.
- The free Supabase project pauses after a week without use: open its dashboard
  before a demonstration, or sign-in stops working.

## The live release on Hugging Face (D-041)

The live site runs on a Hugging Face Docker Space, so the laptop can be off. It needs
Hugging Face **PRO, US$9 a month** (paid by card); the Space runs on the free CPU
Basic hardware. Humble Sister's officials agreed under the MOU to Kibaba holding its
records there (`hosting: agreed` in config/pipeline.yaml).

| Part | Where | What it holds |
| --- | --- | --- |
| The Space `<owner>/kibaba` | Hugging Face, public address `https://<owner>-kibaba.hf.space` | Only `README.md` and `Dockerfile` |
| Dataset `<owner>/kibaba-data` | Hugging Face, private | The bundle: typed pages to page 128, names, the model |
| Bucket `<owner>/kibaba-storage` | Hugging Face, private, mounted in the Space at `/data` | What officials add: pages, photos, learned names, and the database saved every few minutes |
| Sign-in | Supabase Auth | As on the laptop |

**What to know about CPU Basic.** After 48 hours without visitors the Space sleeps; the
next visitor wakes it, and waits two or three minutes while it starts. Its own disk is
wiped at every restart, so the database is saved to the bucket within two minutes of
any change, right after each records update and when the Space stops, and is
restored at the next start. A change made in the last moments before a crash can be
lost; anything older is kept. `https://<address>/api/health` says where pages are
kept: it must say "kept in the storage bucket".

### Publishing

1. On https://huggingface.co/settings/billing, subscribe to **PRO**.
2. In `.env`, check `HF_TOKEN` (write), `HF_BUILD_TOKEN` (read), `GITHUB_READ_TOKEN`,
   `CLOUD_PSEUDONYM_KEY`, `GROQ_API_KEY`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`,
   `RELEASE_OFFICIAL_EMAIL`, `RELEASE_OFFICIAL_PHONE`, `RELEASE_MEMBER_EMAIL` and,
   if wanted, `RELEASE_MEMBER_PHONE`. While phone codes are not set up in Supabase,
   `TWO_STEP_FOR_OFFICIALS=false` turns the officials' texted code off in the Space too.
3. Merge `m4-web-interface` into `main` and push: the image is built from `main`.
4. Build the bundle, then publish:

   ```powershell
   python -m chama.pipeline deploy-bundle
   python -m chama.pipeline deploy-publish
   ```

5. Watch the build in the Space's **Logs** tab (the first build takes 15 to 30 minutes).
   The image has never been built before, so a first-build failure is possible: copy
   the log's last lines.
6. In Supabase, **Authentication > URL Configuration > Redirect URLs**: add
   `https://<owner>-kibaba.hf.space/api/session/google/callback`.
   For real texted codes (D-042), also set **Authentication > Hooks > Send SMS hook**
   to `https://<owner>-kibaba.hf.space/api/hooks/send-sms` with its secret, and put
   `SMS_HOOK_SECRET` and the `AFRICASTALKING_*` settings in `.env` before step 4 (or
   run `deploy-publish` again after adding them): see docs/web_setup.md, step 8.
7. Open `https://<owner>-kibaba.hf.space/api/health`: `ready`, with storage "kept in the
   storage bucket". Then sign in and add page 129.

After pushing new code to `main`, run `deploy-publish --rebuild`. The bucket and its
records are kept; the accounts are only made on the first start, so a change to
`RELEASE_*` after that needs `web-user` commands in the Space, or a fresh start.

### Starting the live release again from page 128

Delete the bucket's `kibaba` folder (on the bucket's page on Hugging Face, or
`hf buckets rm`), then restart the Space from its **Settings**. This deletes every page
added there and cannot be undone. If saved copies exist but none restores, the
Space does not start at all, so that it never saves over them: the Logs tab names
the copies, and the admin decides what to do with them.
