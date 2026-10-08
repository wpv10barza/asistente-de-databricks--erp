from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from .semantic_data import build_records


def tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-záéíóúñ0-9]+", text.lower())
        if len(token) > 2
    }


@dataclass
class SemanticIndex:
    records: list[dict]
    inverted: dict[str, set[int]]

    @classmethod
    def load(cls) -> "SemanticIndex":
        records = build_records()
        inverted: dict[str, set[int]] = defaultdict(set)
        for index, record in enumerate(records):
            document = " ".join(
                [
                    record["query"],
                    record["matched_historical_feature"],
                    record["prt_code"],
                    record["specialty"],
                ]
            )
            for token in tokens(document):
                inverted[token].add(index)
        return cls(records=records, inverted=dict(inverted))

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        query_tokens = tokens(query)
        candidates: set[int] = set()
        for token in query_tokens:
            candidates |= self.inverted.get(token, set())
        if not candidates:
            return []

        scored: list[tuple[float, int, dict]] = []
        for index in candidates:
            record = self.records[index]
            document_tokens = tokens(
                " ".join(
                    [
                        record["query"],
                        record["matched_historical_feature"],
                        record["prt_code"],
                        record["specialty"],
                    ]
                )
            )
            score = len(query_tokens & document_tokens) / max(
                1, len(query_tokens | document_tokens)
            )
            if score:
                scored.append((score, index, record))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [
            {
                "score": round(score, 4),
                "prt_code": record["prt_code"],
                "family": record["family"],
                "specialty": record["specialty"],
                "suggested_column": record["suggested_column"],
                "suggested_column_name": record["suggested_column_name"],
                "query": record["query"],
                "authority": "retrieval_only",
            }
            for score, _, record in scored[:top_k]
        ]
