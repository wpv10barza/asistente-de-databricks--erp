# Laboratorio alumno 3C: 7 dias, horometro y limite de actividad

**Estado: propuesta. Estos archivos NO activan ni detienen ninguna App.**

Afecta unicamente asistente-cloud-erp-alumno en
https://dbc-77f7771e-2520.cloud.databricks.com.
NO afecta el backend original.

## Como se factura

Databricks Apps funciona en la nube aunque Windows este apagado,
pero factura capacidad por hora mientras la App esta ACTIVE,
incluso sin peticiones. La prueba de 14 dias no se prolonga al
detener el App ni asegura credito ilimitado.
Medium: 0.5 DBU/h, Large: 1 DBU/h, XLarge: 3 DBU/h
por instancia. Una semana Medium (168 h) suma aprox. 84 DBU
de App, sin contar SQL, IA, volumenes ni servicios externos.
DBU no es equivalente a USD sin consultar la tarifa.

Referencia oficial:
https://docs.databricks.com/aws/en/dev-tools/databricks-apps/compute-size

## Apagado remoto al vencer 7 dias

El workflow .github/workflows/alumno-lab-expiry-guard.yml
revisa LAB_END_UTC dos veces cada hora y al vencer intenta
detener SOLO la App de la alumna, verificando STOPPED.
Windows NO necesita permanecer encendido.
La programacion de GitHub NO es un apagado exacto:
puede retrasarse, omitirse o fallar por OIDC/permiso.
Tambien configure alertas de consumo en Databricks.

## Configuracion inicial una sola vez, despues de fusionar PR a main

El entorno GitHub sera ALUMNO-3C, separado de prod original.
ATENCION: el deploy-databricks.yml ya existente del backend
TODAVIA contiene la URL del workspace ORIGINAL.
No ejecutar ese workflow de deploy para el laboratorio.

Desde PowerShell:

~~~powershell
Set-PSReadLineOption -HistorySaveStyle SaveNothing
$repo = "wpv10barza/asistente-de-databricks--erp"
gh api --method PUT "repos/$repo/environments/alumno-3c"
gh variable set DATABRICKS_HOST --env alumno-3c -R $repo --body "https://dbc-77f7771e-2520.cloud.databricks.com"
$appId = Read-Host "Application ID principal GitHub OIDC alumna"
gh variable set DATABRICKS_CLIENT_ID --env alumno-3c -R $repo --body $appId
gh variable list --env alumno-3c -R $repo
databricks apps get asistente-cloud-erp-alumno --profile alumno-3c --output json
~~~

Registrar federacion OIDC en Databricks para:
repo:wpv10barza/asistente-de-databricks--erp:environment:alumno-3c
Dar a ese principal permiso para leer y detener
asistente-cloud-erp-alumno. No copiar secrets, claves, ni identidad
del principal del workspace original.

Prueba sin iniciar la App: defina un vencimiento futuro de prueba
y ejecute el workflow guard manualmente. Compruebe que la lectura
de la App termine SUCCESS, no solamente el cron.

~~~powershell
$repo = "wpv10barza/asistente-de-databricks--erp"
$future = [datetime]::UtcNow.AddHours(1).ToString("yyyy-MM-ddTHH:mm:ssZ")
gh variable set LAB_END_UTC --env alumno-3c -R $repo --body $future
gh workflow run alumno-lab-expiry-guard.yml -R $repo --ref main
gh run list -R $repo --workflow alumno-lab-expiry-guard.yml --limit 3
~~~

La fecha anterior es de prueba: el comando Iniciar la reemplaza.

## Arrancar, consultar y detener desde Windows

En el repositorio BACKEND que contiene scripts/Lab-Alumno-3C.ps1:

~~~powershell
.\scripts\Lab-Alumno-3C.ps1 -Modo Estado
.\scripts\Lab-Alumno-3C.ps1 -Modo Iniciar -Horas 168
.\scripts\Lab-Alumno-3C.ps1 -Modo Iniciar -Horas 168 -Ejecutar -GuardVerificado
.\scripts\Lab-Alumno-3C.ps1 -Modo Horometro
.\scripts\Lab-Alumno-3C.ps1 -Modo Detener -Ejecutar
~~~

Estado y Horometro son solo lectura. Iniciar exige -Ejecutar,
-GuardVerificado, App STOPPED y el guard ya disponible en main.
No extiende automaticamente una sesion activa.
Guarda LAB_STARTED_UTC y LAB_END_UTC en el entorno GitHub alumno-3c.
Detener registra LAB_STOPPED_UTC y apaga la App de verdad.
No realiza deploy, no toca Google Sheets y no habilita escritura.

El horometro del script es una estimacion del tiempo de calendario
desde el arranque registrado y NO es saldo de creditos ni DBU
facturadas: no reconstruye acciones fuera de este script.

En emergencia, apague directamente, sin depender de GitHub:

~~~powershell
databricks apps stop asistente-cloud-erp-alumno --profile alumno-3c --timeout 20m
databricks apps get asistente-cloud-erp-alumno --profile alumno-3c --output json
~~~

## Horometro financiero y horas de consumo fuerte

Use sql/horometro_consumo_alumno_3c.sql en el editor SQL de la alumna:
1. DBU al dia facturadas por esa App;
2. 48 horas de mayor consumo en DBU;
3. Consumos SQL/jobs del mismo workspace, sin mezclar el original.

Requiere acceso a system.billing.usage; los datos pueden demorarse
12 horas o mas. Abrir un SQL warehouse tambien puede costar.
Para umbrales, configurar Databricks Account Console Usage/Budgets.
Una alerta diferida no garantiza detener inmediatamente los cargos.
Si la prueba vence, el sistema no puede prorrogar esos 14 dias.

Referencia: https://docs.databricks.com/aws/en/admin/system-tables/billing
