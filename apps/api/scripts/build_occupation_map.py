"""Links Canadian occupations to ESCO ones, writing data/noc_esco_map.json for review and commit.

Similarity alone linked millwrights to milliners, so it only shortlists and the AI decides.
Run rarely: python -m scripts.build_occupation_map [--limit N]. It can be stopped and resumed.
"""

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import numpy as np
from pydantic import BaseModel, ValidationError

from app.embeddings import embed_texts
from app.job_sources import JobBankProvider
from app.llm import LLMClient, LLMUnavailable, get_llm

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "data" / "noc_esco_map.json"
CACHE_PATH = ROOT / ".cache" / "esco_occupations.json"
SEARCH_URL = "https://ec.europa.eu/esco/api/search?type=occupation&language=en&limit=100&full=false"
DETAIL_URL = "https://ec.europa.eu/esco/api/resource/occupation"
REQUEST_DELAY_SECONDS = 0.2
FETCH_ATTEMPTS = 4
RETRY_BASE_SECONDS = 2
FALLBACK_VERSION = "v1.2.0"
SHORTLIST_SIZE = 8
TOP_TITLES = 4
MAX_ATTEMPTS = 2

SYSTEM_PROMPT = """You match a Canadian occupation to the same occupation in a European list.

You get the Canadian occupation with its common job titles, then numbered candidates. Choose the one
candidate describing the same work at the same level, so that its skills would apply to this person.
A nurse aide is not a nurse practitioner, and a food server is not a packaging technologist. Similar
words are not enough. A somewhat broader or narrower candidate is fine if the core work is the same.
If no candidate does the same work, answer 0.

Return only JSON: {"choice": <candidate number, or 0 for none>}"""


class Choice(BaseModel):
    choice: int


def _get_json(client: httpx.Client, url: str, **params: Any) -> dict[str, Any]:
    if urlsplit(url).hostname != "ec.europa.eu":
        raise RuntimeError("ESCO pointed at another host")
    for attempt in range(FETCH_ATTEMPTS):
        try:
            response = client.get(
                url, params=params or None, headers={"Accept": "application/json"}
            )
            # Other 4xx errors won't change on retry.
            if response.status_code < 500 and response.status_code != 429:
                response.raise_for_status()
                body: dict[str, Any] = response.json()
                return body
            failure: Exception = httpx.HTTPStatusError(
                f"ESCO returned {response.status_code}", request=response.request, response=response
            )
        except httpx.TransportError as exc:
            failure = exc
        if attempt + 1 < FETCH_ATTEMPTS:
            time.sleep(RETRY_BASE_SECONDS * 2**attempt)
    raise failure


def _english(field: dict[str, Any] | None) -> Any:
    return (field or {}).get("en")


def summarize_occupation(detail: dict[str, Any]) -> dict[str, Any]:
    links = detail.get("_links", {})
    description = _english(detail.get("description")) or {}
    return {
        "uri": detail["uri"],
        "title": detail["title"],
        "alternatives": _english(detail.get("alternativeLabel")) or [],
        "description": description.get("literal", "") if isinstance(description, dict) else "",
        "essential_skills": [skill["uri"] for skill in links.get("hasEssentialSkill", [])],
        "optional_skills": [
            {"uri": skill["uri"], "title": skill["title"]}
            for skill in links.get("hasOptionalSkill", [])
        ],
    }


def fetch_occupation(client: httpx.Client, uri: str) -> dict[str, Any]:
    try:
        return summarize_occupation(_get_json(client, DETAIL_URL, language="en", uri=uri))
    except httpx.HTTPStatusError:
        # A few records, including civil engineer, fail on the default version but load on this one.
        return summarize_occupation(
            _get_json(client, DETAIL_URL, language="en", uri=uri, selectedVersion=FALLBACK_VERSION)
        )


def load_esco_occupations() -> list[dict[str, Any]]:
    """Cached and resumable, because this takes many requests."""
    cached: dict[str, dict[str, Any]] = {}
    if CACHE_PATH.exists():
        cached = {o["uri"]: o for o in json.loads(CACHE_PATH.read_text(encoding="utf-8"))}

    with httpx.Client(timeout=60, trust_env=False) as client:
        uris: list[str] = []
        url: str | None = SEARCH_URL
        while url:
            body = _get_json(client, url)
            uris += [result["uri"] for result in body["_embedded"]["results"]]
            url = body["_links"].get("next", {}).get("href")
            time.sleep(REQUEST_DELAY_SECONDS)

        missing = [uri for uri in uris if uri not in cached]
        print(f"ESCO occupations: {len(uris)}, already cached: {len(uris) - len(missing)}", flush=True)
        CACHE_PATH.parent.mkdir(exist_ok=True)
        failed = 0
        for done, uri in enumerate(missing, start=1):
            try:
                cached[uri] = fetch_occupation(client, uri)
            except httpx.HTTPError as exc:
                # One bad record shouldn't lose the rest. A rerun tries the skipped ones again.
                failed += 1
                print(f"skipped {uri}: {type(exc).__name__}", flush=True)
            if done % 100 == 0:
                CACHE_PATH.write_text(json.dumps(list(cached.values())), encoding="utf-8")
                print(f"fetched {done}/{len(missing)}, skipped {failed}", flush=True)
            time.sleep(REQUEST_DELAY_SECONDS)

    CACHE_PATH.write_text(json.dumps(list(cached.values())), encoding="utf-8")
    print(f"ESCO occupations cached: {len(cached)} of {len(uris)}", flush=True)
    return list(cached.values())


