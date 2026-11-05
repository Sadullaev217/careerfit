"""Translates occupation names ahead of time, so searching in Russian shows Russian names straight away.

Usage: python -m scripts.seed_translations [--language ru]
Skill names are translated when a report first needs them. Already translated names are skipped.
"""

import argparse

from app import store
from app.llm import get_llm
from app.localization import translate_terms

# The local model keeps handing these back in English.
FIXED_NAMES = {"ru": {"Data scientists": "Специалисты по анализу данных"}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", default="ru")
    args = parser.parse_args()
    if args.language in FIXED_NAMES:
        store.save_translations(FIXED_NAMES[args.language], args.language)
    names = [row["name"] for row in store.list_occupations()]
    found = translate_terms(names, args.language, get_llm(), store)
    print(f"{len(found)} of {len(names)} occupation names translated into {args.language}")


if __name__ == "__main__":
    main()
