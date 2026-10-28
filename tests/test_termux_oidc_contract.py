from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP = (ROOT / "scripts/setup-alumno-oidc-termux.sh").read_text(encoding="utf-8")
INSTALL = (ROOT / "scripts/INSTALAR-TERMUX-ALUMNO.sh").read_text(encoding="utf-8")


def test_termux_student_isolation_and_authentication():
    assert 'ACC=\'e6cf2e56-e1fa-464b-91b0-39517832bde0\'' in SETUP
    assert 'WS=\'7474657268940105\'' in SETUP
    assert 'SPNAME=\'github-actions-alumno-3c\'' in SETUP
    assert 'HOST=\'https://dbc-77f7771e-2520.cloud.databricks.com\'' in SETUP
    assert "dbc-a1aca8aa-28bd.cloud.databricks.com" not in SETUP
    assert "MODE='check'" in SETUP
    assert 'CONFIGURAR-ALUMNO' in SETUP


def test_termux_identity_is_generated_not_invented():
    assert 'service-principals-v2 create --display-name "$SPNAME"' in SETUP
    assert 'create --application-id' not in SETUP
    assert "workspace-assignment update" in SETUP
    assert "service-principal-federation-policy create" in SETUP
    assert 'OIDC' in SETUP
    assert "DATABRICKS_CLIENT_ID" in SETUP
    assert '--env prod' in SETUP
    assert 'action=status' in SETUP
    assert 'action=start' not in SETUP
    assert 'databricks apps start' not in SETUP


def test_termux_linux_container_not_unsafe_android_binary():
    assert 'proot-distro install ubuntu:24.04' in INSTALL
    assert 'databricks/cli/releases/latest' in INSTALL
    assert 'linux_$arch.zip' in INSTALL
    assert 'pkg install -y proot-distro' in INSTALL
    assert 'databricks auth login --host https://accounts.cloud.databricks.com' in INSTALL
    assert "termux-open-url" in INSTALL


def test_termux_bash_installs_first_and_has_required_packages():
    # Termux packages are staged before any PRoot Ubuntu installation.
    assert "pkg update -y" in INSTALL
    assert "pkg install -y bash" in INSTALL
    assert INSTALL.index("pkg install -y bash") < INSTALL.index("pkg install -y proot-distro")
    assert INSTALL.index("pkg install -y proot-distro") < INSTALL.index("proot-distro install ubuntu:24.04")
    for package in ("ca-certificates", "openssl", "coreutils", "findutils", "grep", "sed", "tar", "gzip", "unzip", "curl", "jq", "git"):
        assert package in INSTALL
    for linux_tool in ("bash", "curl", "jq", "unzip", "git", "gh", "openssl", "python3"):
        assert linux_tool in INSTALL
    assert "apt-get install -y bash ca-certificates" in INSTALL
    assert "bash -n /root/Alumno3C/setup-alumno-oidc-termux.sh" in INSTALL
    assert "databricks apps start" not in INSTALL
    assert "action=start" not in INSTALL


def test_termux_repairs_interrupted_dpkg_before_pkg():
    assert "dpkg --configure -a" in INSTALL
    assert INSTALL.index("dpkg --configure -a") < INSTALL.index("pkg update -y")
    assert INSTALL.index("pkg update -y") < INSTALL.index("pkg install -y bash")
    assert "pkg install -y bash" in INSTALL
    assert "proot-distro list -q" in INSTALL
    assert "pkg install -y proot-distro" in INSTALL
    assert "termux-tools" in INSTALL and "python" in INSTALL
    assert "rm -f /var/lib/dpkg/lock" not in INSTALL
    assert "databricks apps start" not in INSTALL
    assert "action=start" not in INSTALL


def test_doc_has_one_safe_dpkg_first_copy_paste_command():
    guide = (ROOT / "docs/TERMUX_CONFIG_ALUMNO_CLOUD.md").read_text(encoding="utf-8")
    assert "dpkg --configure -a && pkg update -y" in guide
    assert "bash -o pipefail -c" in guide
    assert "INSTALAR-TERMUX-ALUMNO.sh" in guide
