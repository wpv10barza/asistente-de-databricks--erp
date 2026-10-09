# Publicación OTA segura a Databricks (pendiente de validación física)

## Propósito
La App FastAPI sirve actualizaciones del dispositivo ESP32-S3-4848S040.
El backend ahora comprueba el **SHA-256 real del contenido** y exige
manifiestos consistentes antes de servir archivos a través de HTTPS.

## Recursos Databricks
En `app.yaml` ya existen las referencias:
- `ESP32_API_TOKEN` desde `esp32_api_token`;
- `OTA_VOLUME_PATH` desde `ota_firmware_volume`;
- `OTA_CHANNEL=stable`.

El volumen está previsto como Unity Catalog
`workspace.default.esp32_firmware` con ruta
`/Volumes/workspace/default/esp32_firmware`.
Verificar que el recurso de la App se asocia realmente a ese volumen y
que el principal de la aplicación dispone de **CAN READ VOLUME**.

## Estructura
```text
stable/
  2.5.1/
    firmware.bin
    manifest.json
  latest.json
```
El binario debe derivar de un compilado de firmware con doble slot OTA.
Los manifiestos en ambos niveles deben declarar la misma
`version`, `sha256` real de 64 caracteres hexadecimales y `size`
en bytes. `manifest.json` de cada versión es obligatorio.
Primero colocar `firmware.bin`, después su manifiesto, y **solo al
final** promover `stable/latest.json`.

No escribir tokens OAuth ni el secreto del dispositivo en los manifiestos.
No publicar un artefacto no verificado o de un chip distinto.

## Contrato
`GET /api/device/v1/firmware/latest` y
`GET /api/device/v1/firmware/{version}.bin`
requieren OAuth Databricks y `X-3C-Device-Token` correcto.
Errores de integridad deben impedir servir el firmware.
El dispositivo comprueba de nuevo SHA-256 antes de aplicar `Update.end`.

## Limitaciones
Esta actualización **no publica por sí sola un binario real** al Volume.
Deben configurarse permisos, publicarse una release válida y realizarse
pruebas físicas de flash inicial, OTA, arranque y rollback. Un HTTP 200
en health solo valida conectividad, no prueba OTA.
