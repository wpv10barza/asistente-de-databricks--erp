# Termux: App Databricks alumno y firmware OTA

El 28/10/2026 GitHub Actions #6 validó la identidad OIDC, pero el principal carecía del entitlement WORKSPACE_ACCESS. En Databricks 2026 el rol USER y el entitlement de workspace son distintos. Esta corrección solo afecta a la cuenta alumna e impide START mientras no se valide el permiso.

## 1. Actualizar configuración OIDC en Ubuntu de Termux

~~~bash
curl -fLsS --retry 3 https://raw.githubusercontent.com/wpv10barza/asistente-de-databricks--erp/main/scripts/setup-alumno-oidc-termux.sh -o /root/Alumno3C/setup-alumno-oidc-termux.sh
bash -n /root/Alumno3C/setup-alumno-oidc-termux.sh
bash /root/Alumno3C/setup-alumno-oidc-termux.sh
~~~

El último comando no modifica recursos. Si confirma cuenta e6cf2e56-e1fa-464b-91b0-39517832bde0, workspace 7474657268940105 y App asistente-cloud-erp-alumno, procede:

~~~bash
bash /root/Alumno3C/setup-alumno-oidc-termux.sh --apply --status
~~~

Escribe CONFIGURAR-ALUMNO. El script intenta conservar todos los entitlements existentes y añadir exclusivamente WORKSPACE_ACCESS al principal OIDC del alumno. Si la API IAM no está disponible, se detiene. Alternativa: workspace alumno > Settings > Identity and access > Service principals > github-actions-alumno-3c > habilitar Workspace access. No conceder Workspace admin.

## 2. Verificar firmware y control de App desde Termux

~~~bash
curl -fLsS --retry 3 https://raw.githubusercontent.com/wpv10barza/asistente-de-databricks--erp/main/scripts/termux-ota-cloud-control.sh -o /root/Alumno3C/termux-ota-cloud-control.sh
bash -n /root/Alumno3C/termux-ota-cloud-control.sh
bash /root/Alumno3C/termux-ota-cloud-control.sh check
~~~

Confirma el release ota-d400e8c1 con firmware.bin y manifest.json, más el último resultado de GitHub Actions. No enciende la App.

Si el último status fue SUCCESS y el profesor autorizó encender la App con posible consumo de créditos:

~~~bash
bash /root/Alumno3C/termux-ota-cloud-control.sh start
~~~

Escribe ENCENDER-ALUMNO solo si deseas iniciar compute. Si todavía falta status:

~~~bash
bash /root/Alumno3C/termux-ota-cloud-control.sh status
~~~

Comprobar el resultado en GitHub Actions:
https://github.com/wpv10barza/asistente-de-databricks--erp/actions/workflows/alumno-cloud-control.yml

## 3. Actualización OTA física del ESP32

En la pantalla ESP32, con Wi-Fi 2.4 GHz y hora UTC NTP válida, entra al menú FOTA, escribe d400e8c1, selecciona VERIFICAR y después INSTALAR. El ESP32 descarga por HTTPS el manifiesto y firmware desde GitHub y comprueba SHA-256.

La App Databricks puede iniciarse desde Termux mediante GitHub Actions, pero no hace la actualización física del ESP32. El flash tampoco aprovisiona mágicamente Wi-Fi o credenciales OAuth/token de dispositivo.

Fuentes: https://docs.databricks.com/api/iam/v2/account-workspace-assignment y https://docs.databricks.com/aws/en/security/auth/entitlements
