-- One row per signed batch, waiting for the Control Center to pull it. Body is the product's gzip batch, base64.
CREATE TABLE IF NOT EXISTS batches (
  id TEXT PRIMARY KEY,
  install_id TEXT NOT NULL,
  ts INTEGER NOT NULL,
  nonce TEXT NOT NULL,
  sig TEXT NOT NULL,
  body TEXT NOT NULL,
  received_at INTEGER NOT NULL,
  UNIQUE (install_id, nonce)
);
CREATE INDEX IF NOT EXISTS batches_install ON batches (install_id, received_at);
CREATE INDEX IF NOT EXISTS batches_received ON batches (received_at);
