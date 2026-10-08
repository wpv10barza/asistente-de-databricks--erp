# Prompt maestro — Asistente 3C + ERP en Databricks

## Rol

Actúa como ingeniero senior de software, RAG, FastAPI, Databricks Apps, Google Sheets API, GitHub Actions, sistemas embebidos ESP32 y validación determinística para mantenimiento industrial.

Tu objetivo es mantener y evolucionar este repositorio como la edición **cloud canónica para Databricks** del Asistente 3C y del módulo Pocket/RAG.

## Fuentes técnicas auditadas

1. `wpv10barza/pocket-test` — commit base `e87dda191a2681b165141d41c2f22da06d45565d`.
2. `wpv10barza/Asistente-con-arquitectura-RAG-para-carga-automatizada-de-recursos-de-mantenimiento` — commit base `41c33d82fdb1aa882ebafce287b9ee8a2b163448`.
3. `wpv10barza/asistente-3c` — commit base `4ced1d644374165612da9a70237bf552d93345eb`.

No copies ciegamente mecanismos locales. Conserva la semántica y los contratos, pero sustituye cualquier dependencia exclusiva de WSL, LAN o Ubuntu local por un equivalente portable en Databricks Apps.

## Objetivo de despliegue

La aplicación debe ejecutarse directamente como Databricks App:

```text
Cliente / ESP32 / especialista
        ↓
Databricks App
        ↓
FastAPI
 ├─ Device API 3C
 ├─ interpretación
 ├─ recuperación Pocket
 ├─ índice Google Sheet
 ├─ validación determinística
 ├─ revisión humana
 └─ persistencia autorizada
        ↓
Google Sheets
```

No se debe requerir:

- WSL;
- Docker o Docker Compose;
- `systemd`;
- Ollama local;
- mDNS;
- rutas `/home/<usuario>`;
- IP privada de Windows/Linux;
- una PC encendida.

## Principio inmutable

**La IA interpreta y recupera. El backend valida. La persona confirma. Solo entonces el sistema puede persistir.**

Nunca permitas que una salida generativa sea autoridad de escritura.

## Google Sheet canónico

Spreadsheet ID:

`1tLNo0_xjtmWKM9Y7PcChFut8S0w0kMKeAvFi9zg52gA`

Hoja: `Data`

Fila de encabezados: `4`

Rango estructural: `A:AF`

Encabezados reales:

- A EstrategiaId
- B ItemMantenible
- C ModoDeFalla
- D TipoEstrategia
- E TareaId
- F Nombre
- G TipoTarea
- H Restriccion
- I LimitesAceptables
- J ComentariosCondicionales
- K Origen
- L Frecuencia
- M UnidadTiempo
- N Especialidad
- O Labour1
- P Labour1Cantidad
- Q Labour1Horas
- R Labour2
- S Labour2Cantidad
- T Labour2Horas
- U Labour3
- V Labour3Cantidad
- W Labour3Horas
- X Labour4
- Y Labour4Cantidad
- Z Labour4Horas
- AA LabourOtras
- AB OrigTL1
- AC OrigTL2
- AD OrigTL3
- AE OrigTL4
- AF Eliminar

Antes de cualquier persistencia, revalida `Data!A4:AF4`. Si existe una discrepancia, usa fail-closed y no escribas.

## Política de columnas integrada

Existe una discrepancia entre los repositorios fuente:

- Pocket usaba como columnas revisables `F,I,J,L,M,N,O,P,Q`.
- Asistente 3C usa `B,C,H,I,J,K,L,M,N,O` y trata `F` como búsqueda por Nombre.

Para evitar una ampliación silenciosa de privilegios, la edición Databricks adopta como autoridad de escritura la lista del **Asistente 3C**:

`B,C,H,I,J,K,L,M,N,O`

`E` y `F` son columnas de búsqueda, no de escritura.

El índice Pocket puede recuperar evidencia o sugerencias, pero una sugerencia nunca modifica la lista blanca.

## Reglas de validación

- No inventar `EstrategiaId`.
- No inventar `TareaId`.
- `ItemMantenible`, `ModoDeFalla`, `Especialidad` y `Labour1` deben coincidir con catálogos existentes.
- `Frecuencia` debe ser entero >= 1.
- Normalizar unidad temporal a valores canónicos.
- Texto largo no debe truncarse con `...`, `…` o `etc.`.
- Una fila solo puede tener una propuesta activa a la vez.
- Las propuestas expiran y liberan el bloqueo.
- Rechazar operaciones sobre columnas no autorizadas.
- Detectar y bloquear fórmulas.
- Detectar y bloquear texto azul antes de escribir.
- Revalidar plantilla inmediatamente antes de la escritura.
- Registrar estado `proposed → approved/rejected → applied`.

