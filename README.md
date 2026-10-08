# Asistente 3C + ERP — Databricks only

Edición cloud del Asistente 3C y del módulo Pocket/RAG preparada exclusivamente para **Databricks Apps**.

No requiere WSL, Docker, Docker Compose, Ollama local ni una PC encendida para ejecutar la API.

## Arquitectura

```text
ESP32 / cliente / especialista
          ↓
Databricks App (FastAPI)
          ├─ Device API 3C
          ├─ interpretación opcional con Gemini
          ├─ índice semántico determinístico (360 casos)
          ├─ índice live de Google Sheets
          ├─ validación determinística
          ├─ revisión humana
          └─ escritura Google Sheets solo tras aprobación
```

## Fuentes canónicas migradas

- `wpv10barza/pocket-test`
- `wpv10barza/Asistente-con-arquitectura-RAG-para-carga-automatizada-de-recursos-de-mantenimiento`
- `wpv10barza/asistente-3c`

La migración conserva el principio central: **IA interpreta y recupera; el backend valida; una persona confirma; solo entonces se persiste**.

## Databricks

La aplicación usa `app.yaml` y el puerto administrado `DATABRICKS_APP_PORT`.

```bash
uvicorn app.main:app --host 0.0.0.0 --port "$DATABRICKS_APP_PORT"
```

El despliegue por GitHub Actions se realiza mediante Declarative Automation Bundles y OIDC; no se almacena un token de Databricks en el repositorio.

## Seguridad por defecto

- `ALLOW_SHEET_WRITE=false`.
- No se versionan claves API, OAuth tokens ni JSON de service account.
- Escritura bloqueada sin aprobación humana.
- Verificación de `Data!A4:AF4` antes de persistir.
- Columnas de identidad/búsqueda permanecen bloqueadas.
- El ESP32 nunca escribe directamente en Google Sheets.

Consulte `PROMPT_MAESTRO_DATABRICKS.md` y `docs/SETUP_DATABRICKS.md`.
