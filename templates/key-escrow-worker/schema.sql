-- D1 schema for af-atrest key escrow (template only; not deployed).
CREATE TABLE IF NOT EXISTS companies (
  id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS escrow_packages (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL,
  device_code TEXT NOT NULL,
  sealed_key TEXT NOT NULL,
  received_at INTEGER NOT NULL,
  UNIQUE(company_id, device_code)
);

CREATE INDEX IF NOT EXISTS idx_escrow_company ON escrow_packages(company_id);
