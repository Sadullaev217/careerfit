"""Everything a report says in our own words, in each language the site supports."""

from typing import Literal, get_args

Language = Literal["en", "ru"]
LANGUAGES: tuple[str, ...] = get_args(Language)

_EN = {
    "category.required_skills": "Required skills",
    "category.preferred_skills": "Other useful skills",
    "category.experience": "Relevant experience",
    "category.education": "Education",
    "category.portfolio": "Portfolio",
    "category.seniority": "Seniority",
    "what.required": "required skills",
    "what.preferred": "other useful skills",
    "skills.no_list": "We don't have a reliable list of {what} for this occupation.",
    "skills.checked": (
        "Your resume shows {shown} and partly shows {partly} of the {total} {what} we checked. "
        "Covering {percent}% earns full marks."
    ),
    "experience.not_stated": "Job ads for this role rarely state the experience wanted.",
    "experience.found": "You have {years} of relevant experience, counting: {titles}.",
    "experience.none": "We didn't find jobs in this occupation on your resume.",
    "experience.undated": " {count} of these had no usable dates, so they aren't counted.",
    "experience.not_required": "Most ads for this role don't require experience. {found}{note}",
    "experience.target": "{found}{note} Typical ads ask for about {target}.",
    "education.not_stated": "Job ads for this role rarely state the education wanted.",
    "education.none": "Typical ads ask for {wanted}. We couldn't find a credential on your resume.",
    "education.other_field": "Typical ads ask for {wanted}. You have {name}, but not clearly in this field.",
    "education.met": "Typical ads ask for {wanted}, and you have {name}.",
    "education.below": "Typical ads ask for {wanted}, and we found {name}.",
    "education.level.0": "no formal credential",
    "education.level.1": "secondary school",
    "education.level.2": "a certificate or trade qualification",
    "education.level.3": "a college diploma",
    "education.level.4": "a bachelor's degree",
    "education.level.5": "a master's degree",
    "education.level.6": "a doctorate or medical degree",
    "portfolio.reason": (
        "Projects on your resume that back up skills for this role: {projects}. Portfolio links you "
        "added: {links}. {full} of these together earn full marks."
    ),
    "seniority.unknown": "We couldn't compare your level with this role.",
    "seniority.no_work": "We didn't find work in this occupation to compare your level with.",
    "seniority.compared": "Your resume reads as {level}, and typical ads suit {expected} level.",
    "seniority.level.intern": "intern",
    "seniority.level.junior": "junior",
    "seniority.level.mid": "mid",
    "seniority.level.senior": "senior",
    "seniority.level.lead": "lead",
    "seniority.level.executive": "executive",
    "salary.basis": (
        "Placed within the middle half of {count} job ads in {region}, based on your experience "
        "and skills.{caveat}"
    ),
    "salary.caveat": " Your match is low, so this is what you could reach once you qualify.",
    "confidence.few_ads": "Only {count} job ads for this role and region.",
    "confidence.no_ads": "No job ads for this role and region.",
    "confidence.moderate_ads": "A moderate number of job ads for this role and region ({count}).",
    "confidence.used_national": (
        "Few local ads state the education or experience wanted, so we used all of Canada."
    ),
    "confidence.little_skill_info": "There is little official skill information for this occupation.",
    "confidence.little_evidence": "Your resume gave us little to go on, so treat this as a rough guide.",
    "confidence.concentrated": "Most ads list the same pay, often from one employer or pay scale.",
    "confidence.suspicious": "Your resume contained text aimed at AI tools, which we removed.",
    "confidence.truncated": "Your resume was very long, so only the first part was read.",
    "confidence.plenty": "Plenty of job ads and a full skill list for this occupation.",
    "not_weighed": "{label}: not usually weighed in this field.",
    "disclaimer": (
        "This is an estimate to help you plan, not a guarantee of being hired or of any salary. It was "
        "made with AI, which can make mistakes."
    ),
    "gap.partly": "Only partly shown on your resume.",
    "gap.missing": "Not found on your resume.",
    "gap.essential": "Essential in the official list for this occupation.",
    "gap.useful": "Useful in the official list for this occupation.",
    "gap.experience": "Experience in this occupation",
    "gap.education": "The education employers usually ask for",
    "gap.portfolio": "Portfolio work that shows these skills",
    "action.experience.title": "Get practice in this line of work",
    "action.experience.details": (
        "Look for volunteering, a placement or an entry-level role in this occupation."
    ),
    "action.experience.expected": "Real experience you can add to your resume.",
    "action.education.title": "Check which credential employers expect",
    "action.education.details": (
        "Compare a few job ads you want, then see which programs lead to that credential."
    ),
    "action.education.expected": "A clear idea of the credential you need and where to get it.",
    "action.portfolio.title": "Add a project that shows your skills",
    "action.portfolio.details": (
        "Complete a small piece of work for this occupation and describe it on your resume."
    ),
    "action.portfolio.expected": "A finished example you can show employers.",
    "action.skill.title": "Build this skill: {skill}",
    "action.skill.details": (
        "Take a short course on this topic, then use it in real work or a small project."
    ),
    "action.skill.expected": "This skill, with an example you can add to your resume.",
    "plan.rewrites": "Update your resume using the suggested rewrites, where they're true for you",
    "plan.measure": "Run a new analysis with your updated resume to see your progress",
    "plan.with_effort": "{title} (about {duration})",
    "note.ranking": (
        "Gaps are ranked by their effect on your score, using the official skill list for this "
        "occupation. The job ads we use don't list skills, so we can't say how often employers ask "
        "for each one."
    ),
    "note.missing": (
        "A skill marked as not found may just be missing from your resume. If you have it, add it "
        "with a real example."
    ),
    "note.effort": (
        "Effort is a rough estimate, and suggestions were written by AI. Check that a course or "
        "certification is current and suits you before paying for it."
    ),
    "note.strong": "Your match is already strong, so treat these as optional extras.",
    "note.licence": (
        "This work may need a licence or registration where you live. Check with the provincial "
        "regulator or a professional association."
    ),
    "note.low": (
        "This job is a long way from your current background, so the other roles below may be a "
        "quicker route."
    ),
    "alternative.shown": "You show {shown} and partly show {partly} of the {total} required skills.",
    "alternative.shown_including": (
        "You show {shown} and partly show {partly} of the {total} required skills, including {name}."
    ),
    "alternative.experience": "Your experience meets what typical ads ask for.",
    "alternative.add": "The main thing to add: {name}.",
    "evidence.skill": "Skill: ",
    "evidence.job": "Job title: ",
    "evidence.project": "Project: ",
    "evidence.degree": "Degree: ",
    "evidence.certification": "Certification: ",
    "evidence.related": " (a related skill)",
    "push.report_ready_title": "Your CareerFit report is ready",
    "push.report_ready_body": "Tap to see your score and your plan.",
    "pdf.title": "CareerFit detailed report",
    "pdf.prepared": "Prepared {date} · Market data as of {as_of}",
    "pdf.score": "Match score: {score} out of 100",
    "pdf.confidence": "Confidence: {level}",
    "pdf.confidence.low": "low",
    "pdf.confidence.medium": "medium",
    "pdf.confidence.high": "high",
    "pdf.breakdown": "How the score adds up",
    "pdf.points": "{points} of {max} points",
    "pdf.not_scored": "Not scored: {items}",
    "pdf.salary": "Likely yearly pay for your profile",
    "pdf.salary_range": "{low} – {high} {currency}. The middle of the market is {median} {currency}.",
    "pdf.salary_basis": "Based on {count} job ads in {region}.",
    "pdf.skills": "Skills the job asks for",
    "pdf.required": "Required",
    "pdf.preferred": "Also useful",
    "pdf.level.yes": "shown",
    "pdf.level.partly": "partly shown",
    "pdf.level.no": "not found",
    "pdf.gaps": "What's missing",
    "pdf.plan": "Your 30, 60 and 90 day plan",
    "pdf.plan.thirty": "First 30 days",
    "pdf.plan.sixty": "Days 31 to 60",
    "pdf.plan.ninety": "Days 61 to 90",
    "pdf.plan.later": "Later",
    "pdf.actions": "Next steps in detail",
    "pdf.action_meta": "About {weeks} · {priority} priority",
    "pdf.priority.high": "high",
    "pdf.priority.medium": "medium",
    "pdf.priority.low": "low",
    "pdf.where": "Where to look: {providers}",
    "pdf.unsure": "This can depend on your province or employer.",
    "pdf.rewrites": "Resume lines to reword",
    "pdf.before": "Before",
    "pdf.after": "After",
    "pdf.alternatives": "Other roles to consider",
    "pdf.alternative": "{name}: {score} out of 100",
    "pdf.notes": "Notes",
    "pdf.about": "About this score",
    "pdf.page": "Page {page}",
}

