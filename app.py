from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.getenv("UVICORN_HOST", "0.0.0.0")
    raw_port = os.getenv("DATABRICKS_APP_PORT") or os.getenv("UVICORN_PORT") or "8000"
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise RuntimeError(f"Invalid app port: {raw_port!r}") from exc

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level=os.getenv("UVICORN_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