def load_canadian_occupations() -> list[dict[str, Any]]:
    names: dict[str, str] = {}
    titles: dict[str, Counter[str]] = defaultdict(Counter)
    seen: set[str] = set()
    for posting in JobBankProvider().fetch():
        names[posting.occupation_code] = posting.occupation_name
        # Counted once per ad, so repeated spam can't decide an occupation's common titles.
        if posting.duplicate_key not in seen:
            seen.add(posting.duplicate_key)
            titles[posting.occupation_code][posting.title] += 1
    occupations = [
        {
            "code": code,
            "name": name,
            "titles": [title for title, _ in titles[code].most_common(TOP_TITLES)],
            "postings": sum(titles[code].values()),
        }
        for code, name in names.items()
    ]
    return sorted(occupations, key=lambda item: -int(item["postings"]))


def build_shortlists(
    canadian: list[dict[str, Any]], esco: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    labels: list[str] = []
    owners: list[int] = []
    for index, occupation in enumerate(esco):
        for label in [occupation["title"], *occupation["alternatives"]]:
            labels.append(label)
            owners.append(index)
    matrix = np.array(embed_texts(labels))
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)

    shortlists: dict[str, list[dict[str, Any]]] = {}
    for item in canadian:
        queries = [item["name"], *item["titles"]]
        vectors = np.array(embed_texts(queries))
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        scores = (matrix @ vectors.T).max(axis=1)
        best: dict[int, float] = {}
        for position in np.argsort(scores)[::-1]:
            owner = owners[int(position)]
            if owner not in best:
                best[owner] = float(scores[int(position)])
            if len(best) == SHORTLIST_SIZE:
                break
        shortlists[item["code"]] = [{**esco[owner], "score": score} for owner, score in best.items()]
    return shortlists


def choose_match(
    occupation: dict[str, Any], candidates: list[dict[str, Any]], llm: LLMClient
) -> dict[str, Any] | None:
    numbered = "\n".join(
        f"{number}. {candidate['title']}: {candidate['description'][:220]}"
        for number, candidate in enumerate(candidates, start=1)
    )
    user = (
        f"Canadian occupation: {occupation['name']}\n"
        f"Common job titles: {', '.join(occupation['titles'])}\n\nCandidates:\n{numbered}"
    )
    for attempt in range(MAX_ATTEMPTS):
        raw = llm.complete_json(SYSTEM_PROMPT, user, Choice.model_json_schema(), attempt)
        try:
            choice = Choice.model_validate_json(raw).choice
        except ValidationError:
            continue
        if choice == 0:
            return None
        if 1 <= choice <= len(candidates):
            return candidates[choice - 1]
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    esco = load_esco_occupations()
    canadian = load_canadian_occupations()
    if args.limit:
        canadian = canadian[: args.limit]
    print(f"Canadian occupations: {len(canadian)}", flush=True)

    existing: dict[str, Any] = {}
    if MAP_PATH.exists():
        existing = {row["code"]: row for row in json.loads(MAP_PATH.read_text(encoding="utf-8"))}
    todo = [item for item in canadian if item["code"] not in existing]
    shortlists = build_shortlists(todo, esco) if todo else {}
    llm = get_llm()
    MAP_PATH.parent.mkdir(exist_ok=True)

    def save() -> None:
        rows = sorted(existing.values(), key=lambda row: row["code"])
        MAP_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    for done, item in enumerate(todo, start=1):
        try:
            match = choose_match(item, shortlists[item["code"]], llm)
        except LLMUnavailable as exc:
            save()
            print(f"Could not reach the model: {exc}. Rerun to continue.", flush=True)
            return 2
        existing[item["code"]] = {
            "code": item["code"],
            "name": item["name"],
            "titles": item["titles"],
            "esco_uri": match["uri"] if match else None,
            "esco_title": match["title"] if match else None,
            "similarity": round(match["score"], 3) if match else None,
        }
        if done % 25 == 0:
            save()
            print(f"matched {done}/{len(todo)}", flush=True)
    save()
    linked = sum(1 for row in existing.values() if row["esco_uri"])
    print(f"done: {linked}/{len(existing)} occupations linked", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
