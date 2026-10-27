# Acceso academico y control cloud — solo alumno

**Objetivo:** el panel ESP32 permanece conectado a Databricks Apps en la nube; el PC del docente no necesita estar encendido. Los alumnos abren la pagina `/acceso` desde un movil o un navegador: https://asistente-cloud-erp-alumno-7474657268940105.aws.databricksapps.com/acceso

## Seguridad e identidades

- Cuenta alumno: `polovaleriow@gmail.com` — permiso `CAN_USE`.
- Cuenta docente: `wpvbar11@gmail.com` — permiso `CAN_MANAGE`.
- **No se almacena ninguna clave en firmware, repositorios ni formularios del backend.** Databricks autentica mediante SSO/OTP. Los dos usuarios deben estar dados de alta en la cuenta Databricks o aprovisionados por el IdP; agregar una ACL no les crea la cuenta.
- La autentificacion del ESP32 al Device API continua usando credenciales M2M y token de dispositivo, **independiente** de las cuentas personales.
- Si la App esta detenida, no puede reactivarse mediante su propio endpoint. El docente utiliza GitHub Actions autenticado o la consola de Databricks.
- **No usar** el workflow antiguo `deploy-databricks.yml` ni `databricks.yml` para la cuenta alumno: ambos apuntan al workspace/App original.
- El propietario de la cuenta debe configurar acceso restringido y proteccion del GitHub environment `prod`. Una persona con capacidad de aprobar/despachar workflows puede consumir recursos.

## Primer arranque seguro

