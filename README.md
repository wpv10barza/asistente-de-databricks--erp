# Asistente 3C + ERP — Databricks only

Edición cloud del **Asistente 3C** y del módulo **Pocket/RAG** preparada exclusivamente para **Databricks Apps**.

No requiere WSL, Docker, Docker Compose, Ollama local ni una PC encendida para ejecutar la API.

## Arquitectura

```text
ESP32 / cliente / especialista
          ↓
Databricks App (FastAPI)
          ├─ Device API 3C
          ├─ interpretación opcional con Gemini
          ├─ índice Pocket determinístico (360 casos)
          ├─ índice live de Google Sheets
          ├─ validación determinística
          ├─ revisión humana
          └─ escritura Google Sheets solo tras aprobación
```

## Fuentes canónicas migradas

- `wpv10barza/pocket-test` @ `e87dda191a2681b165141d41c2f22da06d45565d`
- `wpv10barza/Asistente-con-arquitectura-RAG-para-carga-automatizada-de-recursos-de-mantenimiento` @ `41c33d82fdb1aa882ebafce287b9ee8a2b163448`
- `wpv10barza/asistente-3c` @ `4ced1d644374165612da9a70237bf552d93345eb`

La migración conserva el principio central:

> **IA interpreta y recupera → backend valida → persona confirma → sistema persiste y audita.**

## Diferencias respecto al despliegue Ubuntu/WSL

Se eliminaron del runtime:

- WSL y rutas locales;
- Docker / Compose;
- mDNS;
- Ollama local;
- IP LAN del host;
- scripts de arranque Ubuntu.

Databricks ejecuta directamente FastAPI mediante `app.yaml` y `DATABRICKS_APP_PORT`.

## Endpoints principales

- `GET /api/health`
- `GET /api/index/status`
- `POST /api/index/search`
- `GET /api/sheet/verify`
- `POST /api/index/sheet/rebuild`
- `POST /api/index/sheet/search`
- `POST /api/extract`
- `POST /api/review/proposals`
- `POST /api/review/proposals/{id}/approve`
- `POST /api/review/proposals/{id}/reject`
- `POST /api/review/proposals/{id}/apply`
- `GET /api/device/v1/health`
- `POST /api/device/v1/commands`
- `GET /api/device/v1/commands/{id}`

## Seguridad por defecto

- `ALLOW_SHEET_WRITE=false`.
- No se versionan claves API, OAuth tokens ni JSON de service account.
- `E=TareaId` y `F=Nombre` son búsqueda, no escritura.
- Lista de escritura cloud: `B,C,H,I,J,K,L,M,N,O`.
- Verificación de `Data!A4:AF4` antes de persistir.
- Bloqueo de fórmulas y texto azul antes de actualizar una celda.
- Una propuesta debe pasar por estado `approved` antes de `applied`.
- El ESP32 no puede marcar una operación como aplicada.

## CI/CD

`.github/workflows/ci.yml` prueba la aplicación **sin Docker**, con Python 3.11.

`.github/workflows/deploy-databricks.yml` despliega manualmente mediante:

```text
GitHub Actions
   ↓ OIDC
Databricks Declarative Automation Bundle
   ↓
Databricks App
   ↓
RUNNING
```

Para el primer despliegue el workflow es manual (`workflow_dispatch`) por seguridad.

## Documentación

- [Prompt maestro](PROMPT_MAESTRO_DATABRICKS.md)
- [Migración](docs/MIGRATION_NOTES.md)
- [Setup Databricks](docs/SETUP_DATABRICKS.md)
- [app.yaml](app.yaml)
- [databricks.yml](databricks.yml)

## Inicio en Databricks

Primero despliegue sin secretos. Deben funcionar `/`, `/docs`, `/api/health` y el índice Pocket.

Después agregue secretos de Databricks para Gemini, Google Service Account y Device API. Mantenga escritura desactivada hasta validar lectura, cabeceras y guardas.

## Historial de ordenes 3C y Google Sheets (ESP32)

Nuevo endpoint autenticado con `X-3C-Device-Token`:

- `GET /api/device/v1/history?device_id=PANEL_ID&limit=8`: ordenes enviadas, estados, vistas previas vinculadas y modificaciones confirmadas (fila, celda, valor nuevo y fecha).
- `GET /api/device/v1/history/panel?device_id=PANEL_ID&limit=8`: filas TSV limitadas para la pantalla 480×480, sin bloquear la UI.

Una orden `pending_confirmation` es **solo recibida**, no implica escritura. Los eventos `sheet_applied` se registran unicamente despues de que Google Sheets responde correctamente a `batch_update_cells`. Una vista previa muestra valores propuestos y nunca se etiqueta como aplicada.

