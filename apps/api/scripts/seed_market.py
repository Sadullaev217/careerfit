"""Loads job postings, occupations and each occupation's skills.

Usage: python -m scripts.seed_market [--skills-only | --postings-only]
Needs data/noc_esco_map.json from scripts.build_occupation_map, plus the ESCO skills loaded.
"""

import argparse
import sys
from typing import Any

import numpy as np

from app import store
from app.embeddings import embed_texts
from app.job_sources import JobBankProvider
from app.market_data import UPSERT_BATCH, load_occupation_map, refresh_market_data
from scripts.build_occupation_map import load_esco_occupations

# ESCO's optional lists are noisy, such as "film production process" for accountants,
# so only those closest to the occupation are kept.
MAX_PREFERRED_SKILLS = 15


def rank_by_relevance(occupation_label: str, skill_names: list[str]) -> list[int]:
    """Indexes of skill_names, most relevant first."""
    if not skill_names:
        return []
    vectors = np.array(embed_texts([occupation_label, *skill_names]))
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    scores = vectors[1:] @ vectors[0]
    return [int(index) for index in np.argsort(scores)[::-1]]


def occupation_skill_rows(
    code: str, occupation: dict[str, Any], skill_ids: dict[str, str], skill_titles: dict[str, str]
) -> list[dict[str, Any]]:
    label = occupation["title"]
    rows: dict[str, dict[str, Any]] = {}

    essential = [uri for uri in occupation["essential_skills"] if uri in skill_ids]
    names = [skill_titles.get(uri, "") for uri in essential]
    for rank, index in enumerate(rank_by_relevance(label, names)):
        skill_id = skill_ids[essential[index]]
        rows[skill_id] = {"occupation_code": code, "skill_id": skill_id, "required": True, "rank": rank}

    optional = [item for item in occupation["optional_skills"] if item["uri"] in skill_ids]
    order = rank_by_relevance(label, [item["title"] for item in optional])
    for rank, index in enumerate(order[:MAX_PREFERRED_SKILLS]):
        skill_id = skill_ids[optional[index]["uri"]]
        rows.setdefault(
            skill_id,
            {"occupation_code": code, "skill_id": skill_id, "required": False, "rank": rank},
        )
    return list(rows.values())


def load_skills() -> None:
    occupation_map = load_occupation_map()
    esco = {occupation["uri"]: occupation for occupation in load_esco_occupations()}
    skill_ids = store.skill_ids_by_esco_uri()
    print(f"ESCO skills available: {len(skill_ids)}", flush=True)

    titles = store.skill_names_by_esco_uri()
    batch: list[dict[str, Any]] = []
    linked = 0
    for code, row in occupation_map.items():
        occupation = esco.get(row.get("esco_uri") or "")
        if occupation is None:
            continue
        linked += 1
        batch += occupation_skill_rows(code, occupation, skill_ids, titles)
        if len(batch) >= UPSERT_BATCH:
            store.replace_occupation_skills(batch)
            batch = []
    if batch:
        store.replace_occupation_skills(batch)
    print(f"skills loaded for {linked} of {len(occupation_map)} occupations", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills-only", action="store_true")
    parser.add_argument("--postings-only", action="store_true")
    args = parser.parse_args()

    if not args.skills_only:
        print(refresh_market_data(JobBankProvider(), store, embed_texts), flush=True)
    if not args.postings_only:
        load_skills()
    return 0


if __name__ == "__main__":
    sys.exit(main())
