#!/usr/bin/env bash
# Mobile Ubuntu/Termux control: FOTA verification and student Databricks START.
# Does not flash ESP32, edit firmware, use original workspace, or bypass OIDC.
set -Eeuo pipefail
REPO='wpv10barza/asistente-de-databricks--erp'
FW='wpv10barza/erp-mantto-esp32'
APP='asistente-cloud-erp-alumno'
CLIENT='439d8e37-d5ac-4910-adc6-0eccf1a8db94'
ACTION='check'
if [[ "$#" -gt 0 ]]; then ACTION="$1"; fi
fail() { echo "DETENIDO: $*" >&2;exit 1; }
for exe in gh curl jq; do command -v "$exe" >/dev/null || fail "Falta $exe. Entra a Ubuntu." ;done
[[ "$ACTION" == check || "$ACTION" == start || "$ACTION" == status ]] || fail 'Uso: bash termux-ota-cloud-control.sh {check|status|start}'
echo '== FOTA GitHub 2.7.7 independiente de Databricks =='
release="$(curl -fsSL --retry 3 "https://api.github.com/repos/$FW/releases/tags/ota-d400e8c1")" || fail 'Release FOTA no accesible'
jq -e '.tag_name=="ota-d400e8c1" and ([.assets[].name] | (index("firmware.bin")!=null and index("manifest.json")!=null))' <<<"$release" >/dev/null || fail 'Firmware FOTA no publicado'
echo '[OK] firmware.bin y manifest.json del commit d400e8c1 disponibles.'
echo 'Instalacion FOTA: desde pantalla ESP32 con Wi-Fi 2.4 GHz + hora NTP valida, seleccionar d400e8c1.'
echo "Release: https://github.com/$FW/releases/tag/ota-d400e8c1"
gh auth status >/dev/null 2>&1 || fail 'GitHub no autenticado: gh auth login'
variable="$(gh variable list --env prod -R "$REPO" --json name,value --jq '.[]|select(.name=="DATABRICKS_CLIENT_ID")|.value')" || fail 'No se pudo consultar variable GitHub prod'
[[ "$variable" == "$CLIENT" ]] || fail 'DATABRICKS_CLIENT_ID no coincide con identidad de GitHub OIDC alumno'
if [[ "$ACTION" == status ]]; then
  echo '[STATUS] Consultando GitHub Actions sin encender Databricks.'
  gh workflow run alumno-cloud-control.yml -R "$REPO" --ref main -f action=status
  echo "https://github.com/$REPO/actions/workflows/alumno-cloud-control.yml"
  exit 0
fi
run="$(gh run list -R "$REPO" --workflow alumno-cloud-control.yml --branch main --limit 1 --json databaseId,status,conclusion,createdAt)" || fail 'No se puede consultar GitHub Actions'
jq -r '.[0] // {} | "Ultima ejecución: run=\(.databaseId // "?") status=\(.status // "?") conclusion=\(.conclusion // "?")"' <<<"$run"
if [[ "$ACTION" == check ]];then
  echo '[SOLO LECTURA] Si status anterior fue FAILED, repara WORKSPACE_ACCESS antes de START.'
  exit 0
fi
jq -e '.[0].status=="completed" and .[0].conclusion=="success"' <<<"$run" >/dev/null || fail 'El último control GitHub no terminó SUCCESS: ejecutar status primero'
echo "[AVISO] START de $APP puede consumir créditos de Databricks (solo workspace alumno)."
printf 'Escribe ENCENDER-ALUMNO para confirmar: '
read -r answer
[[ "$answer" == 'ENCENDER-ALUMNO' ]] || fail 'START cancelado'
gh workflow run alumno-cloud-control.yml -R "$REPO" --ref main -f action=start
echo '[ENVIADO] START solicitado. Verifica su resultado en GitHub Actions.'
echo "https://github.com/$REPO/actions/workflows/alumno-cloud-control.yml"