**Durabilidad:** configure `HISTORY_LOG_PATH=/Volumes/.../history/3c-audit.jsonl` en la aplicación Databricks (ruta real montada y con permiso de escritura) para preservar un registro JSONL entre reinicios. Sin volumen configurado, el historial es **solo de la sesión del proceso** y no debe usarse como auditoría histórica completa. Los datos previos a esta función no se reconstruyen automáticamente. Proteja el volumen porque conserva valores de celdas.


## Módulo Voz 3C / Databricks / ESP32

El módulo de voz se aloja en `app/voice_3c.py` y reutiliza la credencial
`GEMINI_API_KEY` ya asignada a Databricks Apps. El modelo de transcripción
configurable es `VOICE_GEMINI_MODEL=gemini-2.5-flash`.
El cliente Windows y las instrucciones están en
[voice-embeding-in-databricks-for-esp32](https://github.com/wpv10barza/voice-embeding-in-databricks-for-esp32).

El micrófono o archivo WAV/MP3 se encuentra en Windows, nunca en el ESP32:
`PowerShell -> Databricks (/voice/transcribe) -> borrador (/voice/drafts)
-> ESP32 (/voice/inbox/panel) -> EDITAR ORDEN 3C -> envío manual -> revisión
humana -> aprobación opcional de la propuesta Sheets`.

La transcripción **nunca** ejecuta escritura ni envía automáticamente la
orden. La bandeja solo conserva borradores durante 15 minutos en memoria
del proceso de la App; se requiere una cola persistente/compartida para
garantizar entrega en despliegues con múltiples réplicas o reinicios.
No desplegar esa variante como entrega garantizada sin migrar el estado.

`GET /api/device/v1/cloud/verify` exige el token del dispositivo y
realiza lectura efectiva de `Data!A4:AF4`, validando los encabezados.
HTTP 200 significa lectura y esquema correcto; HTTP 409, esquema distinto;
HTTP 502, fallo de acceso. `/api/health` solo verifica la configuración
y no prueba acceso real a Google Sheets.

La App requiere OAuth Databricks Apps además de `X-3C-Device-Token`
cuando el workspace lo solicite. No se almacenan tokens en Git.


## Espejo cloud de voz ESP32 (opt-in, sin IP LAN)

El firmware existente consulta por HTTPS el endpoint
GET /api/device/v1/voice/inbox/panel aproximadamente cada 9 segundos.
Esa llamada autenticada registra una senal de vida del dispositivo.
GET /api/device/v1/voice/sync?device_id=panel-4848s040-3c-01
(con X-3C-Device-Token y OAuth Databricks cuando corresponda) indica
panel_seen_recently, antiguedad del ultimo contacto y numero de borradores
queued_for_editor / delivered_to_editor. No precisa abrir el puerto 80
del panel ni conocer su IP local; no escribe Sheets.

**Durabilidad optativa:** asigne a la App un UC Volume con permiso
Can read and write y configure VOICE_DRAFT_STORE_PATH a un archivo
JSON dentro de la ruta montada, por ejemplo
/Volumes/<catalogo>/<esquema>/<volume>/voice/drafts.json.
La ruta es de ejemplo; no invente ni use el Volume de firmware OTA
sin comprobar permisos. Puede definirla en app.yaml cuando haya creado
y vinculado el recurso de almacenamiento.
El servidor conservara hasta 50 borradores durante 15 minutos, el estado
de recepcion y ACK incluso si el proceso se reinicia. Si la ruta configurada
no es escribible, las operaciones de voz fallan con HTTP 503 en lugar de
aceptar borradores que no puedan persistirse. Con la variable vacia,
el modo sera memory_only, como antes.

**Limitacion crucial:** este espejo de fichero es para **una sola instancia**
de FastAPI. No ofrece transacciones entre replicas/instancias ni sustituye
una cola administrada o tabla transaccional. Para alta disponibilidad real
migre a almacenamiento que garantice escrituras atomicas concurrentes.
panel_seen_recently se basa en el ultimo GET de bandeja autenticado; indica
actividad reciente, no demuestra que el borrador haya llegado al editor.
Solo delivered_to_editor confirma el ACK del dispositivo. Al reiniciar el
ESP32 o caer Wi-Fi pueden seguir existiendo interrupciones de red: el
espejo conserva y ayuda a diagnosticar, pero no puede impedirlas.

Despliegue el backend nuevo en **asistente-cloud-erp** y consulte con
el cliente de voz scripts/Diagnosticar-Mirror3C.ps1. El commit de GitHub
y CI exitosa no equivalen a un despliegue en Databricks.
La revision tactil y ALLOW_SHEET_WRITE=false se mantienen intactos.
