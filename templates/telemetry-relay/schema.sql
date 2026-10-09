-- Protocol 2 (Apps-Factory 0.9.0). One row per batch, waiting for the Control Center to pull it.
-- body is the product's gzip batch, base64. known = 0: the install was not registered when it arrived (pending area).
-- token_hash = sha256 of the bearer token the batch came with; the Control Center checks it again.
-- (The 0.8 table `batches` is no longer used. Pull it empty with the old Control Center first, then you may drop it.)
CREATE TABLE IF NOT EXISTS inbox (
  id TEXT PRIMARY KEY,
  install_id TEXT NOT NULL,
  known INTEGER NOT NULL,
  token_hash TEXT NOT NULL,
  src TEXT,
  sent_at INTEGER,
  size INTEGER NOT NULL,
  body TEXT NOT NULL,
  received_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS inbox_install ON inbox (install_id, received_at);
CREATE INDEX IF NOT EXISTS inbox_pending ON inbox (known, src);
CREATE INDEX IF NOT EXISTS inbox_received ON inbox (received_at);
-- Registered installs, pushed by the Control Center (POST /installs). Never the token itself.
CREATE TABLE IF NOT EXISTS installs (
  id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL,
  gen TEXT NOT NULL
);
