"""Loads ESCO skills with their embeddings. Usage: python -m scripts.seed_esco [--limit N]"""

import argparse
import sys
import time
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlsplit

import httpx

from app import store
from app.embeddings import embed_texts

START_URL = "https://ec.europa.eu/esco/api/search?type=skill&language=en&limit=100&full=false"
PAGE_DELAY_SECONDS = 0.2
UPSERT_BATCH = 500


def fetch_skills(client: httpx.Client, limit: int | None) -> Iterator[dict[str, Any]]:
    url: str | None = START_URL
    seen = 0
    while url:
        if urlsplit(url).hostname != "ec.europa.eu":
            raise RuntimeError("ESCO pagination pointed at another host")
        response = client.get(url, headers={"Accept": "application/json"})
        response.raise_for_status()
        body = response.json()
        for result in body["_embedded"]["results"]:
            yield result
            seen += 1
            if limit is not None and seen >= limit:
                return
        url = body["_links"].get("next", {}).get("href")
        time.sleep(PAGE_DELAY_SECONDS)


def to_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """skills.name is unique, so a repeated label keeps its first concept."""
    rows: dict[str, dict[str, Any]] = {}
    for result in results:
        name = (result.get("preferredLabel", {}).get("en") or result["title"]).strip()
        rows.setdefault(name.lower(), {"name": name, "esco_id": result["uri"]})
    return list(rows.values())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    with httpx.Client(timeout=60, trust_env=False) as client:
        results = list(fetch_skills(client, args.limit))
    rows = to_rows(results)
    print(f"fetched {len(results)} skills, {len(rows)} unique names")

    for start in range(0, len(rows), UPSERT_BATCH):
        batch = rows[start : start + UPSERT_BATCH]
        vectors = embed_texts([row["name"] for row in batch])
        store.upsert_skills(
            [{**row, "embedding": vector} for row, vector in zip(batch, vectors, strict=True)]
        )
        print(f"stored {min(start + UPSERT_BATCH, len(rows))}/{len(rows)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
