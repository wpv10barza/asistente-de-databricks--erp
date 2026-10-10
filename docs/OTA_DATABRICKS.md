# OTA firmware storage in Databricks

The ESP32 OTA client in `wpv10barza/firmware-demo` expects the Databricks App to expose:

- `GET /api/device/v1/firmware/latest`
- `GET /api/device/v1/firmware/{version}.bin`

Both routes use the existing device authorization and are also protected by the Databricks Apps edge authentication.

## 1. Create a Unity Catalog volume

Create a managed UC volume, for example:

```text
/Volumes/main/default/esp32_firmware
```

The firmware publishing workflow stores:

```text
/Volumes/.../stable/latest.json
/Volumes/.../stable/1.0.1/firmware.bin
/Volumes/.../stable/1.0.1/manifest.json
```

## 2. Add the volume to the App

In Databricks Apps:

```text
asistente-cloud-erp
→ Settings
→ Resources
→ Add resource
→ UC volume
→ Permission: Can read
→ Resource key: ota_firmware_volume
```

The App only needs read access because GitHub Actions publishes the binaries.

## 3. Bind the resource path

After the resource exists, add this to `app.yaml`:

```yaml
- name: OTA_VOLUME_PATH
  valueFrom: ota_firmware_volume
- name: OTA_CHANNEL
  value: "stable"
```

Do not add `valueFrom: ota_firmware_volume` before the App resource exists, otherwise deployment can fail because the resource key is unresolved.

## 4. Publish from firmware-demo

Configure GitHub Environment `prod` in `firmware-demo` with:

```text
DATABRICKS_HOST
DATABRICKS_CLIENT_ID
OTA_VOLUME_PATH=/Volumes/main/default/esp32_firmware
```

Then run **Firmware OTA** manually with a higher semantic version and `publish_to_databricks=true`.

The workflow uploads the immutable version directory first and updates `latest.json` last.

## 5. Reparar `OTA manifest HTTP 404` desde Windows

**Distinción clave:** la ruta `GET /api/device/v1/firmware/latest` ya
está registrada en el backend. Si el archivo `stable/latest.json` no existe,
la app devuelve **503** (no 404). Por ello **404** indica una URL, despliegue
o enrutamiento equivocado, no simplemente que falta el archivo.

```powershell
databricks apps deploy asistente-cloud-erp `
  --git-commit <SHA_BACKEND_CON_RUTA_OTA> `
  --profile asistente-cloud-erp `
  --timeout 10m
```

Después del despliegue, ejecutar el diagnóstico de solo lectura:

```powershell
.\scripts\Diagnosticar-OTA404.ps1
```

Puede establecer temporalmente las variables de entorno
`DATABRICKS_ACCESS_TOKEN` y `ESP32_API_TOKEN` en la sesión local para
verificar las rutas autenticadas. **No escriba secretos en archivos del
repositorio ni los pegue en el chat.**

Para inspeccionar el canal publicado en el volumen real:

```powershell
.\scripts\Diagnosticar-OTA404.ps1 -VolumePath /Volumes/MI_CATALOGO/MI_ESQUEMA/MI_VOLUMEN
```

Interpretación de códigos:
- **200:** manifiesto encontrado y validado en el servidor;
- **401/403/302:** autenticación/Databricks Apps edge;
- **404:** falta la ruta en la aplicación desplegada o URL incorrecta;
- **503:** ruta presente; configuración/token o release OTA no disponible;
- **500:** error no controlado; revisar logs de la aplicación.

Nuevo recurso autenticado `GET /api/device/v1/firmware/status` comunica
`ready`, `status`, `channel`, `version` y `size` sin divulgar la
ubicación interna del volumen ni las credenciales.

**Seguridad:** jamás publique el `firmware.bin` de
`erp-mantto-esp32` 2.6 como OTA todavía: esa variante no usa
particiones duales OTA ni contiene cliente OTA; instalarla podría
deshabilitar las actualizaciones inalámbricas. Publique únicamente
un binario compilado y probado para la tabla
`partitions_ota_16mb.csv`, con OTA y credenciales de dispositivo
debidamente provisionadas.

### 6. Si responde 503 por manifiesto ausente

Verifique `OTA_VOLUME_PATH` en la app (UC Volume asociado con permiso
de lectura) y el directorio `<volume>/stable/latest.json` mediante
`databricks fs ls dbfs:/Volumes/.../stable --profile asistente-cloud-erp`.
**No invente una ruta de volumen.** El workflow
`wpv10barza/firmware-demo` solo publica al volumen cuando se ejecuta
manualmente con `publish_to_databricks=true` y están configurados
`DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID` y `OTA_VOLUME_PATH` en
GitHub Environment `prod`. Compilar en Actions no implica publicar.
