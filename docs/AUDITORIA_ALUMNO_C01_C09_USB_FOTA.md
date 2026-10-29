# Auditoría académica C01–C09, firmware 2.7.9 y recuperación USB

**Fecha:** 28/10/2026 (hora de Lima). **Modo por defecto: solo lectura**.
No ejecutar `start`, `stop`, `redeploy`, `grant_access`, `--apply`,
`gh workflow run`, `erase` ni flash sin decisión y autorización expresas.

## Evidencia histórica de GitHub, no inventada

- [STATUS 40765029948](https://github.com/wpv10barza/asistente-de-databricks--erp/actions/runs/40765029948): OIDC, App y estado leídos correctamente.
- [START 40765242660](https://github.com/wpv10barza/asistente-de-databricks--erp/actions/runs/40765242660): compute llegó a funcionar; puede haber consumo.
- [STOP 40770482153](https://github.com/wpv10barza/asistente-de-databricks--erp/actions/runs/40770482153): compute STOPPED al terminar.
- [CI 40753555286](https://github.com/wpv10barza/asistente-de-databricks--erp/actions/runs/40753555286): pruebas locales exitosas, sin desplegar Apps.

**Importante:** START ya NO acepta cualquier run `success`: primero el
último run completo del workflow debe ser un STATUS exitoso **sin acciones
de escritura**, del SHA actual de `main`. GitHub Actions también comprueba
este requisito justo antes de arrancar. Tras fusionar cambios a main se
necesitará un STATUS nuevo antes de un START autorizado. El modo `check`
solo consulta; el modo `status` **despacha** una ejecución GitHub de lectura.

## Identificadores que se deben contrastar (nunca asumir por documentación)

- Repo backend: `wpv10barza/asistente-de-databricks--erp`.
- Account alumno: `e6cf2e56-e1fa-464b-91b0-39517832bde0`.
- Workspace alumno: `7474657268940105`.
- Host alumno: `https://dbc-77f7771e-2520.cloud.databricks.com`.
- App alumno: `asistente-cloud-erp-alumno`.
- GitHub principal: `github-actions-alumno-3c`, policy `github-actions-alumno-prod`.
- GitHub environment: `prod` y rama `main`.

## Matriz y procedimientos estrictamente de lectura

| ID | Comprobación y evidencia | Criterio |
| --- | --- | --- |
| C01 | `databricks account workspaces get 7474657268940105 --profile alumno-cuenta-3c --output json` | ID, cuenta, URL y deployment académicos coinciden. |
| C02 | `databricks account service-principals-v2 list --filter 'displayName eq "github-actions-alumno-3c"' --profile alumno-cuenta-3c --output json`; consultar IAM v2 assignment del ID devuelto con GET | `WORKSPACE_ACCESS` directo o efectivo para el principal exacto, sin `WORKSPACE_ADMIN` si no está autorizado. |
| C03 | `databricks account service-principal-federation-policy get <SP_ID> github-actions-alumno-prod --profile alumno-cuenta-3c --output json`; cotejar con ejecución STATUS | Issuer, subject `environment:prod`, audience, Application ID y autenticación OIDC del mismo principal. |
| C04 | `databricks apps get-permissions asistente-cloud-erp-alumno --profile alumno-3c --output json` | Alumno `CAN_USE`, docente y principal control `CAN_MANAGE`, sin concesiones anónimas. Revisar permisos efectivos y otros grupos. |
| C05 | `databricks apps get asistente-cloud-erp-alumno --profile alumno-3c --output json` | Compute/estado, URL, despliegue Git, estado real. Prueba humana de SSO del alumno por separado. |
| C06 | `gh run list -R wpv10barza/asistente-de-databricks--erp --workflow alumno-cloud-control.yml --limit 20 --json databaseId,event,headBranch,headSha,conclusion` | Operaciones facturables solo `main`; comprobar reglas de environment y protección efectiva (no probado por un YAML). |
| C07 | Revisar `.github/workflows/ci.yml`, control y `deploy-databricks.yml`; comparar logs de Actions y auditoría de Databricks | CI de push/PR sin comandos `bundle deploy`, `apps start` ni computación remota; el workflow legacy es manual y también se restringió a main. |
| C08 | Account Console / Usage / Budgets y sistema `system.billing.usage` si ya existe SQL Warehouse encendido | Presupuesto/alertas y consumo real medidos; alertas no son tope duro. No encender warehouse solo para auditar. |
| C09 | [release FOTA 2.7.9](https://github.com/wpv10barza/erp-mantto-esp32/releases/tag/ota-59073909), CI y Firmware CD | Release con `manifest.json` y `firmware.bin` y SHA verificable, sin comando cloud ni flashing automático. |

En C02 se puede consultar únicamente con permiso de lectura:
```bash
databricks api get \
  "/api/2.0/identity/accounts/e6cf2e56-e1fa-464b-91b0-39517832bde0/workspaces/7474657268940105/workspace-assignments/<SP_ID>" \
  --profile alumno-cuenta-3c --output json
```

**¿El alumno tiene los mismos privilegios que el creador? No por diseño.**
La ACL declarada da al alumno `CAN_USE` y al docente `CAN_MANAGE`.
El creador también puede tener roles de administración de cuenta/workspace,
distintos de las ACL de App. Comparar membresías, grupos, entitlements,
ACL de App y propietario efectivo **por separado**. No elevar automáticamente
al alumno a `CAN_MANAGE`, ni a `WORKSPACE_ADMIN`, ni reutilizar credenciales
del creador: exigir autorización explícita y justificación de mínimo privilegio.

## Firmware ESP32-S3: recuperación USB

Existe el release **2.7.9** de [`59073909`](https://github.com/wpv10barza/erp-mantto-esp32/commit/59073909f073d71c8b9a05c3f288f47056985fa2).
El firmware agrega diagnóstico FOTA HTTPS `-1`, un reintento limitado
manteniendo TLS X.509 y campos locales de diagnóstico. La compilación y
publicación se validaron en GitHub, **no es prueba de flash físico**.

Equipo esperado: ESP32-S3-4848S040, 16 MB flash/PSRAM OPI,
PlatformIO `panel_4848s040` y particiones `partitions_ota_16mb.csv`.
Verificar visualmente variante y tamaño antes de flashear.

En Windows PowerShell con **cable USB de datos** y Python/Git instalados:
```powershell
py -m pip install --upgrade platformio==6.2.0
git clone https://github.com/wpv10barza/erp-mantto-esp32.git
cd erp-mantto-esp32
git checkout main
git pull --ff-only origin main
git rev-parse HEAD
.\scripts\Flash-ESP32-3C.ps1 -ListPorts
py -m platformio run -e panel_4848s040
.\scripts\Flash-ESP32-3C.ps1 -SerialSeconds 20
```
Si hay varios puertos, usar `-Port COMx -SerialSeconds 20` con el
puerto identificado. Requiere `include/local_config.h` local; NO registrar
credenciales en Git. Solo usar `-AllowMissingConfig` cuando las
credenciales NVS hayan sido verificadas previamente. **No usar `erase`**:
borra NVS. Verificar log de upload con exit 0, luego firmware 2.7.9 y
los campos `fota_last_http`, `fota_tls_error`, `fota_dns_github`
en `http://<IP_REAL_DEL_ESP32>/health` desde la red local.

### Próximas actualizaciones OTA

**Sí, normalmente por aire después del USB inicial**, si el dispositivo
conserva particiones OTA 16 MB, Wi-Fi 2.4 GHz, hora NTP válida, TLS hacia
GitHub, espacio de las ranuras OTA y manifest/firmware con SHA-256 válido.
Seleccionar SHA8 del release publicado en el menú FOTA y confirmar en el
panel. No se garantiza para todos los fallos: cable USB vuelve a ser
necesario si OTA/particiones, bootloader, memoria, Wi-Fi o TLS dejan de
funcionar, o cambia el diseño de particiones.

**Nada de esto instala firmware desde la App Databricks.** FOTA y control
GitHub cloud son flujos distintos; el ESP32 no necesita permisos de
administración Databricks.
