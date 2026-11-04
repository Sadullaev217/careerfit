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
    | \b(list|mark|rate|rank|score|treat)\s+this\s+(candidate|applicant|person|resume)\b
    | \b(укажи|отметь|оцени)\s+(этого|данного)\s+кандидата\b
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


# Short label lines like "Nationality: X" have no end punctuation either, and must not swallow the next line.
_WRAPPED_LINE_MIN_CHARS = 60
_SENTENCE_ENDINGS = (".", "!", "?", ":", ";")
_MAX_CONTINUATION_LINES = 3


@dataclass(frozen=True)
class SanitizedResume:
    text: str
    personal_lines_removed: int
    instruction_lines_removed: int


def _looks_wrapped(line: str) -> bool:
    stripped = line.rstrip()
    return len(stripped) >= _WRAPPED_LINE_MIN_CHARS and not stripped.endswith(_SENTENCE_ENDINGS)


def _matches(pattern: re.Pattern[str], line: str, following: str | None) -> bool:
    if pattern.search(line):
        return True
    # PDF text wraps, so a trigger phrase can start on one line and finish on the next.
    # A match wholly on the next line is left for that line, so this one isn't lost with it.
    if following is None or not _looks_wrapped(line) or pattern.search(following):
        return False
    return bool(pattern.search(f"{line} {following}"))


def sanitize_resume(text: str) -> SanitizedResume:
    lines = text.splitlines()
    kept: list[str] = []
    personal = instruction = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        following = lines[index + 1] if index + 1 < len(lines) else None

        if _matches(_INSTRUCTION, line, following):
            instruction += 1
        elif _matches(_PERSONAL, line, following):
            personal += 1
        else:
            kept.append(line)
            index += 1
            continue

        # The rest of a wrapped sentence must go too, or a fragment reads as a plain fact.
        index += 1
        for _ in range(_MAX_CONTINUATION_LINES):
            if index >= len(lines) or not lines[index].strip() or not _looks_wrapped(line):
                break
            line = lines[index]
            index += 1
    return SanitizedResume("\n".join(kept), personal, instruction)
