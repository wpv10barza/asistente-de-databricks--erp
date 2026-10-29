from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP = (ROOT / "scripts/setup-alumno-oidc-termux.sh").read_text(encoding="utf-8")
CTRL = (ROOT / "scripts/termux-ota-cloud-control.sh").read_text(encoding="utf-8")


def test_git_oidc_workspace_entitlement_explicit_and_scoped():
    assert '/api/2.0/identity/accounts/$ACC/workspaces/$WS/workspace-assignments/$spid' in SETUP
    assert 'WORKSPACE_ACCESS' in SETUP
    assert 'update_mask=entitlements' in SETUP
    assert '(.entitlements // []) + ["WORKSPACE_ACCESS"] | unique' in SETUP
    assert 'confirmed_access=' in SETUP
    assert "dbc-a1aca8aa-28bd.cloud.databricks.com" not in SETUP
    assert 'action=start' not in SETUP


def test_firmware_verification_and_gated_termux_start():
    assert 'ota-59073909' in CTRL
    assert 'firmware.bin' in CTRL and 'manifest.json' in CTRL
    assert 'DATABRICKS_CLIENT_ID' in CTRL
    assert '439d8e37-d5ac-4910-adc6-0eccf1a8db94' in CTRL
    assert '.conclusion=="success"' in CTRL
    assert 'ENCENDER-ALUMNO' in CTRL
    assert 'gh workflow run alumno-cloud-control.yml' in CTRL
    assert 'action=start' in CTRL and 'action=status' in CTRL
    assert "databricks apps start" not in CTRL
    assert "databricks apps deploy" not in CTRL
    assert "erase_flash" not in CTRL
    assert "dbc-a1aca8aa-28bd.cloud.databricks.com" not in CTRL


def test_start_requires_latest_successful_status_and_main_sha():
    assert 'gh run view "$run_id"' in CTRL
    assert 'main_sha="$(gh api' in CTRL
    assert '.headSha==$sha' in CTRL
    assert 'Estado actual (sin cambios ni inicio de compute)' in CTRL
    assert 'action=start' in CTRL
