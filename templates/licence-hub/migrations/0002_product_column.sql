-- Legacy databases missing product on licence_requests (fresh schema.sql already has it).
-- Prefer: node scripts/apply-migrations.mjs [--local] <sqlite-path> (guarded).
-- Safe re-run on D1: column add may fail if product already exists — use apply-migrations.mjs instead.
-- DEFAULT must match LICENCE_DEFAULT_PRODUCT (or first LICENCE_PRODUCTS id) before running on non-Yousef DBs.
ALTER TABLE licence_requests ADD COLUMN product TEXT NOT NULL DEFAULT 'trip-orders';
