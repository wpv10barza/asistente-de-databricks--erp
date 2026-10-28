# Control del workspace alumno desde Android Termux

Instala Termux desde F-Droid o el proyecto oficial. No necesitas PowerShell ni PC.

## 1. En Termux (Android)

Copia y pega este unico bloque en **Termux nativo**, no dentro de Ubuntu. Instala Bash primero y luego ejecuta el instalador directamente desde GitHub, sin guardar ningun archivo manualmente:

~~~sh
pkg update -y && pkg install -y bash curl ca-certificates && bash -c 'set -o pipefail; curl -fsSL https://raw.githubusercontent.com/wpv10barza/asistente-de-databricks--erp/main/scripts/INSTALAR-TERMUX-ALUMNO.sh | bash'
~~~

En el propio instalador se descargan solo las librerias necesarias para la conexion: `openssl`, certificados TLS, `jq`, `git`, `coreutils`, `grep`, `sed`, `findutils`, `tar`, `gzip`, `unzip` y `proot-distro`. Ubuntu incluye Bash, Python 3, `gh` y el Databricks CLI oficial de Linux ARM64/AMD64. No se descargan contrasenas ni credenciales de GitHub o Databricks.

El instalador prepara Ubuntu PRoot. El CLI de Databricks se instala dentro de Ubuntu Linux ARM64, no como binario nativo de Android.

## 2. En Ubuntu, autentícate

~~~sh
proot-distro login ubuntu
databricks auth login --host https://accounts.cloud.databricks.com --account-id e6cf2e56-e1fa-464b-91b0-39517832bde0 --profile alumno-cuenta-3c
databricks auth login --host https://dbc-77f7771e-2520.cloud.databricks.com --profile alumno-3c
gh auth login
~~~

Usa una identidad con permisos administrativos de la CUENTA ALUMNA para crear el service principal. Si la URL de autenticación no se abre sola, copia la URL que muestra la terminal, ábrela en Chrome y vuelve a Termux. No compartas tokens ni contraseñas.

## 3. Primero solo lectura

~~~sh
bash /root/Alumno3C/setup-alumno-oidc-termux.sh
~~~

Si confirma la cuenta e6cf2e56-e1fa-464b-91b0-39517832bde0, workspace 7474657268940105 y App asistente-cloud-erp-alumno, autoriza los cambios:

~~~sh
bash /root/Alumno3C/setup-alumno-oidc-termux.sh --apply --status
~~~

Se solicitará escribir CONFIGURAR-ALUMNO. Esta acción crea o reutiliza github-actions-alumno-3c, asigna USER al workspace alumno, configura GitHub OIDC prod, concede CAN_MANAGE al principal y docente, CAN_USE a Polo y actualiza la variable DATABRICKS_CLIENT_ID. El script solo despacha status, NO start.

## 4. Abre GitHub desde Termux

Después de salir de Ubuntu con exit:

~~~sh
termux-open-url 'https://github.com/wpv10barza/asistente-de-databricks--erp/actions/workflows/alumno-cloud-control.yml'
~~~

Comprueba que status termine SUCCESS antes de iniciar start, que puede consumir créditos de Databricks. La configuración no requiere otro flash del ESP32. No se toca el workspace original.

Referencias oficiales: https://docs.databricks.com/aws/en/dev-tools/cli/install y https://docs.databricks.com/aws/en/dev-tools/auth/provider-github y https://github.com/termux/proot-distro.
