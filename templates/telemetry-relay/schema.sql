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

-- Licence mailbox (Apps-Factory 0.13.0). A shop asks for a trial or a paid code; the owner's trusted licensing program (Licence
-- Studio, the only place a signing key exists) pulls the request, decides, and hands the signed code back; the shop's program
-- collects it. The relay never holds a signing key and never opens a code.
-- machine = sha256 tag of the PC (never the raw machine id); used only to refuse a second trial on the same PC.
-- poll_hash = sha256 of the secret the shop was given once; the code is only shown to whoever holds it.
CREATE TABLE IF NOT EXISTS licence_requests (
  id TEXT PRIMARY KEY,
  product TEXT NOT NULL,
  kind TEXT NOT NULL,              -- trial | monthly | permanent
  device TEXT NOT NULL,            -- the 10-character device code, e.g. 7KD2M-QX9TP
  machine TEXT,                    -- 64 hex (trial only)
  nonce TEXT NOT NULL,             -- the shop's own request id: a replay finds the same row
  poll_hash TEXT NOT NULL,
  shop TEXT NOT NULL DEFAULT '',   -- untrusted text typed by the shop (at most 60 characters), shown to the owner as text only
  ref TEXT NOT NULL DEFAULT '',    -- untrusted payment reference (paid kinds)
  version TEXT NOT NULL DEFAULT '',
  src TEXT,                        -- daily-salted hash of the sender's address (16 hex)
  status TEXT NOT NULL,            -- pending | issued | refused | delivered | expired
  reason TEXT NOT NULL DEFAULT '',
  code TEXT,                       -- the signed code while it waits for the shop (a public artefact bound to the device)
  created_at INTEGER NOT NULL,
  decided_at INTEGER,
  delivered_at INTEGER,
  owner_decision TEXT,             -- NULL | approved | denied: the owner's button on Telegram. Never a licence by itself.
  owner_decided_at INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS licence_nonce ON licence_requests (product, device, nonce);
CREATE INDEX IF NOT EXISTS licence_status ON licence_requests (status, created_at);
CREATE INDEX IF NOT EXISTS licence_device ON licence_requests (device, created_at);
CREATE INDEX IF NOT EXISTS licence_machine ON licence_requests (product, machine, kind, status);
CREATE INDEX IF NOT EXISTS licence_src ON licence_requests (src, created_at);
-- Every step of a request (created, refused, issued, delivered), for the owner to read back. Never a code, never a shop text.
CREATE TABLE IF NOT EXISTS licence_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at INTEGER NOT NULL,
  request_id TEXT,
  event TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS licence_events_at ON licence_events (at);
-- An existing deployment (before Apps-Factory 0.14.0) adds the two columns once; a new one needs nothing:
--   ALTER TABLE licence_requests ADD COLUMN owner_decision TEXT;
--   ALTER TABLE licence_requests ADD COLUMN owner_decided_at INTEGER;
