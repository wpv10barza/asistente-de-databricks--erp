#!/data/data/com.termux/files/usr/bin/bash
# Android Termux bootstrap for a supported Linux Databricks CLI inside Ubuntu PRoot.
# Does NOT authenticate/create service principals/start Databricks Apps.
set -Eeuo pipefail
command -v pkg >/dev/null || { echo 'Ejecutar en Termux nativo (Android), no Ubuntu' >&2; exit 1; }
echo '== Configurando Termux y Ubuntu para Databricks ALUMNO =='
pkg update -y
pkg install -y proot-distro curl jq git
if ! proot-distro list --installed 2>/dev/null | grep -Eqi 'ubuntu'; then
  proot-distro install ubuntu:24.04
fi
proot-distro login ubuntu -- bash -lc 'set -e; apt-get update; DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl jq unzip gh; mkdir -p /root/Alumno3C'
proot-distro login ubuntu -- bash -lc '
set -Eeuo pipefail
arch="$(uname -m)"
case "$arch" in aarch64|arm64) arch=arm64;; x86_64|amd64) arch=amd64;; *) echo "Arquitectura no admitida: $arch" >&2; exit 1;; esac
url="$(curl -fsSL https://api.github.com/repos/databricks/cli/releases/latest | jq -r --arg suffix "linux_$arch.zip" ".assets[] | select(.name | endswith(\$suffix)) | .browser_download_url" | head -n 1)"
if [[ -z "$url" || "$url" == null || "$url" != https://github.com/databricks/cli/releases/download/* ]]; then
  echo "No hay ZIP oficial Linux $arch. Abrir https://github.com/databricks/cli/releases" >&2
  exit 1
fi
curl -fL "$url" -o /tmp/databricks-cli.zip
unzip -o /tmp/databricks-cli.zip databricks -d /usr/local/bin >/dev/null
chmod +x /usr/local/bin/databricks
rm -f /tmp/databricks-cli.zip
databricks -v
'
proot-distro login ubuntu -- bash -lc 'curl -fLsS https://raw.githubusercontent.com/wpv10barza/asistente-de-databricks--erp/main/scripts/setup-alumno-oidc-termux.sh -o /root/Alumno3C/setup-alumno-oidc-termux.sh; chmod 700 /root/Alumno3C/setup-alumno-oidc-termux.sh; bash -n /root/Alumno3C/setup-alumno-oidc-termux.sh'
cat <<'TXT'

== Instalación en Android completada (sin iniciar cómputo) ==
En Termux entra a Ubuntu:
  proot-distro login ubuntu

Dentro de Ubuntu autentícate (administrador de la cuenta ALUMNA):
  databricks auth login --host https://accounts.cloud.databricks.com --account-id e6cf2e56-e1fa-464b-91b0-39517832bde0 --profile alumno-cuenta-3c
  databricks auth login --host https://dbc-77f7771e-2520.cloud.databricks.com --profile alumno-3c
  gh auth login

Verificación SIN MODIFICAR:
  bash /root/Alumno3C/setup-alumno-oidc-termux.sh

Después, solo si el administrador autoriza los cambios:
  bash /root/Alumno3C/setup-alumno-oidc-termux.sh --apply --status

Para abrir GitHub en el navegador móvil: salir de Ubuntu (exit), y ejecutar:
  termux-open-url 'https://github.com/wpv10barza/asistente-de-databricks--erp/actions/workflows/alumno-cloud-control.yml'

NUNCA coloca contraseñas de Databricks en el firmware. NO ejecuta start/redeploy.
TXT
