from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .column_map import SHEET_HEADERS_A_AF
from .indexer import tokens


@dataclass
class LiveSheetIndex:
    rows: list[dict] = field(default_factory=list)
    inverted: dict[str, set[int]] = field(default_factory=dict)

    def rebuild(self, values: list[list[object]], start_row: int = 5) -> int:
        rows: list[dict] = []
        inverted: dict[str, set[int]] = defaultdict(set)
        headers = list(SHEET_HEADERS_A_AF.values())

        for offset, raw in enumerate(values):
            padded = list(raw) + [""] * max(0, len(headers) - len(raw))
            if not any(str(value).strip() for value in padded[: len(headers)]):
                continue

            item = {headers[index]: padded[index] for index in range(len(headers))}
            item["_sheet_row"] = start_row + offset
            document = " ".join(
                str(item[header])
                for header in headers
                if item[header] not in (None, "")
            )
            row_index = len(rows)
            rows.append(item)
            for token in tokens(document):
                inverted[token].add(row_index)

        self.rows = rows
        self.inverted = dict(inverted)
        return len(rows)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        query_tokens = tokens(query)
        if not query_tokens or not self.rows:
            return []

        candidates: set[int] = set()
        for token in query_tokens:
            candidates |= self.inverted.get(token, set())

        scored: list[tuple[float, int, dict]] = []
        for index in candidates:
            item = self.rows[index]
            document_tokens = tokens(
                " ".join(
                    str(value)
                    for key, value in item.items()
                    if not key.startswith("_") and value not in (None, "")
                )
            )
            score = len(query_tokens & document_tokens) / max(1, len(query_tokens))
            if score:
                scored.append((score, index, item))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [
            {
                "score": round(score, 4),
                "sheet_row": item["_sheet_row"],
                "EstrategiaId": item.get("EstrategiaId", ""),
                "TareaId": item.get("TareaId", ""),
                "Nombre": item.get("Nombre", ""),
                "Especialidad": item.get("Especialidad", ""),
                "Labour1": item.get("Labour1", ""),
            }
            for score, _, item in scored[:top_k]
        ]
