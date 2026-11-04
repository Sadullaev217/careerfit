"""Scores the extractor on eval/resumes.json. Usage: python -m eval.run_eval [--model NAME] [--out FILE]"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from app.config import settings
from app.extraction import ExtractionFailed, extract_profile
from app.llm import LLMUnavailable, OllamaClient
from eval.scoring import CHECKS, score_profile

RESUMES = Path(__file__).parent / "resumes.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=settings.llm_model)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    llm = OllamaClient(settings.ollama_url, args.model, settings.llm_timeout_seconds)
    resumes = json.loads(RESUMES.read_text(encoding="utf-8"))
    per_check: dict[str, list[float]] = {check: [] for check in CHECKS}
    report = []
    valid = 0
    seconds: list[float] = []

    for resume in resumes:
        started = time.perf_counter()
        try:
            result = extract_profile(resume["text"], llm)
        except LLMUnavailable as exc:
            print(f"Could not reach the model: {exc}")
            return 2
        except ExtractionFailed as exc:
            elapsed = time.perf_counter() - started
            seconds.append(elapsed)
            print(f"{resume['id']:<16} FAILED {exc.code} in {elapsed:.0f}s")
            report.append({"id": resume["id"], "error": exc.code})
            continue
        elapsed = time.perf_counter() - started
        seconds.append(elapsed)
        valid += 1
        scores = score_profile(result.profile, resume["expected"])
        for check, value in scores.items():
            per_check[check].append(value)
        overall = statistics.mean(scores.values())
        misses = {check: round(value, 2) for check, value in scores.items() if value < 1}
        print(
            f"{resume['id']:<16} {overall:5.0%} in {elapsed:3.0f}s, attempts {result.attempts}, "
            f"skills found {len(result.profile.skills)}, misses {misses}"
        )
        report.append(
            {
                "id": resume["id"],
                "scores": scores,
                "seconds": elapsed,
                "attempts": result.attempts,
                "profile": result.profile.model_dump(),
            }
        )

    print(f"\nmodel: {args.model}")
    print(f"valid structured output: {valid}/{len(resumes)}")
    for check in CHECKS:
        values = per_check[check]
        if values:
            print(f"{check:<20} {statistics.mean(values):5.0%}  ({len(values)} resumes)")
    all_scores = [value for values in per_check.values() for value in values]
    if all_scores:
        print(f"{'overall accuracy':<20} {statistics.mean(all_scores):5.0%}")
    print(f"{'mean seconds':<20} {statistics.mean(seconds):5.1f}")

    if args.out:
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
