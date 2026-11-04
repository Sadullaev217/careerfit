from dataclasses import dataclass
from typing import Any, Protocol

from app.embeddings import embed_texts
from app.profile_schema import ExtractedProfile

# Measured on real ESCO data: lower values accept errors like "React" -> "regulate chemical reaction".
# An unmapped skill keeps its name in the profile; a wrong mapping would corrupt the score.
MIN_MATCH_SIMILARITY = 0.85


class SkillIndex(Protocol):
    def match_skill(self, embedding: list[float]) -> dict[str, Any] | None: ...


@dataclass(frozen=True)
class SkillMatch:
    skill_id: str
    canonical_name: str
    esco_id: str | None
    similarity: float


def match_names(names: list[str], index: SkillIndex) -> list[SkillMatch | None]:
    if not names:
        return []
    results: list[SkillMatch | None] = []
    for embedding in embed_texts(names):
        row = index.match_skill(embedding)
        if row is None or row["similarity"] < MIN_MATCH_SIMILARITY:
            results.append(None)
        else:
            results.append(SkillMatch(row["id"], row["name"], row["esco_id"], row["similarity"]))
    return results


def profile_skill_rows(
    profile: ExtractedProfile, user_id: str, document_id: str, index: SkillIndex
) -> list[dict[str, Any]]:
    matches = match_names([skill.name_en for skill in profile.skills], index)
    rows: dict[str, dict[str, Any]] = {}
    for skill, match in zip(profile.skills, matches, strict=True):
        if match is None:
            continue
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
    return list(rows.values())
