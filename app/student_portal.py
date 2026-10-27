"""Portal académico de solo lectura sobre el backend Databricks existente.

La identidad/SSO y CAN_USE/CAN_MANAGE se gestionan en el proxy de Databricks
Apps. El formulario no recoge contraseñas ni tokens de dispositivos.
"""


def render_portal() -> str:
    return """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Acceso académico 3C | Databricks</title>
  <style>
    :root { color-scheme: light; font-family: system-ui, sans-serif; background:#f1f5f9; color:#172a3a; }
    * { box-sizing:border-box; }
    body { max-width:980px; margin:24px auto; padding:0 16px 40px; line-height:1.5; }
    header, section { background:#fff; border:1px solid #dce5ed; border-radius:14px; padding:21px; margin:14px 0; }
    h1 { font-size:1.7rem; margin:0 0 12px; }
    h2 { font-size:1.17rem; margin:0 0 10px; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(290px,1fr)); gap:14px; }
    .grid section { margin:0; }
    button, a.button { cursor:pointer; display:inline-block; background:#176f62; color:white; border:0; text-decoration:none;
      border-radius:9px; padding:10px 14px; margin:5px 7px 5px 0; font:inherit; font-weight:600; }
    button:focus-visible, a:focus-visible, input:focus-visible { outline:3px solid #f59e0b; outline-offset:2px; }
    button:disabled { opacity:.55; cursor:wait; }
    input { font:inherit; border:1px solid #83929e; border-radius:8px; padding:10px; width:100%; margin:5px 0; }
    p { margin:8px 0 12px; } small,.muted { color:#485b69; }
    .status { padding:10px; margin-top:10px; border:1px solid #d9e1e6; border-radius:8px;
      background:#f8fafc; white-space:pre-wrap; overflow-wrap:anywhere; }
    pre { white-space:pre-wrap; overflow-wrap:anywhere; max-height:280px; overflow:auto; background:#f8fafc;
      border:1px solid #d9e1e6; padding:12px; border-radius:8px; }
    code { overflow-wrap:anywhere; }
  </style>
</head>
<body>
  <header>
    <h1>Interfaz portátil 3C — Conexión al backend</h1>
    <p>Acceso académico a <strong>Databricks Apps</strong>, desde móvil o PC, sin que el equipo personal deba permanecer encendido.</p>
    <p class="muted">Inicia sesión mediante Databricks (SSO o código de un solo uso).
      No introduzcas tu contraseña ni el token del ESP32 aquí. La sesión y los permisos los verifica Databricks.</p>
  </header>

  <div class="grid">
    <section>
      <h2>Conexión al backend</h2>
      <p>Conéctate al servicio en ejecución y consulta sus capacidades, no solo una prueba del dispositivo.</p>
      <button type="button" id="connect">Conectar con el backend</button>
      <div id="backend-status" class="status" role="status" aria-live="polite">Pulsa Conectar para consultar el backend.</div>
      <p><a href="/docs">Explorar API</a> · <a href="/api/index/status">Índice Pocket</a></p>
    </section>
    <section>
      <h2>Acceso del alumno</h2>
      <p>Cuenta autorizada con permiso <code>CAN_USE</code>. Puedes usar el índice Pocket de manera real, con búsqueda de solo lectura.</p>
      <form id="search-form">
        <label for="query">Consulta de mantenimiento</label>
        <input id="query" name="query" minlength="3" maxlength="1000" placeholder="Ej.: mantenimiento preventivo" required>
        <button type="submit">Buscar en Pocket</button>
      </form>
      <pre id="search-results" role="status" aria-live="polite">Introduce una consulta para buscar.</pre>
    </section>
    <section>
      <h2>Conexión a Google Sheets</h2>
      <p>Verifica una lectura real de las cabeceras de la hoja configurada. No modifica datos.</p>
      <button type="button" id="verify-sheet">Verificar conexión a los datos</button>
      <div id="sheet-status" class="status" role="status" aria-live="polite">Sin verificar.</div>
      <p class="muted">Si faltan las credenciales de Google o el permiso sobre la hoja, la API indicará el fallo.</p>
    </section>
    <section>
      <h2>Control docente</h2>
      <p>El docente con permiso <code>CAN_MANAGE</code> gestiona el servicio desde GitHub Actions:
        <strong>estado, iniciar, detener, redesplegar y permisos</strong>.
        Estos controles no requieren el PC encendido ni recompilan el firmware.</p>
      <a class="button" href="https://github.com/wpv10barza/asistente-de-databricks--erp/actions/workflows/alumno-cloud-control.yml"
        target="_blank" rel="noopener noreferrer">Abrir control cloud en GitHub</a>
    </section>
  </div>
  <section>
    <h2>Módulos y seguridad</h2>
    <p><a href="/voice-3c">Módulo IA / Voz 3C</a> · <a href="/api/health">Diagnóstico API</a> ·
      <a href="/api/device/v1/health">Estado del ESP32</a></p>
    <small>Si la App está detenida, la página tampoco puede iniciarla: usa el control docente o Databricks.
      Las operaciones sensibles requieren la validación y aprobación humanas existentes; la escritura en Sheets sigue deshabilitada por defecto.
      El ESP32 utiliza autenticación independiente, no cuentas personales.</small>
  </section>
  <script>
    "use strict";
    const connect = document.getElementById("connect");
    const backendStatus = document.getElementById("backend-status");
    const verify = document.getElementById("verify-sheet");
    const sheetStatus = document.getElementById("sheet-status");
    const form = document.getElementById("search-form");
    const searchResults = document.getElementById("search-results");

    async function requestJSON(url, options) {
      const response = await fetch(url, {cache:"no-store", credentials:"same-origin", ...options});
      const result = await response.json();
      if (!response.ok) throw new Error("HTTP " + response.status + ": " + JSON.stringify(result.detail || result));
      return result;
    }
    connect.addEventListener("click", async () => {
      connect.disabled = true;
      backendStatus.textContent = "Consultando el backend Databricks...";
      try {
        const info = await requestJSON("/api/health");
        backendStatus.textContent = info.ok
          ? "Backend conectado. Entorno: " + info.runtime +
            "\\nÍndice Pocket: " + info.records_indexed + " registros" +
            "\\nGoogle Sheets configurado: " + (info.sheet_auth_mode !== "unconfigured" ? "sí" : "no") +
            "\\nDispositivo: " + (info.device_api_configured ? "configurado" : "sin configurar") +
            "\\nFirmware OTA: " + (info.ota_volume_configured ? "configurado" : "sin configurar")
          : "El backend respondió pero no confirmó su estado.";
      } catch (err) {
        backendStatus.textContent = "No se pudo conectar: " + err.message;
      } finally { connect.disabled = false; }
    });
    verify.addEventListener("click", async () => {
      verify.disabled = true;
      sheetStatus.textContent = "Validando lectura real de Google Sheets...";
      try {
        const info = await requestJSON("/api/sheet/verify");
        sheetStatus.textContent = info.ok ? "Conexión real confirmada. Cabeceras correctas. Modo: " + info.auth_mode
          : "La hoja respondió con discrepancias.";
      } catch (err) {
        sheetStatus.textContent = "Conexión a datos no verificada: " + err.message;
      } finally { verify.disabled = false; }
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const query = document.getElementById("query").value.trim();
      if (query.length < 3) return;
      const button = form.querySelector('button[type="submit"]');
      button.disabled = true;
      searchResults.textContent = "Buscando en Databricks...";
      try {
        const result = await requestJSON("/api/index/search", {
          method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({query,top_k:5})
        });
        searchResults.textContent = JSON.stringify(result.matches || result, null, 2);
      } catch (err) {
        searchResults.textContent = "No se pudo completar la búsqueda: " + err.message;
      } finally { button.disabled = false; }
    });
  </script>
</body>
</html>"""
