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
2. En GitHub > Settings > Environments > **`alumno-cloud` (entorno independiente del `prod` original)**, configure `DATABRICKS_HOST=https://dbc-77f7771e-2520.cloud.databricks.com` y `DATABRICKS_CLIENT_ID=<application ID del service principal GitHub OIDC>`. El principal debe tener federacion OIDC y `CAN MANAGE` sobre la App.
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

- **status/start/stop/grant_access**: sin clonar repo, pytest, PlatformIO, firmware u OTA. `start` y `stop` envían la solicitud con `--no-wait`; el workflow termina antes, pero la App puede seguir iniciándose o deteniéndose. Ejecute `status` para confirmar el estado real.
- **redeploy**: despliega el backend desde la rama `main` y **sí espera el resultado** para detectar un fallo real. La duración del arranque de Databricks no se elimina acortando la espera de GitHub.
- El workflow `firmware-cd.yml` del repo `erp-mantto-esp32` se mantiene para una publicacion OTA distinta; no activarlo para cada clase.

**No se concede acceso anónimo a Databricks Apps ni se inicia compute desde una petición HTTP no autenticada.**

## Separación estricta de entornos

- El workflow académico usa **solo** el GitHub Environment `alumno-cloud` con sus propias `DATABRICKS_HOST` y `DATABRICKS_CLIENT_ID`. No reutilice `prod`: el deploy original apunta a otro workspace y podría afectar su configuración.
- Aplique reglas de protección y aprobadores autorizados al Environment `alumno-cloud`. GitHub Actions no proporciona autenticación interactiva al alumno; el navegador utiliza Databricks SSO/OTP.
- `start` y `stop` ahora son solicitudes asíncronas. Una ejecución verde confirma que Databricks recibió la solicitud, **no** que ya está `RUNNING` o `STOPPED`. Use `status` antes de declarar el sistema disponible.
- Para `grant_access`, las cuentas deben existir en el Databricks account del workspace del alumno y el principal OIDC requiere permisos para administrar el acceso. No se alteran los permisos del workspace original.
