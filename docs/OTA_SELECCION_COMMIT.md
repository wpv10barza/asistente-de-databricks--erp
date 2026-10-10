# Selección de OTA por commit de GitHub

La Databricks App admite `GET /api/device/v1/firmware/commits/{commit_sha}`.
El cliente debe enviar OAuth Databricks y `X-3C-Device-Token` igual que
en los otros endpoints OTA.

Se aceptan SHA completos de 40 caracteres o prefijos de 8 a 40 hexadecimales.
La búsqueda **no clona ni descarga fuentes de GitHub**: busca únicamente
versiones previamente compiladas y publicadas en el UC Volume
`workspace.default.esp32_firmware`.

Ejemplo de `stable/2.5.1/manifest.json`:
```json
{
  "version": "2.5.1",
  "git_commit_sha": "a4b4144c6d96aedf8ca6a78f9b7adf7a436c0b0e",
  "sha256": "EL_SHA256_REAL_DE_64_HEXADECIMALES",
  "size": 123456
}
```
Este es solo un esquema: no es un firmware publicado.
El endpoint retorna version, git_commit_sha, size, sha256, url, canal y
verificación. Rechaza prefijos ambiguos, revisiones inexistentes,
contenido alterado y manifiestos incorrectos. No cae de vuelta a latest
cuando falla una selección manual.

Un commit antiguo o de GitHub Actions fallido (como `a4b4144c` en su
compilación original) **no será instalable** hasta que el binario haya
sido recompilado, validado y publicado expresamente.

El firmware cliente usa el endpoint para verificar antes de instalar,
con doble partición OTA, tamaño, SHA256 y rollback.
No se permite el `git pull` desde el microcontrolador: instala binarios,
no archivos fuente. Ningún cambio modifica las órdenes 3C ni Sheets.
