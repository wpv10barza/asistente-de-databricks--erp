# Notas de migración a Databricks

## Baselines

| Fuente | Commit auditado |
|---|---|
| pocket-test | e87dda191a2681b165141d41c2f22da06d45565d |
| presentación RAG | 41c33d82fdb1aa882ebafce287b9ee8a2b163448 |
| asistente-3c | 4ced1d644374165612da9a70237bf552d93345eb |

## Cambios exclusivamente de plataforma

- Express/Node no es requisito del runtime cloud: el contrato se porta a FastAPI.
- WSL, scripts de Ubuntu, Docker y Docker Compose se eliminan del runtime.
- mDNS se elimina porque no tiene sentido como descubrimiento de un servicio público/proxy de Databricks.
- Ollama/Qwen3/nomic local no se levanta dentro de Databricks Apps.
- El índice Pocket se genera en memoria para evitar depender de escritura al sistema de archivos del host.
- `PORT=3000` se reemplaza por `DATABRICKS_APP_PORT`.

## Discrepancia de columnas

Pocket: `F,I,J,L,M,N,O,P,Q`.

Asistente 3C: `B,C,H,I,J,K,L,M,N,O`.

La política cloud adopta la lista de Asistente 3C como lista de escritura. El índice Pocket sigue siendo una capa de recuperación y no amplía permisos.

## Estado

Esta migración no afirma validación física del ESP32. CI/CD y Databricks prueban software. El panel físico debe validarse separadamente.
