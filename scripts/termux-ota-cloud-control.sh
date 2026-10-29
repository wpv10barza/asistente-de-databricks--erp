#!/usr/bin/env bash
# Mobile Ubuntu/Termux control: FOTA verification and student Databricks START.
# Does not flash ESP32, edit firmware, use original workspace, or bypass OIDC.
set -Eeuo pipefail
REPO='wpv10barza/asistente-de-databricks--erp'
FW='wpv10barza/erp-mantto-esp32'
FW_TAG='ota-59073909'
FW_SHA='59073909f073d71c8b9a05c3f288f47056985fa2'
APP='asistente-cloud-erp-alumno'
CLIENT='439d8e37-d5ac-4910-adc6-0eccf1a8db94'
ACTION='check'
if [[ "$#" -gt 0 ]]; then ACTION="$1"; fi
fail() { echo "DETENIDO: $*" >&2;exit 1; }
for exe in gh curl jq; do command -v "$exe" >/dev/null || fail "Falta $exe. Entra a Ubuntu." ;done
[[ "$ACTION" == check || "$ACTION" == start || "$ACTION" == status ]] || fail 'Uso: bash termux-ota-cloud-control.sh {check|status|start}'
echo '== FOTA GitHub 2.7.7 independiente de Databricks =='
release="$(curl -fsSL --retry 3 "https://api.github.com/repos/$FW/releases/tags/$FW_TAG")" || fail 'Release FOTA no accesible'
jq -e --arg tag "$FW_TAG" --arg sha "$FW_SHA" '.tag_name==$tag and (.target_commitish == $sha or .target_commitish == "main" or .target_commitish == null) and ([.assets[].name] | (index("firmware.bin")!=null and index("manifest.json")!=null))' <<<"$release" >/dev/null || fail 'Firmware FOTA no publicado o sin assets'
echo "[OK] firmware.bin y manifest.json del release $FW_TAG (version 2.7.9) publicados."
echo 'Instalacion FOTA: en pantalla ESP32 seleccionar 59073909; si HTTPS falla con -1, USB sin borrar NVS.'
echo "Release: https://github.com/$FW/releases/tag/$FW_TAG"
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
jq -e '.[0].status=="completed" and .[0].conclusion=="success" and (.[0].databaseId | type == "number")' <<<"$run" >/dev/null || fail 'El ultimo control no termino SUCCESS: ejecutar STATUS primero'
run_id="$(jq -er '.[0].databaseId' <<<"$run")"
details="$(gh run view "$run_id" -R "$REPO" --json headSha,headBranch,event,status,conclusion,jobs)" || fail 'No se pudieron verificar los pasos del ultimo run'
main_sha="$(gh api "repos/$REPO/commits/main" --jq '.sha')" || fail 'No se pudo leer SHA main'
jq -e --arg sha "$main_sha" '.headSha==$sha and .headBranch=="main" and .event=="workflow_dispatch" and .status=="completed" and .conclusion=="success" and ([.jobs[]?.steps[]? | select(.name=="Estado actual (sin cambios ni inicio de compute)" and .conclusion=="success")] | length > 0) and ([.jobs[]?.steps[]? | select(.conclusion=="success" and (.name | test("^(Iniciar App|Detener App|Desplegar solo|Otorgar acceso)")))] | length == 0)' <<<"$details" >/dev/null || fail 'START bloqueado: ultimo run no es STATUS exitoso del HEAD actual de main'
echo "[AVISO] START de $APP puede consumir créditos de Databricks (solo workspace alumno)."
printf 'Escribe ENCENDER-ALUMNO para confirmar: '
read -r answer
[[ "$answer" == 'ENCENDER-ALUMNO' ]] || fail 'START cancelado'
gh workflow run alumno-cloud-control.yml -R "$REPO" --ref main -f action=start
echo '[ENVIADO] START solicitado. Verifica su resultado en GitHub Actions.'
echo "https://github.com/$REPO/actions/workflows/alumno-cloud-control.yml"
