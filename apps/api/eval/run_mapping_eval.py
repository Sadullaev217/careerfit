"""Scores skill mapping against the loaded ESCO skills. Usage: python -m eval.run_mapping_eval"""

import json
import sys
from pathlib import Path
from typing import Any

from app import store
from app.skill_matching import match_names

ITEMS = Path(__file__).parent / "skill_mapping.json"


def score_mapping(items: list[dict[str, Any]], labels: list[str | None]) -> dict[str, int]:
    """An empty accept list means ESCO has no right answer, so any mapping is an error."""
    totals = {"correct": 0, "wrong": 0, "unmapped": 0, "correctly_unmapped": 0}
    for item, label in zip(items, labels, strict=True):
        accept = item["accept"]
        if label is None:
            totals["unmapped" if accept else "correctly_unmapped"] += 1
        elif any(term in label.lower() for term in accept):
            totals["correct"] += 1
        else:
            totals["wrong"] += 1
    return totals


def main() -> int:
    items = json.loads(ITEMS.read_text(encoding="utf-8"))
    matches = match_names([item["name"] for item in items], store)
    labels = [match.canonical_name if match else None for match in matches]

    for item, match, label in zip(items, matches, labels, strict=True):
        score = f"{match.similarity:.2f}" if match else "  - "
        print(f"{score}  {item['name']} -> {label}")

    totals = score_mapping(items, labels)
    mapped = totals["correct"] + totals["wrong"]
    should_map = sum(bool(item["accept"]) for item in items)
    print(f"\n{totals}")
    print(f"when it maps, it's right: {totals['correct']}/{mapped}")
    print(f"skills with a right answer that were mapped correctly: {totals['correct']}/{should_map}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
