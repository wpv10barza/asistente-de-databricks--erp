"""Safety checks for optional student 3C seven-day cloud lab."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
flow = (ROOT / ".github/workflows/alumno-lab-expiry-guard.yml").read_text(encoding="utf-8")
ps = (ROOT / "scripts/Lab-Alumno-3C.ps1").read_text(encoding="utf-8")
sql = (ROOT / "sql/horometro_consumo_alumno_3c.sql").read_text(encoding="utf-8")
doc = (ROOT / "docs/LAB_ALUMNO_7D_HOROMETRO.md").read_text(encoding="utf-8")
base_flow = (ROOT / ".github/workflows/deploy-databricks.yml").read_text(encoding="utf-8")

assert "schedule:" in flow and "workflow_dispatch:" in flow
assert 'cron: "17,47 * * * *"' in flow
assert "environment: alumno-3c" in flow
assert "vars.LAB_END_UTC" in flow
assert "vars.DATABRICKS_CLIENT_ID" in flow
assert "vars.DATABRICKS_HOST" in flow
assert 'https://dbc-77f7771e-2520.cloud.databricks.com' in flow
assert "databricks apps stop" in flow
assert "databricks apps get" in flow
assert "databricks apps start" not in flow
assert "app-state" not in flow
assert "asistente-cloud-erp-alumno" in flow
assert "asistente-cloud-erp-7474651957738908" not in flow
assert "dbc-a1aca8aa-28bd" not in flow
assert "APP=asistente-cloud-erp-alumno" in flow
assert 'state != "STOPPED"' in flow
assert "configured=false" in flow

assert "ValidateRange(1, 168)" in ps
assert "-Ejecutar" in ps and "GuardVerificado" in ps
assert "alumno-lab-expiry-guard.yml" in ps
assert "LAB_STARTED_UTC" in ps and "LAB_END_UTC" in ps and "LAB_STOPPED_UTC" in ps
assert "asistente-cloud-erp-alumno" in ps
assert "databricks apps start" in ps and "databricks apps stop" in ps
assert "profile" in ps and "alumno-3c" in ps
assert "--env alumno-3c" in ps
assert "--env prod" not in ps
assert "databricks bundle" not in ps
assert "ALLOW_SHEET_WRITE" not in ps

assert "system.billing.usage" in sql
assert "billing_origin_product = 'APPS'" in sql
assert "usage_metadata.app_name = 'asistente-cloud-erp-alumno'" in sql
assert "DATE_TRUNC('HOUR', usage_start_time)" in sql
assert "JOIN student_workspace" in sql
assert not re.search(r"\b(drop|delete|truncate|insert|update|merge)\s+(into|from|table|system\.)", sql, flags=re.I)

assert "cron" in doc and "14 dias" in doc and "84 DBU" in doc
assert "alumno-3c" in doc
assert "databricks bundle deploy --target prod" in base_flow
assert "dbc-a1aca8aa-28bd.cloud.databricks.com" not in flow
assert "dbc-a1aca8aa-28bd.cloud.databricks.com" in (ROOT / "databricks.yml").read_text(encoding="utf-8"), "Original deploy must remain untouched"
print("Student lab expiry guard, planned horometer and billing SQL: PASS")
