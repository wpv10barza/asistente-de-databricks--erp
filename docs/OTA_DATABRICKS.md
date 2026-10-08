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