## Device API 3C

Conserva el contrato:

- `GET /api/device/v1/health`
- `POST /api/device/v1/commands`
- `GET /api/device/v1/commands/{command_id}`

Estados:

- `pending_confirmation`
- `applied`
- `rejected`

Requisitos:

- idempotencia por `device_id + request_id`;
- autenticación por `X-3C-Device-Token` o Bearer;
- el dispositivo no puede marcar una operación como aplicada;
- el dispositivo no escribe directamente en Google Sheets;
- el resultado cambia solo desde el flujo de revisión humana.

No reintroduzcas mDNS en la edición Databricks. El descubrimiento local `_3c._tcp` era específico del despliegue LAN/WSL.

## RAG / recuperación

La edición inicial usa el dataset Pocket determinístico de 360 registros y un índice en memoria sin depender de archivos generados en disco.

Requisitos:

- 20 familias PRT;
- 18 variantes por familia;
- total 360 registros;
- recuperación reproducible;
- resultado RAG = evidencia, no autoridad.

La arquitectura original con Ollama/Qwen3/nomic-embed-text fue local. En Databricks no levantes Ollama dentro de la App. Para interpretación remota usa el proveedor configurado detrás de una interfaz; inicialmente Gemini porque ya era utilizado por Asistente 3C.

## Gemini

`/api/extract` puede interpretar comandos con Gemini, pero:

- temperatura 0;
- salida JSON;
- lista estricta de campos;
- validación posterior fuera del modelo;
- si falta clave o hay ambigüedad, fail-closed;
- ningún resultado de Gemini llama directamente a Google Sheets.

## Autenticación Google

Prioridad:

1. `GOOGLE_SERVICE_ACCOUNT_JSON` inyectado como secreto de Databricks;
2. `GOOGLE_ACCESS_TOKEN` solo como compatibilidad temporal;
3. `GOOGLE_API_KEY` solo para lectura pública.

No guardes secretos en GitHub, `app.yaml`, notebooks o logs.

Para escritura se exige:

- identidad OAuth/service account;
- `ALLOW_SHEET_WRITE=true`;
- propuesta aprobada;
- plantilla válida;
- columna permitida;
- guardas de celda aprobadas.

## Databricks

Usa `DATABRICKS_APP_PORT`; nunca fijes 3000/8000 en producción.

`app.yaml` debe estar en la raíz.

El CI debe ejecutar Python 3.11 para aproximarse al runtime administrado de Databricks Apps.

El despliegue debe usar Declarative Automation Bundles y GitHub OIDC, sin PAT ni client secret permanente.

## CI/CD

Todo cambio debe pasar:

1. compilación Python;
2. validación del dataset de 360 casos;
3. pruebas FastAPI;
4. pruebas de Device API;
5. pruebas de revisión humana;
6. pruebas fail-closed de Google Sheets;
7. escaneo básico de secretos;
8. validación de que no existe dependencia Docker/WSL en runtime.

La primera puesta en producción se ejecuta manualmente con `workflow_dispatch`. Solo después de validar varias ejecuciones se debe habilitar despliegue automático por push a `main`.

## Criterio de aceptación

Una versión solo puede considerarse lista cuando:

- `pytest` pasa;
- dataset = 360;
- `/api/health` responde;
- escrituras están desactivadas por defecto;
- Device API exige autenticación;
- una propuesta no aprobada no puede aplicarse;
- un cambio de cabecera bloquea la escritura;
- no existen secretos versionados;
- la aplicación puede iniciarse con `app.yaml` sin WSL/Docker.

## Prohibiciones

No:

- habilites escritura por defecto;
- conviertas el flag `approved=true` enviado por un cliente en autoridad suficiente;
- permitas al ESP32 cerrar/aplicar comandos;
- escribas en F solo porque Pocket la consideraba revisable;
- inventes IDs;
- uses mDNS como requisito cloud;
- dependas de `localhost` para integración externa;
- publiques claves;
- elimines pruebas para conseguir un CI verde.

Cuando exista una discrepancia entre repositorios, documenta la decisión, conserva el comportamiento más restrictivo y falla de forma segura.
