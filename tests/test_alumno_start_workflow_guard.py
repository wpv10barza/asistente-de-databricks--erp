"""Static guardrails: CI cannot silently mutate student compute."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CONTROL=(ROOT/".github/workflows/alumno-cloud-control.yml").read_text()
CI=(ROOT/".github/workflows/ci.yml").read_text()
LEGACY=(ROOT/".github/workflows/deploy-databricks.yml").read_text()

def test_student_start_enforces_status_on_current_main():
    assert "actions: read" in CONTROL
    assert "START exige ultimo STATUS de main" in CONTROL
    assert "github.token" in CONTROL
    assert '(.head_sha == $sha)' in CONTROL
    assert "Estado actual (sin cambios ni inicio de compute)" in CONTROL
    assert "ejecucion previa realizo una accion de escritura" in CONTROL
    assert 'GITHUB_REF' in CONTROL
    assert 'databricks apps deploy "$STUDENT_APP" --git-branch main' in CONTROL

def test_ci_has_no_databricks_remote_compute_commands():
    for command in ("databricks apps start", "databricks apps deploy",
                    "databricks bundle deploy","databricks bundle run",
                    "databricks clusters create", "databricks jobs run-now"):
        assert command not in CI
    assert "workflow_dispatch:" not in CI
    assert "pytest" in CI

def test_legacy_deploy_requires_explicit_dispatch_from_main():
    assert "workflow_dispatch:" in LEGACY
    assert "push:" not in LEGACY
    assert "schedule:" not in LEGACY
    assert '[[ "$GITHUB_REF" == \'refs/heads/main\' ]]' in LEGACY
