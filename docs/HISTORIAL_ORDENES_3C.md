# Historial de órdenes 3C en pantalla ESP32

La recepción HTTP 200 y `pending_confirmation` **no implica** que se haya
modificado Google Sheets. Tras aprobación humana y escritura confirmada, el
backend registra `applied`, `change_count` y `changes_summary` (celdas y
valores nuevos); un rechazo queda en `rejected`. No hay escritura directa
al recibir el comando.

`GET /api/device/v1/commands/history?device_id=panel-4848s040-3c-01&offset=0`
requiere el mismo token del dispositivo y devuelve una entrada por página:
`total`, `offset`, `command_id`, `text`, `status`, `result`,
`change_count`, `changes_summary`, `updated_at`.

**Limitación:** este historial es reciente, no es una auditoría permanente.
El almacén original solo conserva hasta 50 comandos por 15 minutos y se
reinicia cuando Databricks Apps reinicia. No presentar esta vista como
prueba histórica de modificaciones fuera de ese plazo. Para auditoría
persistente se necesita una base/volumen con escrituras controladas y
retención independiente de la memoria de la aplicación.

La aprobación sigue siendo humana mediante propuestas de revisión:
`POST /api/review/proposals`, `/approve` y `/apply`. Únicamente
`/apply` tras `gateway.batch_update_cells` exitoso marca
`applied`. El menú ESP32 no concede autorización de escritura.
