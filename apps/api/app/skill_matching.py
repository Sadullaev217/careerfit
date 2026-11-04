import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.embeddings import embed_texts
from app.profile_schema import ExtractedProfile

# Measured on real ESCO data: lower values accept errors like "React" -> "regulate chemical reaction".
# An unmapped skill keeps its name in the profile; a wrong mapping would corrupt the score.
MIN_MATCH_SIMILARITY = 0.85

_WORD = re.compile(r"[a-z0-9+#]+")
_IGNORED_WORDS = {"a", "an", "and", "for", "in", "of", "on", "the", "to", "use", "with"}
# Long enough that "mentoring" matches "mentor", short enough that "negotiation" matches "negotiate".
_STEM_LENGTH = 5
# Lets "menu" match "menus" without letting "java" match "javascript".
_MAX_SHORT_WORD_SUFFIX = 3


class SkillIndex(Protocol):
    def match_skill(self, embedding: list[float]) -> dict[str, Any] | None: ...


@dataclass(frozen=True)
class SkillMatch:
    skill_id: str
    canonical_name: str
    esco_id: str | None
    similarity: float


def _words(text: str) -> set[str]:
    return set(_WORD.findall(text.lower())) - _IGNORED_WORDS


def _same_word(a: str, b: str) -> bool:
    shorter, longer = sorted((a, b), key=len)
    if len(shorter) >= _STEM_LENGTH:
        return longer.startswith(shorter[:_STEM_LENGTH])
    return longer.startswith(shorter) and len(longer) - len(shorter) <= _MAX_SHORT_WORD_SUFFIX


def shares_a_word(name: str, label: str) -> bool:
    """Real use showed why: unfamiliar tool names score highly against unrelated brand names,
    such as "Jotai" -> "Grovo" at 0.90, so similarity alone can't be trusted."""
    return any(_same_word(a, b) for a in _words(name) for b in _words(label))


def match_names(names: list[str], index: SkillIndex) -> list[SkillMatch | None]:
    if not names:
        return []
    results: list[SkillMatch | None] = []
    for name, embedding in zip(names, embed_texts(names), strict=True):
        row = index.match_skill(embedding)
        if (
            row is None
            or row["similarity"] < MIN_MATCH_SIMILARITY
            or not shares_a_word(name, row["name"])
        ):
            results.append(None)
        else:
            results.append(SkillMatch(row["id"], row["name"], row["esco_id"], row["similarity"]))
    return results


@dataclass(frozen=True)
class ProfileSkills:
    rows: list[dict[str, Any]]
    matches: list[dict[str, Any]]


def profile_skills(
    profile: ExtractedProfile, user_id: str, document_id: str, index: SkillIndex
) -> ProfileSkills:
    found = match_names([skill.name_en for skill in profile.skills], index)
    rows: dict[str, dict[str, Any]] = {}
    matches: list[dict[str, Any]] = []
    for skill, match in zip(profile.skills, found, strict=True):
        if match is None:
            continue
        matches.append(
            {
                "source_name": skill.name_en,
                "canonical_name": match.canonical_name,
                "esco_id": match.esco_id,
                "match_score": round(match.similarity, 2),
            }
        )
        # Two resume phrases can map to one canonical skill: keep the surest one.
        current = rows.get(match.skill_id)
        if current is not None and current["confidence"] >= skill.confidence:
            continue
        rows[match.skill_id] = {
            "user_id": user_id,
            "skill_id": match.skill_id,
            "level": None if skill.level == "unknown" else skill.level,
            "years": skill.years,
            "confidence": skill.confidence,
            "match_score": round(match.similarity, 2),
            "source_name": skill.name_en,
            "source_document_id": document_id,
        }
    return ProfileSkills(list(rows.values()), matches)
