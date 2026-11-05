"""Gathers everything the score needs. Saved judgements make repeat analyses match exactly."""

from datetime import date
from typing import Any, Protocol

from app.llm import LLMClient
from app.market_lookup import NATIONAL, requirements, salary_range, top_skills
from app.messages import Language
from app.profile_schema import ExtractedProfile
from app.scoring import JudgedSkill, MarketSnapshot, ScoreInput, ScoreResult, score_profile
from app.skill_judgement import Embed, judge_skills, judgement_key


class AnalysisStore(Protocol):
    def market_stats(self, occupation_code: str, region: str | None) -> dict[str, Any]: ...
    def occupation_skills(self, occupation_code: str) -> list[dict[str, Any]]: ...
    def list_documents(self, user_id: str) -> list[dict[str, Any]]: ...
    def get_skill_judgement(self, document_id: str, key: str) -> dict[str, Any] | None: ...
    def save_skill_judgement(self, document_id: str, key: str, result: dict[str, Any]) -> None: ...


def _judgements(
    profile: ExtractedProfile,
    document_id: str,
    occupation_name: str,
    required: list[str],
    preferred: list[str],
    store: AnalysisStore,
    llm: LLMClient,
    embed: Embed,
) -> dict[str, Any]:
    key = judgement_key(profile, occupation_name, required, preferred, llm.model)
    saved = store.get_skill_judgement(document_id, key)
    if saved is not None:
        return saved
    judged = judge_skills(profile, occupation_name, required, preferred, llm, embed)
    result = {
        "required": [skill.model_dump() for skill in judged.required],
        "preferred": [skill.model_dump() for skill in judged.preferred],
        "relevant_job_indexes": judged.relevant_job_indexes,
        "relevant_credential_indexes": judged.relevant_credential_indexes,
    }
    store.save_skill_judgement(document_id, key, result)
    return result


def analyze(
    *,
    extraction: dict[str, Any],
    document_id: str,
    user_id: str,
    occupation_code: str,
    occupation_name: str,
    region: str | None,
    as_of: date,
    store: AnalysisStore,
    llm: LLMClient,
    embed: Embed,
    language: Language = "en",
) -> ScoreResult:
    return score_profile(
        prepare_score_input(
            extraction=extraction,
            document_id=document_id,
            user_id=user_id,
            occupation_code=occupation_code,
            occupation_name=occupation_name,
            region=region,
            as_of=as_of,
            store=store,
            llm=llm,
            embed=embed,
            language=language,
        )
    )


def prepare_score_input(
    *,
    extraction: dict[str, Any],
    document_id: str,
    user_id: str,
    occupation_code: str,
    occupation_name: str,
    region: str | None,
    as_of: date,
    store: AnalysisStore,
    llm: LLMClient,
    embed: Embed,
    language: Language = "en",
) -> ScoreInput:
    profile = ExtractedProfile.model_validate(extraction["data"])
    stats = store.market_stats(occupation_code, region)
    required, preferred = top_skills(store.occupation_skills(occupation_code))

    judged = _judgements(profile, document_id, occupation_name, required, preferred, store, llm, embed)
    links = sum(
        row["type"] == "portfolio_link" and row["status"] == "ready"
        for row in store.list_documents(user_id)
    )
    education, experience, used_national = requirements(occupation_code, region, stats, store)
    return ScoreInput(
        profile=profile,
        market=MarketSnapshot(
            occupation_code=occupation_code,
            occupation_name=occupation_name,
            region=region or NATIONAL,
            sample_size=stats["sample_size"],
            education=education,
            experience=experience,
            salary=salary_range(occupation_code, region, stats, store),
            latest_posting=stats["latest_posting"],
            used_national_requirements=used_national,
        ),
        required=[JudgedSkill.model_validate(item) for item in judged["required"]],
        preferred=[JudgedSkill.model_validate(item) for item in judged["preferred"]],
        relevant_job_indexes=judged["relevant_job_indexes"],
        relevant_credential_indexes=judged["relevant_credential_indexes"],
        portfolio_links=links,
        as_of=as_of,
        suspicious_content=bool(extraction.get("suspicious_content")),
        truncated=bool(extraction.get("truncated")),
        language=language,
    )