1. En Databricks, asegure que **las dos cuentas existan**. Verifique la App `asistente-cloud-erp-alumno` y la configuracion OAuth, secretos y volumen. No modifique el workspace original.
2. En GitHub > Settings > Environments > `prod`, configure solo `DATABRICKS_CLIENT_ID=<Application ID real del service principal GitHub OIDC>`. **El host alumno esta fijado en el workflow:** `https://dbc-77f7771e-2520.cloud.databricks.com`. No copiar las variables o secretos del entorno original. El principal necesita federacion OIDC y `CAN MANAGE` sobre la App.
3. En [Alumno Cloud | Control rapido](https://github.com/wpv10barza/asistente-de-databricks--erp/actions/workflows/alumno-cloud-control.yml), seleccione `grant_access`. Esto usa `update-permissions` (incremental, no reemplaza la lista existente).
4. Seleccione `status`, `start`, `redeploy` o `stop` segun la necesidad. START usa el ultimo despliegue; redeploy usa `main` solo si cambió el backend.
5. Compruebe que alumno/profesor pueden entrar con sus propias identidades desde un navegador. Compruebe `/api/health` y Device API; verificar que `ALLOW_SHEET_WRITE=false`.

## Flujo recomendado durante 7 dias

- Inicio de cada jornada: docente ejecuta **start** desde su movil o PC.
- Fin de cada jornada: **stop** para evitar compute continuo cuando no se utiliza.
- No hay apagado automatico ni limite de DBU implementados: configurar alertas/budgets en Account Console y detener manualmente si se excede el presupuesto.
- El credito de prueba de 14 dias no se pausa cuando la App se detiene.
- GitHub Actions solo inicia el servicio cloud, **nunca necesita el PC encendido**. El despliegue completo y compilacion de firmware son procesos separados.
- Las pruebas de 7 dias deben registrar START/STOP y DBUs reales con `system.billing.usage`; un boton no reemplaza facturacion.

## Interfaz portátil ESP32

- `Conexion al backend` y `PROBAR CLOUD` verifican conectividad M2M. Un microcontrolador no debe solicitar ni guardar passwords institucionales.
- La pagina web `/acceso` es el portal para que alumno/docente entren autenticados. El panel sigue funcionando con su token de dispositivo.
- Si no responde, el docente inicia la App desde Actions antes de probar el panel.

## Despliegue rapido vs completo

- **status/start/stop/grant_access**: sin clonar repo, pytest, PlatformIO, firmware u OTA; su duracion depende de la transicion del servicio Databricks.
- **redeploy**: recompila/reinstala el entorno de App desde el Git conectado cuando haga falta; puede tardar minutos.
- El workflow `firmware-cd.yml` del repo `erp-mantto-esp32` se mantiene para una publicacion OTA distinta; no activarlo para cada clase.

**No se concede acceso anónimo a Databricks Apps ni se inicia compute desde una petición HTTP no autenticada.**

## Correccion del fallo GitHub Actions #1 (2026-10-27)

La ejecucion inicial `40566536573` se detuvo en el preflight antes de contactar a Databricks: en GitHub environment `prod`, `DATABRICKS_HOST` y `DATABRICKS_CLIENT_ID` aparecieron vacios. Se corrigio la dependencia de `DATABRICKS_HOST` fijando **exclusivamente** el workspace alumno dentro del YAML, de manera que esa variable ya no se administra ni puede confundirse con el workspace original.

**Una modificacion al workflow NO crea una identidad en Databricks.** Para usar el control cloud sigue faltando configurar el Application ID real del service principal:

```powershell
$Repo = "wpv10barza/asistente-de-databricks--erp"
$ClientId = Read-Host "Application ID REAL del service principal GitHub OIDC"
if ([string]::IsNullOrWhiteSpace($ClientId)) { throw "Falta Application ID" }
gh variable set DATABRICKS_CLIENT_ID -R $Repo --env prod --body $ClientId
gh variable list -R $Repo --env prod
```

Este ID NO es el numero del workspace, el email del profesor ni el token de dispositivo ESP32. Debe existir previamente en la cuenta Databricks y estar autorizado en el workspace alumno.

### Federacion y privilegios

Para el repositorio creado en 2026, GitHub OIDC usa el subject **con IDs inmutables** (validar contra el JWT efectivo si el repositorio fue transferido o renombrado):

- Issuer: `https://token.actions.githubusercontent.com`
- Subject: `repo:wpv10barza@181611197/asistente-de-databricks--erp@1410769928:environment:prod`
- Audience: configurar el valor que corresponda a la cuenta Databricks y al token emitido por GitHub; Databricks recomienda el account ID. No inventar un account ID.
- Service principal Databricks: vinculado al workspace alumno, permiso `CAN MANAGE` sobre la App `asistente-cloud-erp-alumno`.

La politica de federacion debe crearse por un administrador de la cuenta Databricks; la escritura de la variable de GitHub por si sola **no** configura la federacion. Referencias oficiales:
- https://docs.databricks.com/aws/en/dev-tools/auth/provider-github
- https://docs.databricks.com/aws/en/dev-tools/auth/oauth-federation-policy

### Uso tras completar federacion

1. [Alumno Cloud | Control rapido](https://github.com/wpv10barza/asistente-de-databricks--erp/actions/workflows/alumno-cloud-control.yml): `Run workflow` en `main`, `action=status`. Esto verifica la conexion sin iniciar la App.
2. Revisar que el run muestre autentificacion OIDC y App alumno correctas.
3. `action=start`: **inicia compute facturable** solo por solicitud explicita del docente. Si ya esta encendida y solo se desea consultar, elegir `status`.
4. `action=redeploy` solamente si la App alumna esta asociada al Git backend esperado. El workflow no exige Git para `status/start/stop/grant_access`.
5. Despues de las pruebas, `action=stop`. Confirmar el estado en GitHub o consola.

El nuevo workflow termina con errores claros cuando falta el Application ID, cuando falla la federation policy o cuando la App corresponde a un repositorio no esperado. El flujo sigue protegido por GitHub environment `prod` y por `main`, no recompila el ESP32, ni publica OTA y **no utiliza el workspace original**.

**Nota economica:** el boton del ESP32 lleva al docente al workflow GitHub mediante QR. El ESP32 no recibe permisos de administracion; la FOTA por GitHub Releases es independiente del compute de Databricks.
