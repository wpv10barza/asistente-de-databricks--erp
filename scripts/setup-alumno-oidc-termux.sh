#!/usr/bin/env bash
# Safe account+workspace GitHub OIDC bootstrap from Linux (Termux PRoot Ubuntu).
# Read-only by default. --apply writes ONLY to verified student account/workspace.
set -Eeuo pipefail
umask 077
ACC='e6cf2e56-e1fa-464b-91b0-39517832bde0'
WS='7474657268940105'
HOST='https://dbc-77f7771e-2520.cloud.databricks.com'
DEPLOY='dbc-77f7771e-2520'
APP='asistente-cloud-erp-alumno'
SPNAME='github-actions-alumno-3c'
POLICY='github-actions-alumno-prod'
SUBJECT='repo:wpv10barza@181611197/asistente-de-databricks--erp@1410769928:environment:prod'
ISSUER='https://token.actions.githubusercontent.com'
GHREPO='wpv10barza/asistente-de-databricks--erp'
ACCOUNT_PROFILE='alumno-cuenta-3c'
WORKSPACE_PROFILE='alumno-3c'
MODE='check'
STATUS=0
usage() {
  cat <<'TXT'
Uso: bash setup-alumno-oidc-termux.sh [--apply] [--status]
  Por defecto solo lectura. --apply modifica cuenta alumno/GitHub prod.
  --status solo solicita status (NO start) y requiere --apply.
Autentica antes:
 databricks auth login --host https://accounts.cloud.databricks.com --account-id e6cf2e56-e1fa-464b-91b0-39517832bde0 --profile alumno-cuenta-3c
 databricks auth login --host https://dbc-77f7771e-2520.cloud.databricks.com --profile alumno-3c
 gh auth login
TXT
}
for opt in "$@"; do
 case "$opt" in
 --apply) MODE='apply';;
 --status) STATUS=1;;
 -h|--help) usage;exit 0;;
 *) echo "Opcion desconocida: $opt" >&2;usage;exit 2;;
 esac
