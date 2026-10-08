# Puesta en marcha en Databricks Apps

## 1. Crear o desplegar la App

Nombre previsto:

`asistente-databricks-erp`

El repositorio ya contiene `app.yaml` y `databricks.yml`.

El comando de ejecución es administrado por Databricks y usa `DATABRICKS_APP_PORT`.

## 2. Primera prueba sin secretos

Despliegue primero con `app.yaml` tal como está. La aplicación debe arrancar con:

- índice Pocket: disponible;
- Google Sheet: autenticación no configurada;
- escritura: desactivada;
- Gemini: no configurado;
- Device API: no acepta comandos hasta añadir token.

Pruebe:

- `/`
- `/docs`
- `/api/health`
- `/api/index/status`

## 3. Secretos de la App

Cree un scope de secretos exclusivo para esta aplicación y agregue, según necesidad:

- `gemini_api_key`
- `google_service_account_json`
- `esp32_api_token`

Añada esos secretos como recursos de la Databricks App con exactamente esas resource keys.

Después tome `app.with-secrets.example.yaml` como referencia para agregar los `valueFrom` a `app.yaml`.

No copie el valor del secreto dentro de Git.

## 4. Google Service Account

La opción recomendada para Google Sheets es `GOOGLE_SERVICE_ACCOUNT_JSON`.

Comparta el Google Sheet con el correo de la service account y conceda solo el permiso necesario.

Para la primera prueba mantenga:

`ALLOW_SHEET_WRITE=false`

Pruebe:

1. `GET /api/sheet/verify`
2. `POST /api/index/sheet/rebuild`
3. `POST /api/index/sheet/search`

Solo después de validar lectura, cabeceras y guardas de estilo considere activar escritura.

## 5. GitHub Actions → Databricks por OIDC

En GitHub cree el Environment `prod`.

Variables del environment:

- `DATABRICKS_HOST=https://dbc-a1aca8aa-28bd.cloud.databricks.com`
- `DATABRICKS_CLIENT_ID=<application-id-del-service-principal>`

No se necesita client secret si se configura Workload Identity Federation.

En Databricks cree una federation policy para el service principal y otorgue `CAN MANAGE` sobre la App o permisos para crearla.

Luego ejecute manualmente:

`Actions → Deploy to Databricks Apps → Run workflow`

El workflow valida el bundle, despliega, reinicia la App y espera a que el estado sea `RUNNING`.

## 6. Escritura

Para habilitar persistencia deliberadamente, cambie el valor no sensible de:

`ALLOW_SHEET_WRITE=true`

Esto no basta por sí solo. El backend exige además:

- propuesta existente;
- estado `approved`;
- autenticación Google con OAuth/service account;
- cabecera A:AF exacta;
- columna en lista blanca;
- celda sin fórmula;
- celda sin texto azul.

## 7. ESP32

La Device API conserva los endpoints del Asistente 3C.

Databricks Apps aplica su propia capa de autenticación/proxy. Antes de apuntar el firmware directamente al dominio de la App, compruebe cómo autenticará el dispositivo frente al proxy de Databricks. El token `X-3C-Device-Token` protege la aplicación, pero no sustituye una autenticación exigida por la plataforma.

La validación del firmware físico sigue siendo una fase independiente.
