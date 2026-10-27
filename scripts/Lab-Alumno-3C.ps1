[CmdletBinding()]
param(
    [ValidateSet('Estado', 'Iniciar', 'Detener', 'Horometro')]
    [string]$Modo = 'Estado',
    [ValidateRange(1, 168)]
    [int]$Horas = 168,
    [switch]$Ejecutar,
    [switch]$GuardVerificado
)

# Student-specific control; intentionally NEVER operates on the original App.
# Hour meter uses scheduled wall time, not financial billing measurements.
$ErrorActionPreference = 'Stop'
$Repo = 'wpv10barza/asistente-de-databricks--erp'
$App = 'asistente-cloud-erp-alumno'
$Profile = 'alumno-3c'
$ExpectedHost = 'https://dbc-77f7771e-2520.cloud.databricks.com'
$Workflow = 'alumno-lab-expiry-guard.yml'

function Invoke-GhText {
    param([string[]]$Arguments)
    $result = (& gh @Arguments | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw ("GitHub CLI error ({0}). Compruebe gh auth status." -f ($Arguments -join ' '))
    }
    return $result
}

function Get-GhVariable {
    param([string]$Name)
    $result = & gh variable get $Name --env prod --repo $Repo 2>$null
    if ($LASTEXITCODE -ne 0) { return '' }
    return ([string]($result | Out-String)).Trim()
}

function Set-GhVariable {
    param([string]$Name, [string]$Value)
    & gh variable set $Name --env prod --repo $Repo --body $Value
    if ($LASTEXITCODE -ne 0) { throw "No se pudo configurar $Name en GitHub prod." }
}

function Get-StudentState {
    $raw = (& databricks apps get $App --profile $Profile --output json | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "No se pudo consultar la App alumno-3c." }
    $obj = $raw | ConvertFrom-Json
    if ($obj.name -ne $App) { throw 'Databricks devolvio otra App: cancelado.' }
    return $obj
}

foreach ($exe in @('databricks','gh')) {
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) {
        throw "Falta $exe en PATH."
    }
}

$State = Get-StudentState
$Compute = [string]$State.compute_status.state
$Status = [string]$State.app_status.state
$Started = Get-GhVariable 'LAB_STARTED_UTC'
$Deadline = Get-GhVariable 'LAB_END_UTC'
$Stopped = Get-GhVariable 'LAB_STOPPED_UTC'

Write-Host ("App: {0}" -f $App)
Write-Host ("Compute: {0} | Backend: {1}" -f $Compute, $Status)
Write-Host ("Inicio registrado (UTC): {0}" -f $Started)
Write-Host ("Apagado programado (UTC): {0}" -f $Deadline)

if ($Modo -in @('Estado', 'Horometro')) {
    if ($Started) {
        try {
            $t0 = [datetime]::Parse($Started).ToUniversalTime()
            $until = [datetime]::UtcNow
            if ($Stopped) {
                $tStop = [datetime]::Parse($Stopped).ToUniversalTime()
                if ($tStop -lt $until) { $until = $tStop }
            }
            if ($until -ge $t0) {
                $h = [math]::Round(($until - $t0).TotalHours, 2)
                Write-Host ("Horometro PROGRAMADO desde inicio registrado: {0} h" -f $h)
            }
        } catch {
            Write-Warning 'Fechas de horometro invalidas; revise las variables GitHub.'
        }
    }
    Write-Host 'AVISO: tiempo orientativo, NO es consumo facturado ni saldo de creditos.'
    Write-Host 'Para DBU reales consultar system.billing.usage en Databricks SQL.'
    return
}

if (-not $Ejecutar) {
    Write-Host ("Simulacion: -Modo {0}. Agregue -Ejecutar para efectuar cambios." -f $Modo)
    return
}

if ($Modo -eq 'Detener') {
    & databricks apps stop $App --profile $Profile --timeout 20m
    if ($LASTEXITCODE -ne 0) { throw 'No se completo el stop del backend alumno.' }
    $newState = Get-StudentState
    if ([string]$newState.compute_status.state -ne 'STOPPED') {
        throw 'No se confirma STOPPED: revise Databricks Apps.'
    }
    Set-GhVariable 'LAB_STOPPED_UTC' ([datetime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))
    Write-Host '[OK] App alumna detenida. No se ha alterado el workspace original.'
    return
}

# An unattended seven-day start is never permitted without an explicit
# confirmation that the GitHub OIDC guard was actually tested.
if (-not $GuardVerificado) {
    throw 'Antes de Iniciar: pruebe el workflow guard con OIDC y repita con -GuardVerificado.'
}
if ($Compute -ne 'STOPPED') {
    throw 'La App no esta STOPPED. No se extiende ni reinicia otra ventana activa.'
}
$HostConfigured = Get-GhVariable 'DATABRICKS_HOST'
$OidcPrincipal = Get-GhVariable 'DATABRICKS_CLIENT_ID'
if ($HostConfigured -ne $ExpectedHost -or [string]::IsNullOrWhiteSpace($OidcPrincipal)) {
    throw 'Configurar DATABRICKS_HOST y DATABRICKS_CLIENT_ID del entorno prod antes de Iniciar.'
}
# Workflows added in an unmerged PR are not operational; require default branch.
Invoke-GhText @('workflow', 'view', $Workflow, '--repo', $Repo) | Out-Null
$now = [datetime]::UtcNow
$end = $now.AddHours($Horas)
$startIso = $now.ToString('yyyy-MM-ddTHH:mm:ssZ')
$endIso = $end.ToString('yyyy-MM-ddTHH:mm:ssZ')
Set-GhVariable 'LAB_END_UTC' $endIso
Set-GhVariable 'LAB_STARTED_UTC' $startIso
# Delete the previous stop marker if it exists.
if ($Stopped) {
    & gh variable delete LAB_STOPPED_UTC --env prod --repo $Repo
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo limpiar el marcador de apagado anterior.' }
}

& databricks apps start $App --profile $Profile --timeout 20m
if ($LASTEXITCODE -ne 0) { throw 'Fallo el start. El plazo de guardia permanece configurado.' }
$newState = Get-StudentState
if ([string]$newState.compute_status.state -ne 'ACTIVE') {
    throw 'El arranque no alcanzo estado ACTIVE; compruebe la App.'
}
Write-Host ("[OK] App alumna activa. Apagado guardia programado para {0} UTC." -f $endIso)
Write-Warning 'GitHub schedule puede demorarse/fallar. NO es un limite absoluto de cobro; revise la App y presupuestos de Databricks.'