done
[[ "$STATUS" == 0 || "$MODE" == apply ]] || { echo '--status requiere --apply' >&2;exit 2; }
for exe in databricks jq; do command -v "$exe" >/dev/null || { echo "Falta $exe en Ubuntu" >&2;exit 3; };done
if [[ "$MODE" == apply ]];then command -v gh >/dev/null || { echo 'Falta gh CLI en Ubuntu' >&2;exit 3; };fi
TMPDIR_RUN="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_RUN"' EXIT
fail(){ echo "DETENIDO sin START: $*" >&2;exit 1; }
get(){ jq -r "$1" <<<"$2"; }
run_json(){
 local value
 if ! value="$("$@")";then fail "Falló Databricks CLI; revisa mensaje/permiso anterior";fi
 jq -e . >/dev/null 2>&1 <<<"$value" || fail 'Respuesta no es JSON'
 printf '%s' "$value"
}
ac(){ run_json databricks account "$@" --profile "$ACCOUNT_PROFILE" --output json; }
ws(){ run_json databricks "$@" --profile "$WORKSPACE_PROFILE" --output json; }
write_json(){ printf '%s\n' "$2" > "$TMPDIR_RUN/$1";chmod 600 "$TMPDIR_RUN/$1"; }
echo '== Validacion ESTRICTA cuenta+workspace del alumno (sin PC) =='
echo "Account $ACC | Workspace $WS | App $APP"
account_desc="$(databricks auth describe --profile "$ACCOUNT_PROFILE" 2>&1)" || fail "No autenticado en cuenta alumna: $account_desc"
[[ "$account_desc" == *'accounts.cloud.databricks.com'* && "$account_desc" == *"$ACC"* ]] || fail 'El perfil de cuenta no prueba el Account ID esperado'
workspace_desc="$(databricks auth describe --profile "$WORKSPACE_PROFILE" 2>&1)" || fail "No autenticado en workspace alumno: $workspace_desc"
[[ "$workspace_desc" == *"$HOST"* ]] || fail 'Perfil workspace distinto del alumno'
wsmeta="$(ac workspaces get "$WS")"
[[ "$(get '.workspace_id // .workspaceId // "" | tostring' "$wsmeta")" == "$WS" ]] || fail 'Workspace ID equivocado'
actual_deployment="$(get '.deployment_name // .deploymentName // ""' "$wsmeta")"
[[ "$actual_deployment" == *"$DEPLOY"* ]] || fail 'Deployment distinto del alumno'
actual_url="$(get '.workspace_url // .workspaceUrl // ""' "$wsmeta")"
[[ -z "$actual_url" || "$actual_url" == *"dbc-77f7771e-2520.cloud.databricks.com"* ]] || fail 'URL workspace incorrecta'
appmeta="$(ws apps get "$APP")"
[[ "$(get '.name // ""' "$appmeta")" == "$APP" ]] || fail 'Nombre App no corresponde'
echo '[OK] Cuenta, workspace y App alumno confirmados.'
principals="$(ac service-principals-v2 list --filter "displayName eq \"$SPNAME\"" --limit 100)"
# Databricks CLI may emit a ROOT JSON ARRAY (as on the Android phone), not
# only SCIM envelope objects. Never access .Resources/.next_page_token on [].
principal_page="$(jq -er 'if type=="array" then "" elif type=="object" then (.next_page_token // .nextPageToken // "") else error("unexpected principal list type") end' <<<"$principals")" || fail 'Tipo inesperado de lista de principals'
[[ -z "$principal_page" ]] || fail 'Principals paginados; revisar manual'
principal_items="$(jq -ec 'if type=="array" then . elif type=="object" then (.Resources // .resources // .service_principals // .servicePrincipals // error("missing principal collection")) else error("unexpected principal collection") end | if type=="array" then . else error("principal collection must be array") end' <<<"$principals")" || fail 'Lista de principals con formato desconocido'
# If SCIM explicitly reports more results than returned, never create an
# identity on an incomplete result set.
principal_total="$(jq -r 'if type=="object" then (.totalResults // .total_results // -1) else -1 end' <<<"$principals")"
[[ "$principal_total" == -1 || "$principal_total" -le "$(jq 'length' <<<"$principal_items")" ]] || fail 'Principals SCIM incompletos; no crear duplicados'
matches="$(jq -c --arg n "$SPNAME" 'map(select((.display_name // .displayName // "")==$n))' <<<"$principal_items")"
count="$(jq 'length' <<<"$matches")"
[[ "$count" -le 1 ]] || fail 'Principals duplicados, no crearé otro'
principal=''
if [[ "$count" == 1 ]];then principal="$(jq -c '.[0]' <<<"$matches")";echo "[OK] Reutilizando $SPNAME";else echo "[PENDIENTE] Crear $SPNAME";fi
echo "OIDC subject=$SUBJECT"
echo "OIDC audience=$ACC"
if [[ "$MODE" != apply ]];then echo '[SOLO LECTURA] No se modificó ninguna identidad, App ni Github';exit 0;fi
gh auth status >/dev/null 2>&1 || fail 'Falta gh auth login y permiso sobre repo'
printf 'Va a modificar SOLO cuenta ALUMNA. Escribe CONFIGURAR-ALUMNO para confirmar: '
read -r confirm
[[ "$confirm" == 'CONFIGURAR-ALUMNO' ]] || fail 'Operación cancelada'
if [[ -z "$principal" ]];then
 echo "[APPLY] Crear $SPNAME SIN applicationID"
 created="$(ac service-principals-v2 create --display-name "$SPNAME")"
 principal="$(jq -c '.service_principal // .servicePrincipal // .' <<<"$created")"