_RU = {
    "category.required_skills": "Обязательные навыки",
    "category.preferred_skills": "Другие полезные навыки",
    "category.experience": "Подходящий опыт",
    "category.education": "Образование",
    "category.portfolio": "Портфолио",
    "category.seniority": "Уровень",
    "what.required": "обязательных навыков",
    "what.preferred": "других полезных навыков",
    "skills.no_list": "У нас нет надёжного перечня {what} для этой профессии.",
    "skills.checked": (
        "Проверено {what}: {total}. В резюме показано: {shown}, частично: {partly}. "
        "Максимальный балл даётся при охвате {percent}%."
    ),
    "experience.not_stated": "В объявлениях на эту работу редко указывают требуемый опыт.",
    "experience.found": "Ваш подходящий опыт: {years}. Учтено: {titles}.",
    "experience.none": "Мы не нашли в резюме работы по этой профессии.",
    "experience.undated": " Без понятных дат и поэтому не учтено: {count}.",
    "experience.not_required": "В большинстве объявлений опыт не требуется. {found}{note}",
    "experience.target": "{found}{note} Обычно в объявлениях просят примерно {target}.",
    "education.not_stated": "В объявлениях на эту работу редко указывают требуемое образование.",
    "education.none": "Обычно просят: {wanted}. Мы не нашли в резюме подходящего документа.",
    "education.other_field": (
        "Обычно просят: {wanted}. У вас: {name}, но не явно в этой области."
    ),
    "education.met": "Обычно просят: {wanted}. У вас: {name}.",
    "education.below": "Обычно просят: {wanted}. Мы нашли: {name}.",
    "education.level.0": "без официального документа",
    "education.level.1": "среднее школьное образование",
    "education.level.2": "сертификат или рабочая квалификация",
    "education.level.3": "диплом колледжа",
    "education.level.4": "степень бакалавра",
    "education.level.5": "степень магистра",
    "education.level.6": "докторская или медицинская степень",
    "portfolio.reason": (
        "Проектов в резюме, подтверждающих навыки для этой работы: {projects}. Добавлено ссылок на "
        "портфолио: {links}. Всего для максимального балла нужно: {full}."
    ),
    "seniority.unknown": "Мы не смогли сравнить ваш уровень с этой работой.",
    "seniority.no_work": "Мы не нашли работы по этой профессии, чтобы сравнить ваш уровень.",
    "seniority.compared": "Ваш уровень по резюме: {level}. Обычно объявлениям подходит: {expected}.",
    "seniority.level.intern": "стажёр",
    "seniority.level.junior": "начинающий специалист",
    "seniority.level.mid": "специалист среднего уровня",
    "seniority.level.senior": "старший специалист",
    "seniority.level.lead": "руководитель группы",
    "seniority.level.executive": "руководитель высшего звена",
    "salary.basis": (
        "Диапазон выбран внутри средней половины зарплат из объявлений ({count}, регион: {region}) "
        "с учётом вашего опыта и навыков.{caveat}"
    ),
    "salary.caveat": " Соответствие пока низкое, поэтому это то, на что можно рассчитывать после подготовки.",
    "confidence.few_ads": "Объявлений для этой работы и региона мало: {count}.",
    "confidence.no_ads": "Для этой работы и региона нет объявлений.",
    "confidence.moderate_ads": "Для этой работы и региона среднее число объявлений: {count}.",
    "confidence.used_national": (
        "Местные объявления редко указывают образование или опыт, поэтому мы учли всю Канаду."
    ),
    "confidence.little_skill_info": "Для этой профессии мало официальных данных о навыках.",
    "confidence.little_evidence": "В резюме мало сведений, поэтому считайте это примерным ориентиром.",
    "confidence.concentrated": (
        "В большинстве объявлений указана одна зарплата, часто от одного работодателя или по одной шкале."
    ),
    "confidence.suspicious": "В вашем резюме был текст, адресованный ИИ. Мы его удалили.",
    "confidence.truncated": "Резюме очень длинное, поэтому прочитана только его первая часть.",
    "confidence.plenty": "Много объявлений и полный перечень навыков для этой профессии.",
    "not_weighed": "{label}: обычно не учитывается в этой области.",
    "disclaimer": (
        "Это оценка, которая помогает планировать, а не гарантия трудоустройства или какой-либо "
        "зарплаты. Она сделана с помощью ИИ, который может ошибаться."
    ),
    "gap.partly": "В резюме показан лишь частично.",
    "gap.missing": "В резюме не найден.",
    "gap.essential": "В официальном перечне для этой профессии указан как обязательный.",
    "gap.useful": "В официальном перечне для этой профессии указан как полезный.",
    "gap.experience": "Опыт работы по этой профессии",
    "gap.education": "Образование, которое обычно просят работодатели",
    "gap.portfolio": "Работы в портфолио, показывающие эти навыки",
    "action.experience.title": "Получите практику в этой сфере",
    "action.experience.details": (
        "Поищите волонтёрство, стажировку или начальную должность по этой профессии."
    ),
    "action.experience.expected": "Реальный опыт, который можно добавить в резюме.",
    "action.education.title": "Проверьте, какой документ ждут работодатели",
    "action.education.details": (
        "Сравните несколько подходящих объявлений и узнайте, какие программы дают нужный документ."
    ),
    "action.education.expected": "Ясное понимание, какой документ нужен и где его получить.",
    "action.portfolio.title": "Добавьте проект, показывающий ваши навыки",
    "action.portfolio.details": (
        "Выполните небольшую работу по этой профессии и опишите её в резюме."
    ),
    "action.portfolio.expected": "Готовый пример, который можно показать работодателям.",
    "action.skill.title": "Развивайте навык: {skill}",
    "action.skill.details": (
        "Пройдите короткий курс по этой теме и примените знания на работе или в небольшом проекте."
    ),
    "action.skill.expected": "Этот навык и пример, который можно добавить в резюме.",
    "plan.rewrites": "Обновите резюме, используя предложенные формулировки там, где они верны для вас",
    "plan.measure": "Запустите новый анализ с обновлённым резюме, чтобы увидеть прогресс",
    "plan.with_effort": "{title} (примерно {duration})",
    "note.ranking": (
        "Пробелы упорядочены по влиянию на вашу оценку на основе официального перечня навыков для "
        "этой профессии. В используемых объявлениях навыки не указаны, поэтому мы не можем сказать, "
        "как часто работодатели просят каждый из них."
    ),
    "note.missing": (
        "Навык с пометкой «не найден» может просто отсутствовать в резюме. Если он у вас есть, "
        "добавьте его с реальным примером."
    ),
    "note.effort": (
        "Срок указан примерно, а рекомендации написаны ИИ. Перед оплатой проверьте, что курс или "
        "сертификат актуален и подходит вам."
    ),
    "note.strong": "У вас уже хорошее соответствие, поэтому считайте эти шаги необязательными.",
    "note.licence": (
        "Для этой работы может потребоваться лицензия или регистрация по месту жительства. Уточните "
        "у регулятора провинции или в профессиональной ассоциации."
    ),
    "note.low": (
        "Эта работа далека от вашего нынешнего опыта, поэтому другие должности ниже могут оказаться "
        "более быстрым путём."
    ),
    "alternative.shown": "Обязательных навыков всего: {total}. Вы показываете: {shown}, частично: {partly}.",
    "alternative.shown_including": (
        "Обязательных навыков всего: {total}. Вы показываете: {shown}, частично: {partly}. Например: {name}."
    ),
    "alternative.experience": "Ваш опыт соответствует тому, что обычно просят в объявлениях.",
    "alternative.add": "Что добавить в первую очередь: {name}.",
    "evidence.skill": "Навык: ",
    "evidence.job": "Должность: ",
    "evidence.project": "Проект: ",
    "evidence.degree": "Образование: ",
    "evidence.certification": "Сертификат: ",
    "evidence.related": " (связанный навык)",
    "push.report_ready_title": "Ваш отчёт CareerFit готов",
    "push.report_ready_body": "Нажмите, чтобы увидеть оценку и план.",
    "pdf.title": "Подробный отчёт CareerFit",
    "pdf.prepared": "Подготовлен {date} · Данные рынка на {as_of}",
    "pdf.score": "Оценка совпадения: {score} из 100",
    "pdf.confidence": "Надёжность оценки: {level}",
    "pdf.confidence.low": "низкая",
    "pdf.confidence.medium": "средняя",
    "pdf.confidence.high": "высокая",
    "pdf.breakdown": "Из чего складывается оценка",
    "pdf.points": "{points} из {max} баллов",
    "pdf.not_scored": "Не оценивалось: {items}",
    "pdf.salary": "Вероятная годовая зарплата для вашего профиля",
    "pdf.salary_range": "{low} – {high} {currency}. Середина рынка: {median} {currency}.",
    "pdf.salary_basis": "По {count} вакансиям, регион: {region}.",
    "pdf.skills": "Навыки, которые требуются для работы",
    "pdf.required": "Обязательные",
    "pdf.preferred": "Полезные",
    "pdf.level.yes": "есть",
    "pdf.level.partly": "частично",
    "pdf.level.no": "не найдено",
    "pdf.gaps": "Чего не хватает",
    "pdf.plan": "Ваш план на 30, 60 и 90 дней",
    "pdf.plan.thirty": "Первые 30 дней",
    "pdf.plan.sixty": "Дни 31–60",
    "pdf.plan.ninety": "Дни 61–90",
    "pdf.plan.later": "Позже",
    "pdf.actions": "Следующие шаги подробно",
    "pdf.action_meta": "Около {weeks} · приоритет: {priority}",
    "pdf.priority.high": "высокий",
    "pdf.priority.medium": "средний",
    "pdf.priority.low": "низкий",
    "pdf.where": "Где искать: {providers}",
    "pdf.unsure": "Это может зависеть от провинции или работодателя.",
    "pdf.rewrites": "Строки резюме, которые стоит переписать",
    "pdf.before": "Было",
    "pdf.after": "Стало",
    "pdf.alternatives": "Другие подходящие профессии",
    "pdf.alternative": "{name}: {score} из 100",
    "pdf.notes": "Примечания",
    "pdf.about": "Об этой оценке",
    "pdf.page": "Страница {page}",
}

