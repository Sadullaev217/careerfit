"""Removes lines before the AI sees them. Prompt rules alone failed in evaluation on both models.

These patterns reduce risk but can't catch every wording, so model output is still untrusted.
"""

import re
from dataclasses import dataclass

_INSTRUCTION = re.compile(
    r"""
    \b(ignore|disregard|forget)\s+(all\s+|any\s+|the\s+|your\s+)*(previous|prior|above|earlier|preceding)\b
    | \b(instruction|instructions|note|message|prompt)\s+(to|for)\s+(the\s+)?
      ((ai|llm|chatbot|gpt|claude)\b | (assistant|model)(?=\s*([:.,;]|$)))
    | \bsystem\s+prompt\b
    | \byou\s+are\s+(now\s+)?(an?\s+|the\s+)?(ai|assistant|language\s+model)\b
    | \bset\s+(every|all|each)\s+confidence\b
    | \b(проигнорируй|игнорируй|забудь)\b.{0,40}\b(инструкци|предыдущ|прошл|указани)
    | \b(инструкци[яию]|указани[ея]|сообщение)\s+для\s+(ии|ai|модели|ассистента|нейросети|бота)\b
    | \bсистемн\w+\s+(промпт|инструкци)
    """,
    re.IGNORECASE | re.VERBOSE,
)

_PERSONAL = re.compile(
    r"""
    \b(date\s+of\s+birth|d\.o\.b\.?|nationality|citizenship|marital\s+status|religion)\b
    | \b(married|divorced|widowed)\s*[.,;]
    | ^\s*(dob|gender|sex)\s*[:\-–—]
    | ^\s*(female|male)\s*([.,;:]|$)
    | ^\s*age\s*[:\-–—]?\s*\d{2}\b
    | \b(us|uk|eu)\s+citizen\b
    | \b(дата\s+рождения|гражданство|семейное\s+положение|национальность|вероисповедание|религия)\b
    | \b(замужем|женат|разведен|разведена|вдова|вдовец)\b
    | ^\s*(пол|возраст)\s*[:\-–—]
    | ^\s*(женщина|мужчина)\s*([.,;:]|$)
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)


@dataclass(frozen=True)
class SanitizedResume:
    text: str
    personal_lines_removed: int
    instruction_lines_removed: int


def sanitize_resume(text: str) -> SanitizedResume:
    kept: list[str] = []
    personal = instruction = 0
    for line in text.splitlines():
        if _INSTRUCTION.search(line):
            instruction += 1
        elif _PERSONAL.search(line):
            personal += 1
        else:
            kept.append(line)
    return SanitizedResume("\n".join(kept), personal, instruction)
