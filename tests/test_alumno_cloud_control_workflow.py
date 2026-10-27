"""Control académico GitHub OIDC: no tocar workspace original ni iniciar compute en CI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/alumno-cloud-control.yml").read_text(encoding="utf-8")


def test_student_workspace_is_locked_and_auth_is_explicit():
    assert "DATABRICKS_HOST: https://dbc-77f7771e-2520.cloud.databricks.com" in WORKFLOW
    assert "vars.DATABRICKS_HOST" not in WORKFLOW
    assert "dbc-a1aca8aa-28bd.cloud.databricks.com" not in WORKFLOW
    assert "asistente-databricks-erp" not in WORKFLOW
    assert "STUDENT_APP: asistente-cloud-erp-alumno" in WORKFLOW
    assert "DATABRICKS_AUTH_TYPE: github-oidc" in WORKFLOW
    assert "DATABRICKS_CLIENT_ID: ${{ vars.DATABRICKS_CLIENT_ID }}" in WORKFLOW
    assert "environment: prod" in WORKFLOW
    assert '[[ "$GITHUB_REF" != "refs/heads/main" ]]' in WORKFLOW
    assert "id-token: write" in WORKFLOW


def test_actions_are_manual_fast_and_redeploy_checks_git_only_when_needed():
    assert "workflow_dispatch:" in WORKFLOW
    assert "schedule:" not in WORKFLOW
    assert "push:" not in WORKFLOW
    for action in ("status", "start", "stop", "redeploy", "grant_access"):
        assert f"- {action}" in WORKFLOW
    assert 'os.environ["ACTION"] == "redeploy"' in WORKFLOW
    assert "databricks apps start" in WORKFLOW
    assert "databricks apps stop" in WORKFLOW
    assert 'databricks apps deploy "$STUDENT_APP" --git-branch main' in WORKFLOW
    assert "databricks current-user me --output json" in WORKFLOW
    assert "PlatformIO" not in WORKFLOW
    assert "firmware-cd.yml" not in WORKFLOW


def test_acl_and_error_messages_keep_personal_login_with_databricks():
    assert '"polovaleriow@gmail.com", "permission_level": "CAN_USE"' in WORKFLOW
    assert '"wpvbar11@gmail.com", "permission_level": "CAN_MANAGE"' in WORKFLOW
    assert "databricks apps update-permissions" in WORKFLOW
    assert "databricks apps set-permissions" not in WORKFLOW
    assert "Application ID REAL" in WORKFLOW
    assert "Falta GitHub Settings > Environments > prod" in WORKFLOW
    assert "START/REDEPLOY pueden generar consumo" in WORKFLOW
