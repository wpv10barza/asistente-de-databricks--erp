-- HOROMETRO 3C / DATABRICKS BILLING AUDIT (read-only)
-- Execute in the STUDENT workspace SQL editor with permission to read
-- system.billing.usage. Usage data can arrive ~12 hours late or more.
-- This is actual billed DBU usage, not a live clock or remaining trial balance.
-- No use of SELECT *; no credentials, orders or email addresses involved.

-- 1) Daily DBUs billed by this specific student App (last 14 days).
SELECT
    usage_date,
    usage_metadata.app_name AS app,
    sku_name,
    usage_unit,
    ROUND(SUM(usage_quantity), 4) AS consumed_units
FROM system.billing.usage
WHERE
    billing_origin_product = 'APPS'
    AND usage_metadata.app_name = 'asistente-cloud-erp-alumno'
    AND usage_start_time >= CURRENT_TIMESTAMP() - INTERVAL 14 DAYS
GROUP BY usage_date, usage_metadata.app_name, sku_name, usage_unit
ORDER BY usage_date DESC, consumed_units DESC;

-- 2) Locate strong consumption hours of this specific App.
-- DBUs per UTC hour by SKU; compare with expected provisioned capacity.
SELECT
    DATE_TRUNC('HOUR', usage_start_time) AS utc_hour,
    sku_name,
    ROUND(SUM(usage_quantity), 4) AS dbu_in_hour
FROM system.billing.usage
WHERE
    billing_origin_product = 'APPS'
    AND usage_metadata.app_name = 'asistente-cloud-erp-alumno'
    AND usage_unit = 'DBU'
    AND usage_start_time >= CURRENT_TIMESTAMP() - INTERVAL 14 DAYS
GROUP BY DATE_TRUNC('HOUR', usage_start_time), sku_name
ORDER BY dbu_in_hour DESC
LIMIT 48;

-- 3) Other DBU-consuming products in the SAME student workspace.
-- First identify workspace_id through the App's usage records above.
-- Account-level usage also includes the original workspace; this CTE scopes
-- to the student App workspace rather than indiscriminately mixing accounts.
WITH student_workspace AS (
    SELECT DISTINCT workspace_id
    FROM system.billing.usage
    WHERE billing_origin_product = 'APPS'
      AND usage_metadata.app_name = 'asistente-cloud-erp-alumno'
      AND workspace_id IS NOT NULL
)
SELECT
    u.usage_date,
    u.billing_origin_product,
    u.sku_name,
    ROUND(SUM(u.usage_quantity), 4) AS dbus
FROM system.billing.usage u
JOIN student_workspace sw
  ON u.workspace_id = sw.workspace_id
WHERE
    u.usage_unit = 'DBU'
    AND u.usage_start_time >= CURRENT_TIMESTAMP() - INTERVAL 14 DAYS
GROUP BY u.usage_date, u.billing_origin_product, u.sku_name
ORDER BY u.usage_date DESC, dbus DESC;

-- Note:
-- - Pricing may be affected by contract discounts, free trial credits and
--   vendor API fees outside Databricks.
-- - Never sum usage from the entire account when assessing only one student.
-- - If query #3 is empty, the App may not have billing records yet.
