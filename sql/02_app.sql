-- Milestone 4: the web interface (decisions D-026, D-027).
--   app     : accounts, sessions, uploads, jobs, pipeline runs and risk scores (codes only)
--   private : drafts of scanned pages, name matches and the edit record (hold names)
-- Safe to re-run: the pipeline runs every sql/*.sql file before each `all`.
CREATE SCHEMA IF NOT EXISTS app;

-- People who can sign in. Accounts are made with
-- `python -m chama.pipeline web-user add`; the password lives in Supabase Auth.
CREATE TABLE IF NOT EXISTS app.users (
    id           BIGSERIAL PRIMARY KEY,
    identity_id  TEXT UNIQUE,                -- Supabase user id, filled at the first sign-in
    email        TEXT        NOT NULL,
    display_name TEXT,                       -- officials only; a member's name comes from the records
    position     TEXT,                       -- chair, treasurer or secretary (officials)
    role         TEXT        NOT NULL CHECK (role IN ('official', 'member', 'admin')),
    chama_id     TEXT        NOT NULL,
    member_code  TEXT,                       -- members only: the record they may see
    active       BOOLEAN     NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT members_have_a_code CHECK ((role = 'member') = (member_code IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS users_email ON app.users (lower(email));

-- Signed-in sessions. The cookie holds a random token; only its SHA-256 is
-- kept here, so a copy of this table cannot be used to sign in.
CREATE TABLE IF NOT EXISTS app.sessions (
    token_hash TEXT        PRIMARY KEY,
    user_id    BIGINT      NOT NULL REFERENCES app.users (id),
    csrf_token TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    ended_at   TIMESTAMPTZ
);

-- Ledger photos sent from the Scan page. The photo itself is kept in
-- PHOTO_DIR, outside the web folders, re-saved without location data.
CREATE TABLE IF NOT EXISTS app.uploads (
    id              BIGSERIAL PRIMARY KEY,
    chama_id        TEXT        NOT NULL,
    uploaded_by     BIGINT      NOT NULL REFERENCES app.users (id),
    photo_path      TEXT        NOT NULL,
    checksum        TEXT        NOT NULL,     -- SHA-256 of the photo as sent
    idempotency_key TEXT        NOT NULL UNIQUE,
    status          TEXT        NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'reading', 'ready', 'failed', 'accepted', 'discarded')),
    problem         TEXT,                     -- why reading failed, in words for the official
    provider        TEXT,
    model           TEXT,
    seconds         REAL,                     -- time the model took to read the page
    page_no         INTEGER,                  -- ledger page number, given at Accept
    meeting_date    DATE,
    accepted_by     BIGINT REFERENCES app.users (id),
    accepted_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT one_upload_per_photo UNIQUE (chama_id, checksum),
    CONSTRAINT one_upload_per_page UNIQUE (chama_id, page_no)
);

-- Background work for python -m chama.web.worker. One job of each kind per
-- upload: a retry runs the same job again instead of adding one.
CREATE TABLE IF NOT EXISTS app.jobs (
    id            BIGSERIAL PRIMARY KEY,
    kind          TEXT        NOT NULL CHECK (kind IN ('read_photo', 'run_pipeline')),
    upload_id     BIGINT      NOT NULL REFERENCES app.uploads (id),
    status        TEXT        NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'done', 'failed')),
    step          TEXT,
    error_code    TEXT,
    error_message TEXT,
    attempts      INTEGER     NOT NULL DEFAULT 0,
    run_after     TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_at     TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    CONSTRAINT one_job_per_kind UNIQUE (upload_id, kind)
);
CREATE INDEX IF NOT EXISTS jobs_waiting ON app.jobs (run_after) WHERE status = 'queued';

-- The rows read from a scanned page, as the official corrects them. `cells`
-- holds the raw-layout columns as text, exactly as written on the page.
CREATE TABLE IF NOT EXISTS private.draft_rows (
    id         BIGSERIAL PRIMARY KEY,
    upload_id  BIGINT      NOT NULL REFERENCES app.uploads (id),
    tbl        TEXT        NOT NULL CHECK (tbl IN ('meetings', 'statements', 'new_loans')),
    position   INTEGER     NOT NULL,
    cells      JSONB       NOT NULL,
    added      BOOLEAN     NOT NULL DEFAULT false,   -- added by the official, not read from the photo
    deleted    BOOLEAN     NOT NULL DEFAULT false,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS draft_rows_upload ON private.draft_rows (upload_id);

-- Flags from chama.extraction.checks on the current draft, replaced on each save.
CREATE TABLE IF NOT EXISTS private.draft_flags (
    id        BIGSERIAL PRIMARY KEY,
    upload_id BIGINT NOT NULL REFERENCES app.uploads (id),
    row_id    BIGINT NOT NULL REFERENCES private.draft_rows (id),
    col       TEXT,
    rule      TEXT   NOT NULL,
    level     TEXT   NOT NULL CHECK (level IN ('check', 'hint')),
    message   TEXT   NOT NULL
);
CREATE INDEX IF NOT EXISTS draft_flags_upload ON private.draft_flags (upload_id);

-- Each spelling on a scanned page, matched to a member before Accept.
CREATE TABLE IF NOT EXISTS private.name_matches (
    upload_id      BIGINT  NOT NULL REFERENCES app.uploads (id),
    raw_name       TEXT    NOT NULL,          -- normalised spelling, as in private.member_aliases
    canonical_name TEXT,                      -- the member; empty until matched
    is_new         BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (upload_id, raw_name)
);

-- The edit record (OFF-13): who changed what on a scanned page, and when.
-- Rows are only ever added: the trigger below refuses updates and deletes.
CREATE TABLE IF NOT EXISTS private.row_edits (
    id        BIGSERIAL PRIMARY KEY,
    upload_id BIGINT      NOT NULL REFERENCES app.uploads (id),
    row_id    BIGINT      REFERENCES private.draft_rows (id),
    tbl       TEXT        NOT NULL,
    col       TEXT,
    action    TEXT        NOT NULL CHECK (action IN ('edit', 'add_row', 'delete_row', 'match_name')),
    old_value TEXT,
    new_value TEXT,
    edited_by BIGINT      NOT NULL REFERENCES app.users (id),
    edited_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION private.refuse_edit_record_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'private.row_edits is an insert-only record: rows cannot be changed or deleted';
END
$$;
DROP TRIGGER IF EXISTS row_edits_insert_only ON private.row_edits;
CREATE TRIGGER row_edits_insert_only
    BEFORE UPDATE OR DELETE ON private.row_edits
    FOR EACH ROW EXECUTE FUNCTION private.refuse_edit_record_change();
DROP TRIGGER IF EXISTS row_edits_no_truncate ON private.row_edits;
CREATE TRIGGER row_edits_no_truncate
    BEFORE TRUNCATE ON private.row_edits
    FOR EACH STATEMENT EXECUTE FUNCTION private.refuse_edit_record_change();

-- The pipeline run started by an accepted scan: exactly one per upload.
CREATE TABLE IF NOT EXISTS app.pipeline_runs (
    id          BIGSERIAL PRIMARY KEY,
    upload_id   BIGINT      NOT NULL REFERENCES app.uploads (id),
    chama_id    TEXT        NOT NULL,
    status      TEXT        NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'done', 'failed')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at  TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    CONSTRAINT one_run_per_upload UNIQUE (upload_id)
);

CREATE TABLE IF NOT EXISTS app.pipeline_steps (
    run_id        BIGINT  NOT NULL REFERENCES app.pipeline_runs (id),
    step          TEXT    NOT NULL CHECK (step IN ('ingest', 'names', 'anonymise', 'checks', 'score')),
    position      INTEGER NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'waiting'
        CHECK (status IN ('waiting', 'running', 'done', 'failed')),
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    error_message TEXT,
    PRIMARY KEY (run_id, step)
);

-- Early-warning bands with their reasons, written by `python -m chama.pipeline
-- score`. Pages read these; no raw score is stored (ground rule G3).
CREATE TABLE IF NOT EXISTS app.risk_scores (
    id            BIGSERIAL PRIMARY KEY,
    chama_id      TEXT        NOT NULL,
    member_code   TEXT        NOT NULL,
    page_no       INTEGER     NOT NULL,       -- the meeting the score is based on
    meeting_month DATE        NOT NULL,
    meeting_date  DATE,
    band          TEXT        NOT NULL CHECK (band IN ('low', 'medium', 'high')),
    reasons       JSONB       NOT NULL,       -- [{feature, sentence, effect}], strongest first
    model_run_id  TEXT        NOT NULL,
    model_name    TEXT        NOT NULL,
    scored_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT one_score_per_member_meeting_run UNIQUE (chama_id, member_code, page_no, model_run_id)
);
CREATE INDEX IF NOT EXISTS risk_scores_meeting ON app.risk_scores (chama_id, page_no);
-- S-8: the registered model version and a SHA-256 of its files, so each colour
-- can be traced to the exact model that gave it (D-030).
ALTER TABLE app.risk_scores ADD COLUMN IF NOT EXISTS model_version TEXT;
ALTER TABLE app.risk_scores ADD COLUMN IF NOT EXISTS model_checksum TEXT;

-- The worker's heartbeat, for the health check: the model it loaded and when
-- it was last seen.
CREATE TABLE IF NOT EXISTS app.worker_status (
    worker          TEXT        PRIMARY KEY,
    model_run_id    TEXT,
    model_loaded_at TIMESTAMPTZ,
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
