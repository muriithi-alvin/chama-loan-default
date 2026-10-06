-- Database layers, from raw to model-ready.
--   raw       : exactly what was typed from the ledgers, all text, real names (restricted)
--   private   : the name-to-code link (restricted, never used by models or dashboard)
--   staging   : names replaced by codes, values given proper types (dates, numbers)
--   analytics : cleaned tables and engineered features used for modelling
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS private;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;

-- Tracks every pipeline run, for traceability.
CREATE TABLE IF NOT EXISTS raw.load_log (
    load_id      BIGSERIAL PRIMARY KEY,
    chama_id     TEXT        NOT NULL,
    source_file  TEXT        NOT NULL,
    sheet        TEXT        NOT NULL,
    row_count    INTEGER     NOT NULL,
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Links the different spellings of one person to a single member.
-- Filled by the matching step; reviewed by hand.
CREATE TABLE IF NOT EXISTS private.member_aliases (
    chama_id       TEXT NOT NULL,
    raw_name       TEXT NOT NULL,   -- spelling from the ledger, normalised: "J. Kamau" -> "j kamau"
    canonical_name TEXT NOT NULL,   -- the agreed full name, e.g. "John Kamau"
    PRIMARY KEY (chama_id, raw_name)
);

-- The name-to-code link.
CREATE TABLE IF NOT EXISTS private.member_codes (
    chama_id       TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    member_code    TEXT NOT NULL UNIQUE,
    PRIMARY KEY (chama_id, canonical_name)
);
