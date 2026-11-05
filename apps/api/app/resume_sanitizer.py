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
    | ^\s*(full\s+)?name\s*[:\-–—]
    | ^\s*(фио|имя)\s*[:\-–—]
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

# Phone formats are spelled out because a looser pattern also matches date ranges like 2019-01 - 2021-03.
_CONTACT = re.compile(
    r"""
    [\w.+-]+@[\w-]+\.[\w.-]+
    | (https?://|www\.)\S+
    | \b(linkedin|github)\.com/\S*
    | \+\d[\d\s().-]{7,}\d
    | (\b[78][\s-]?)?\(\d{3}\)[\s-]?\d{2,3}[\s-]?\d{2}[\s-]?\d{2}\b
    | \b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

_NAME_WORD = re.compile(r"^[^\W\d_]+(?:['’-][^\W\d_]+)*\.?$")
_NAME_SEPARATORS = re.compile(r"[|•·,]|\s[-–—]\s")
_NAME_PARTICLES = frozenset(
    [
        "al",
        "ben",
        "bin",
        "binti",
        "da",
        "de",
        "del",
        "den",
        "der",
        "di",
        "dos",
        "du",
        "el",
        "ibn",
        "la",
        "le",
        "ter",
        "van",
        "von",
    ]
)
# A heading or a job title on the first line isn't a name. Missing one here only loses that line.
_NOT_NAME_WORDS = frozenset(
    [
        "accountant",
        "administrator",
        "analyst",
        "architect",
        "assistant",
        "attorney",
        "chef",
        "consultant",
        "contact",
        "cook",
        "coordinator",
        "curriculum",
        "cv",
        "designer",
        "developer",
        "director",
        "driver",
        "education",
        "employment",
        "engineer",
        "experience",
        "history",
        "languages",
        "lawyer",
        "manager",
        "nurse",
        "objective",
        "officer",
        "profile",
        "programmer",
        "projects",
        "references",
        "resume",
        "résumé",
        "scientist",
        "skills",
        "specialist",
        "summary",
        "teacher",
        "technician",
        "vitae",
        "welder",
        "work",
        "аналитик",
        "бухгалтер",
        "водитель",
        "врач",
        "директор",
        "инженер",
        "менеджер",
        "медсестра",
        "навыки",
        "образование",
        "опыт",
        "повар",
        "программист",
        "работы",
        "разработчик",
        "резюме",
        "сварщик",
        "специалист",
        "учитель",
        "юрист",
    ]
)
_MIN_NAME_WORDS = 2
_MAX_NAME_WORDS = 5
_MAX_NAME_LINE_WORDS = 10


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


def _name_on_line(line: str) -> str | None:
    """Names signal background without saying anything about ability, so the AI shouldn't see them."""
    if ":" in line or any(char.isdigit() for char in line):
        return None
    if len(line.split()) > _MAX_NAME_LINE_WORDS:
        return None
    candidate = _NAME_SEPARATORS.split(line, maxsplit=1)[0].strip()
    words = candidate.split()
    if not _MIN_NAME_WORDS <= len(words) <= _MAX_NAME_WORDS:
        return None
    capitalised = 0
    for word in words:
        lowered = word.lower().rstrip(".")
        if lowered in _NOT_NAME_WORDS:
            return None
        if lowered in _NAME_PARTICLES:
            continue
        if not _NAME_WORD.match(word) or not word[0].isupper():
            return None
        capitalised += 1
    return candidate if capitalised >= _MIN_NAME_WORDS else None


def _without_name(lines: list[str]) -> tuple[list[str], int]:
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        name = _name_on_line(line.strip())
        if name is None:
            return lines, 0
        # It can come back later in a page footer or sign-off.
        pattern = re.compile(re.escape(name), re.IGNORECASE)
        return [pattern.sub("", other) for other in lines[index + 1 :]], 1
    return lines, 0


def _without_contact_details(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    for line in lines:
        stripped = _CONTACT.sub("", line)
        if stripped == line:
            cleaned.append(line)
        elif stripped.strip(" |•·,;:-–—\t"):
            cleaned.append(stripped.rstrip(" |•·,;:-–—\t"))
    return cleaned


def sanitize_resume(text: str) -> SanitizedResume:
    lines = _without_contact_details(text.splitlines())
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
    kept, names_removed = _without_name(kept)
    return SanitizedResume("\n".join(kept), personal + names_removed, instruction)
