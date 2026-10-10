# Diagnostico OTA ESP32/Databricks. Solo lectura: NO publica ni instala firmware.
# Uso:
# powershell -ExecutionPolicy Bypass -File .\scripts\Diagnosticar-OTA404.ps1
# Antes, opcionalmente establecer DATABRICKS_ACCESS_TOKEN y ESP32_API_TOKEN en
# las variables de entorno de la sesion; no introducir credenciales en argumentos.
[CmdletBinding()]
param(
    [string]$AppUrl = "https://asistente-cloud-erp-7474651957738908.aws.databricksapps.com",
    [string]$AppName = "asistente-cloud-erp",
    [string]$Profile = "asistente-cloud-erp",
    [string]$VolumePath = ""
)
$ErrorActionPreference = "Stop"
$AppUrl = $AppUrl.TrimEnd('/')
$headers = @{}
if ($env:DATABRICKS_ACCESS_TOKEN) {
    $headers["Authorization"] = "Bearer $env:DATABRICKS_ACCESS_TOKEN"
}
if ($env:ESP32_API_TOKEN) {
    $headers["X-3C-Device-Token"] = $env:ESP32_API_TOKEN
}
function Probe-Route([string]$RelativePath) {
    $url = "$AppUrl$RelativePath"
    $code = 0
    $body = ""
    try {
        $r = Invoke-WebRequest -Uri $url -Method GET -Headers $headers -UseBasicParsing -TimeoutSec 20 -MaximumRedirection 0
        $code = [int]$r.StatusCode
        $body = [string]$r.Content
    } catch {
        if ($_.Exception.Response) {
            $code = [int]$_.Exception.Response.StatusCode
            try {
                $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $body = $reader.ReadToEnd()
                $reader.Dispose()
            } catch {
                $body = "(No se pudo leer el cuerpo de la respuesta)"
            }
        } else {
            Write-Host "ERROR de red en $RelativePath : $($_.Exception.Message)"
            return @{ status = 0; path = $RelativePath; body = $body }
        }
    }
    Write-Host ("{0,3} {1}" -f $code, $RelativePath)
    if ($body.Length -gt 0) {
        Write-Host ("  Respuesta: " + $body.Substring(0,[Math]::Min(300,$body.Length)))
    }
    return @{status=$code;path=$RelativePath;body=$body}
}
Write-Host "=== Diagnostico OTA Databricks Apps ==="
Write-Host "App: $AppName"
if (-not $headers.ContainsKey("Authorization")) {
    Write-Warning "DATABRICKS_ACCESS_TOKEN no definido. La capa de Databricks puede responder 302/401/403."
}
if (-not $headers.ContainsKey("X-3C-Device-Token")) {
    Write-Warning "ESP32_API_TOKEN no definido. Las rutas OTA protegidas responderan 401/503."
}
try {
    Write-Host "--- Estado de Databricks Apps ---"
    & databricks apps get $AppName --profile $Profile --output json
} catch {
    Write-Warning "No fue posible consultar Databricks Apps: $($_.Exception.Message)"
}
Write-Host "--- Rutas HTTP ---"
$health = Probe-Route "/api/device/v1/health"
$diagnostic = Probe-Route "/api/device/v1/firmware/status"
$manifest = Probe-Route "/api/device/v1/firmware/latest"
if ($health.status -eq 200 -and $manifest.status -eq 404) {
    Write-Warning "404 del manifiesto aunque Device API funciona: revisar URL del ESP32 y version real desplegada. Debe incluir /api/device/v1/firmware/latest."
} elseif ($manifest.status -eq 503) {
    Write-Warning "La ruta EXISTE, pero falta o es incorrecto latest.json / binario en el Volume OTA (o falta token)."
} elseif ($manifest.status -eq 200) {
    Write-Host "OK: manifiesto servido. Compare version/size/sha256 antes de instalar." -ForegroundColor Green
} elseif ($manifest.status -eq 401 -or $manifest.status -eq 403) {
    Write-Warning "Es un problema de autenticacion, no de archivo OTA."
} elseif ($manifest.status -eq 302) {
    Write-Warning "El gateway solicita inicio de sesion OAuth; hace falta autenticar la solicitud."
} elseif ($manifest.status -eq 404) {
    Write-Warning "404: endpoint ausente en la app desplegada, dominio/base URL incorrecto o respuesta del gateway. Comprobar respuesta y logs."
}
if ($diagnostic.status -eq 404 -and $health.status -eq 200) {
    Write-Warning "Falta endpoint de diagnostico: despliegue el backend que incorpora /api/device/v1/firmware/status."
}
if ($VolumePath) {
    if ($VolumePath -notmatch '^/Volumes/[^/]+/[^/]+/[^/]+$') {
        throw "VolumePath debe ser exactamente /Volumes/catalogo/esquema/volumen"
    }
    $root = "dbfs:$VolumePath/stable"
    Write-Host "--- Archivos OTA del canal stable ---"
    & databricks fs ls $root --profile $Profile
    & databricks fs cat "$root/latest.json" --profile $Profile
}
Write-Host "Diagnostico terminado. No se ha flasheado ni publicado firmware."
