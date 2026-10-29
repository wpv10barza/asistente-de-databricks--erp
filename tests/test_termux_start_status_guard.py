"""Behavioral regression: Termux must never dispatch START from an unrelated successful run."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "termux-ota-cloud-control.sh"
SHA = "d2d2e0c7b76781b200ec1d46b8294cc546e7be4f"
CLIENT = "439d8e37-d5ac-4910-adc6-0eccf1a8db94"

FAKE_GH = r"""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args=sys.argv[1:]
log=Path(os.environ["MOCK_LOG"])
with log.open("a") as f: f.write("gh "+" ".join(args)+"\n")
scenario=os.environ.get("MOCK_SCENARIO","status")
sha=os.environ["MOCK_SHA"]
if args[:2]==["auth","status"]: sys.exit(0)
if args[:2]==["variable","list"]:
    print(os.environ["MOCK_CLIENT"]);sys.exit(0)
if args[:2]==["run","list"]:
    print(json.dumps([{"databaseId":5678,"status":"completed","conclusion":"success","createdAt":"2026-10-28T23:00:00Z"}]));sys.exit(0)
if args[:2]==["run","view"]:
    step={"name":"Estado actual (sin cambios ni inicio de compute)" if scenario!="stop" else "Detener App (compute)", "conclusion":"success"}
    print(json.dumps({"headSha":sha if scenario!="stale" else "f"*40,
      "headBranch":"main","event":"workflow_dispatch","status":"completed","conclusion":"success",
      "jobs":[{"steps":[step]}]}));sys.exit(0)
if args[:1]==["api"]:
    print(sha);sys.exit(0)
if args[:2]==["workflow","run"]:
    print("dispatched");sys.exit(0)
print("UNKNOWN gh:",args,file=sys.stderr)
sys.exit(8)
"""
FAKE_CURL = r"""#!/usr/bin/env python3
import json
print(json.dumps({"tag_name":"ota-59073909","target_commitish":"main",
  "assets":[{"name":"firmware.bin"},{"name":"manifest.json"}]}))
"""

def execute(tmp_path, scenario="status", action="start", confirmation="ENCENDER-ALUMNO\n", client=CLIENT):
    if not shutil.which("jq"):
        pytest.skip("jq required")
    bin_dir=tmp_path/"bin"
    bin_dir.mkdir()
    for name, data in (("gh", FAKE_GH),("curl",FAKE_CURL)):
        file=bin_dir/name
        file.write_text(data)
        file.chmod(0o755)
    logfile=tmp_path/"calls.log"
    env=os.environ.copy()
    env.update({"PATH":str(bin_dir)+os.pathsep+env["PATH"],
      "MOCK_LOG":str(logfile),"MOCK_SCENARIO":scenario,
      "MOCK_SHA":SHA,"MOCK_CLIENT":client})
    run=subprocess.run(["bash",str(SCRIPT),action],input=confirmation,
      capture_output=True,text=True,timeout=15,env=env)
    return run, logfile.read_text() if logfile.exists() else ""

def test_check_is_readonly_and_uses_latest_fota(tmp_path):
    result,log=execute(tmp_path,action="check",confirmation="")
    assert result.returncode==0,(result.stdout,result.stderr)
    assert "ota-59073909" in result.stdout
    assert "gh workflow run" not in log
    assert "gh run view" not in log

@pytest.mark.parametrize("scenario",["stop","stale"])
def test_prior_stop_or_old_sha_cannot_authorize_start(tmp_path,scenario):
    result,log=execute(tmp_path,scenario=scenario)
    assert result.returncode!=0
    assert "START bloqueado" in result.stderr
    assert "gh workflow run" not in log

def test_exact_latest_status_requires_human_confirmation(tmp_path):
    result,log=execute(tmp_path,scenario="status",confirmation="NO\n")
    assert result.returncode!=0
    assert "gh workflow run" not in log

def test_exact_latest_status_can_dispatch_after_confirmation(tmp_path):
    result,log=execute(tmp_path,scenario="status")
    assert result.returncode==0,(result.stdout,result.stderr)
    assert "gh workflow run alumno-cloud-control.yml" in log
    assert "action=start" in log
    assert "databricks apps start" not in log

def test_mismatched_client_stops_before_check(tmp_path):
    result,log=execute(tmp_path,action="check",client="unrelated-client")
    assert result.returncode!=0
    assert "DATABRICKS_CLIENT_ID no coincide" in result.stderr
    assert "gh workflow run" not in log