fi
spid="$(get '.service_principal_id // .servicePrincipalId // .id // "" | tostring' "$principal")"
client="$(get '.application_id // .applicationId // ""' "$principal")"
[[ "$spid" =~ ^[0-9]+$ ]] || fail 'SP ID no numérico; revisar antes de repetir (puede haber sido creado)'
[[ "$client" =~ ^[0-9a-fA-F-]{36}$ ]] || fail 'Application ID no válido; revisar antes de repetir'
sp_account="$(get '.account_id // .accountId // ""' "$principal")"
[[ -z "$sp_account" || "$sp_account" == "$ACC" ]] || fail 'Principal de cuenta distinta'
echo "[OK] Principal id=$spid, Application ID=$client"
write_json assign '{"permissions":["USER"]}'
ac workspace-assignment update "$WS" "$spid" --json "@$TMPDIR_RUN/assign" >/dev/null
policies="$(ac service-principal-federation-policy list "$spid")"
policy_page="$(jq -er 'if type=="array" then "" elif type=="object" then (.next_page_token // .nextPageToken // "") else error("unexpected policy list type") end' <<<"$policies")" || fail 'Tipo inesperado de lista de políticas'
[[ -z "$policy_page" ]] || fail 'Policies paginadas, revisar manual'
policy_items="$(jq -ec 'if type=="array" then . elif type=="object" then (.policies // error("missing policy collection")) else error("unexpected policy collection") end | if type=="array" then . else error("policy collection must be array") end' <<<"$policies")" || fail 'Políticas con formato desconocido'
pmatches="$(jq -c --arg n "$POLICY" 'map(select((.policy_id // .policyId // "")==$n))' <<<"$policy_items")"
[[ "$(jq 'length' <<<"$pmatches")" -le 1 ]] || fail 'Policies duplicadas'
if [[ "$(jq 'length' <<<"$pmatches")" == 0 ]];then
 policy_json="$(jq -nc --arg i "$ISSUER" --arg a "$ACC" --arg s "$SUBJECT" '{oidc_policy:{issuer:$i,audiences:[$a],subject:$s}}')"
 write_json policy "$policy_json"
 ac service-principal-federation-policy create "$spid" --policy-id "$POLICY" --json "@$TMPDIR_RUN/policy" >/dev/null
fi
confirmed="$(ac service-principal-federation-policy get "$spid" "$POLICY")"
matches_expected="$(jq -r --arg iss "$ISSUER" --arg subj "$SUBJECT" --arg aud "$ACC" '(.oidc_policy // .oidcPolicy // {}) as $p | ($p.issuer==$iss and $p.subject==$subj and (($p.audiences // []) | index($aud) != null))' <<<"$confirmed")"
[[ "$matches_expected" == true ]] || fail 'La política OIDC no coincide; NO reemplazo'
echo '[OK] Federación de GitHub OIDC verificada'
acl="$(jq -nc --arg cid "$client" '{access_control_list:[{service_principal_name:$cid,permission_level:"CAN_MANAGE"},{user_name:"polovaleriow@gmail.com",permission_level:"CAN_USE"},{user_name:"wpvbar11@gmail.com",permission_level:"CAN_MANAGE"}]}')"
write_json acl "$acl"
ws apps update-permissions "$APP" --json "@$TMPDIR_RUN/acl" >/dev/null
ws apps get-permissions "$APP" >/dev/null
gh variable set DATABRICKS_CLIENT_ID --repo "$GHREPO" --env prod --body "$client"
echo '[OK] Configurado: ninguna App se ha iniciado; solo se cambió la identidad y ACL del alumno'
if [[ "$STATUS" == 1 ]];then
 gh workflow run alumno-cloud-control.yml -R "$GHREPO" --ref main -f action=status
 echo '[STATUS] Solicitado. Consultar resultado en GitHub Actions'
fi
echo "GitHub https://github.com/$GHREPO/actions/workflows/alumno-cloud-control.yml"
echo "Nuevo Application ID (no secreto)=$client"