_CATALOGUE: dict[str, dict[str, str]] = {"en": _EN, "ru": _RU}

_REGIONS_RU = {
    "Canada": "вся Канада",
    "Alberta": "Альберта",
    "British Columbia": "Британская Колумбия",
    "Manitoba": "Манитоба",
    "New Brunswick": "Нью-Брансуик",
    "Newfoundland and Labrador": "Ньюфаундленд и Лабрадор",
    "Northwest Territories": "Северо-Западные территории",
    "Nova Scotia": "Новая Шотландия",
    "Nunavut": "Нунавут",
    "Ontario": "Онтарио",
    "Prince Edward Island": "Остров Принца Эдуарда",
    "Québec": "Квебек",
    "Saskatchewan": "Саскачеван",
    "Yukon": "Юкон",
}


def say(language: str, key: str, **values: object) -> str:
    return _CATALOGUE[language][key].format(**values)


def catalogue_keys(language: str) -> set[str]:
    return set(_CATALOGUE[language])


def region_name(language: str, region: str) -> str:
    return _REGIONS_RU.get(region, region) if language == "ru" else region


def _russian_form(value: float, one: str, few: str, many: str) -> str:
    # Fractions always take the "few" form in Russian: 1,5 года.
    if value != int(value):
        return few
    number = int(value)
    if number % 10 == 1 and number % 100 != 11:
        return one
    if 2 <= number % 10 <= 4 and not 12 <= number % 100 <= 14:
        return few
    return many


def _russian_number(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def years(language: str, value: float) -> str:
    if language == "ru":
        return f"{_russian_number(value)} {_russian_form(value, 'год', 'года', 'лет')}"
    return f"{value:g} year" if value == 1 else f"{value:g} years"


def weeks(language: str, value: int) -> str:
    if language == "ru":
        return f"{value} {_russian_form(value, 'неделя', 'недели', 'недель')}"
    return f"{value} week" if value == 1 else f"{value} weeks"
