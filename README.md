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

