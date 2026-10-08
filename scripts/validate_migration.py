#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.column_map import WRITE_COLUMNS
from app.indexer import SemanticIndex
from app.semantic_data import PRTS, build_records

records = build_records()
assert len(PRTS) == 20
assert len(records) == 360
assert WRITE_COLUMNS == {"B", "C", "H", "I", "J", "K", "L", "M", "N", "O"}

index = SemanticIndex.load()
assert len(index.records) == 360
assert index.search("termografía punto caliente tablero", 3)

assert not (ROOT / "Dockerfile").exists(), "Databricks-only repo must not require Dockerfile"
assert not (ROOT / "docker-compose.yml").exists(), "Databricks-only repo must not require Compose"
assert (ROOT / "app.yaml").exists()
assert (ROOT / "databricks.yml").exists()

app_yaml = (ROOT / "app.yaml").read_text(encoding="utf-8")
assert "DATABRICKS_APP_PORT" in app_yaml
assert "ALLOW_SHEET_WRITE" in app_yaml
assert 'value: "false"' in app_yaml

print(
    "MIGRATION_VALIDATED "
    "runtime=databricks-only records=360 "
    "write_columns=B,C,H,I,J,K,L,M,N,O "
    "docker=not-required wsl=not-required"
)
