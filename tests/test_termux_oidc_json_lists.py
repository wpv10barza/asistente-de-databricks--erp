"""Regression: Databricks CLI emits raw JSON arrays as well as SCIM envelopes.

All Databricks/GitHub commands below are mocked: no real identities or Apps change.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "setup-alumno-oidc-termux.sh"
ACCOUNT = "e6cf2e56-e1fa-464b-91b0-39517832bde0"
HOST = "https://dbc-77f7771e-2520.cloud.databricks.com"
APP = "asistente-cloud-erp-alumno"
CLIENT = "6b0e842c-574f-455f-a623-951411efcc19"

MOCK_DATABRICKS = r"""#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
a=sys.argv[1:]
log=Path(os.environ["MOCK_LOG"])
with log.open("a",encoding="utf-8") as f: f.write("db "+" ".join(a)+"\n")
def out(x):
  print(json.dumps(x))
  sys.exit(0)
if a[:2]==["auth","describe"]:
  profile=a[a.index("--profile")+1]
  if profile=="alumno-cuenta-3c":
    print("host = https://accounts.cloud.databricks.com; account_id = e6cf2e56-e1fa-464b-91b0-39517832bde0")
  else:
    print("host = https://dbc-77f7771e-2520.cloud.databricks.com")
  sys.exit(0)
if a[:3]==["account","workspaces","get"]:
  out({"workspace_id":7474657268940105,"deployment_name":"dbc-77f7771e-2520"})
if a[:2]==["apps","get"]:
  out({"name":"asistente-cloud-erp-alumno"})
if a[:3]==["account","service-principals-v2","list"]:
  out(json.loads(os.environ["MOCK_PRINCIPALS"]))
if a[:3]==["account","service-principals-v2","create"]:
  out({"id":"12345","applicationId":"6b0e842c-574f-455f-a623-951411efcc19","displayName":"github-actions-alumno-3c"})
if a[:3]==["account","workspace-assignment","update"]:
  out({"status":"ok"})
if a[:2]==["api","get"] and "/workspace-assignments/" in a[2]:
  out({"principal_id":int(a[2].rstrip("/").split("/")[-1]),
       "workspace_id":7474657268940105,
       "account_id":"e6cf2e56-e1fa-464b-91b0-39517832bde0",
       "entitlements":json.loads(os.environ.get("MOCK_IAM_ENTITLEMENTS",'["WORKSPACE_ACCESS"]')),
       "effective_entitlements":[]})
if a[:2]==["api","patch"]:
  out({"status":"ok"})
if a[:3]==["account","service-principal-federation-policy","list"]:
  out(json.loads(os.environ.get("MOCK_POLICIES",'[]')))
if a[:3]==["account","service-principal-federation-policy","create"]:
  out({"policy_id":"github-actions-alumno-prod"})
if a[:3]==["account","service-principal-federation-policy","get"]:
  out({"oidc_policy":{"issuer":"https://token.actions.githubusercontent.com","audiences":["e6cf2e56-e1fa-464b-91b0-39517832bde0"],"subject":"repo:wpv10barza@181611197/asistente-de-databricks--erp@1410769928:environment:prod"}})
if a[:2]==["apps","update-permissions"]:
  out({"status":"ok"})
if a[:2]==["apps","get-permissions"]:
  out({"access_control_list":[]})
print("UNRECOGNIZED MOCK DATABRICKS CMD:",a,file=sys.stderr)
sys.exit(9)
"""
MOCK_GH = r"""#!/usr/bin/env python3
import os,sys
from pathlib import Path
with Path(os.environ["MOCK_LOG"]).open("a",encoding="utf-8") as f:
  f.write("gh "+" ".join(sys.argv[1:])+"\n")
