-- Customers keyed by (product, device). Existing rows use the DEFAULT product id below.
-- Prefer: node scripts/apply-migrations.mjs [--local] <sqlite-path> (guarded).
-- DEFAULT must match LICENCE_DEFAULT_PRODUCT (or first LICENCE_PRODUCTS id) before running on non-Yousef DBs.
ALTER TABLE customers ADD COLUMN product TEXT NOT NULL DEFAULT 'trip-orders';
CREATE UNIQUE INDEX IF NOT EXISTS customers_product_device ON customers(product, device);