"""


def run_mocked(tmp_path, principals, *arguments, policies=None, confirmation=""):
    if not shutil.which("jq"):
        pytest.skip("jq required to run the exact shell regression")
    bindir=tmp_path/"bin"
    bindir.mkdir()
    db=bindir/"databricks"
    db.write_text(MOCK_DATABRICKS,encoding="utf-8")
    db.chmod(0o755)
    gh=bindir/"gh"
    gh.write_text(MOCK_GH,encoding="utf-8")
    gh.chmod(0o755)
    log=tmp_path/"calls.log"
    env=os.environ.copy()
    env.update({
        "PATH":str(bindir)+os.pathsep+env.get("PATH",""),
        "MOCK_LOG":str(log),
        "MOCK_PRINCIPALS":json.dumps(principals),
        "MOCK_POLICIES":json.dumps([] if policies is None else policies),
        "MOCK_IAM_ENTITLEMENTS":json.dumps(["WORKSPACE_ACCESS"]),
    })
    p=subprocess.run(["bash",str(SCRIPT),*arguments],input=confirmation,
        capture_output=True,text=True,env=env,timeout=20)
    return p,log.read_text(encoding="utf-8") if log.exists() else ""


@pytest.mark.parametrize("data", [
    [],
    {"Resources":[],"totalResults":0},
    {"resources":[],"next_page_token":""},
    [{"id":"23456","applicationId":CLIENT,"displayName":"github-actions-alumno-3c"}],
    {"Resources":[{"id":"23456","applicationId":CLIENT,"displayName":"github-actions-alumno-3c"}],"totalResults":1},
])
def test_readonly_accepts_array_and_object_principal_lists(tmp_path,data):
    p,log=run_mocked(tmp_path,data)
    assert p.returncode==0,(p.stdout,p.stderr)
    assert "[OK] Cuenta, workspace y App alumno confirmados." in p.stdout
    assert "[SOLO LECTURA]" in p.stdout
    assert "service-principals-v2 create" not in log
    assert "workspace-assignment update" not in log
    assert "gh variable set" not in log


@pytest.mark.parametrize("data", [
    {"totally_unexpected":42},
    {"Resources":[],"next_page_token":"another-page"},
    {"Resources":[],"totalResults":3},
])
def test_fails_closed_on_unknown_or_incomplete_list(tmp_path,data):
    p,log=run_mocked(tmp_path,data,"--apply","--status",confirmation="CONFIGURAR-ALUMNO\n")
    assert p.returncode!=0
    assert "service-principals-v2 create" not in log
    assert "workspace-assignment update" not in log
    assert "gh workflow run" not in log


@pytest.mark.parametrize("policies", [
    [], {"policies":[],"next_page_token":""},
])
def test_apply_would_create_identity_and_dispatch_only_status_with_mocks(tmp_path,policies):
    p,log=run_mocked(tmp_path,[],"--apply","--status",policies=policies,
                     confirmation="CONFIGURAR-ALUMNO\n")
    assert p.returncode==0,(p.stdout,p.stderr)
    assert "service-principals-v2 create --display-name github-actions-alumno-3c" in log
    assert "service-principal-federation-policy create" in log
    assert "gh variable set DATABRICKS_CLIENT_ID" in log
    assert "gh workflow run alumno-cloud-control.yml" in log
    assert "action=status" in log
    assert "action=start" not in log
    assert "apps start" not in log
    assert "apps stop" not in log
    assert "apps deploy" not in log


def test_student_workspace_entitlement_grant_is_scoped_and_idempotent(tmp_path):
    p, log = run_mocked(tmp_path, [], "--apply", "--status",
                        policies=[], confirmation="CONFIGURAR-ALUMNO\n")
    assert p.returncode == 0, (p.stdout, p.stderr)
    assert 'api get /api/2.0/identity/accounts/e6cf2e56-e1fa-464b-91b0-39517832bde0/workspaces/7474657268940105/workspace-assignments/12345' in log
    assert "api patch" not in log  # pre-existing entitlement must be preserved
    assert "gh workflow run alumno-cloud-control.yml" in log
