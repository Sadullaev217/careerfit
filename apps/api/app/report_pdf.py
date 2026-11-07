"""The detailed report: one finished result laid out as a printable PDF.

Everything in it is already in the saved result, so making it costs no AI time. Headings come from the
message catalogue; the report's own text is in the language the analysis was run in.
"""

from datetime import date, datetime
from pathlib import Path
from typing import Literal

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.messages import region_name, say, weeks
from app.recommendations import FullResult

FONT_DIR = Path(__file__).parent / "fonts"
FONT = "DejaVu"
INK = (26, 34, 46)
MUTED = (96, 104, 116)
ACCENT = (0, 88, 76)

Language = Literal["en", "ru"]


def _money(value: int, language: Language) -> str:
    grouped = f"{value:,}"
    return grouped.replace(",", " ") if language == "ru" else grouped


def _day(value: str) -> str:
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return value[:10]


class _Document(FPDF):
    def __init__(self, language: Language) -> None:
        super().__init__(format="Letter")
        self.language = language
        self.add_font(FONT, "", str(FONT_DIR / "DejaVuSans.ttf"))
        self.add_font(FONT, "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(18, 18, 18)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font(FONT, "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, f"CareerFit · {say(self.language, 'pdf.page', page=self.page_no())}", align="C")

    def heading(self, text: str) -> None:
        self.ln(4)
        self.set_font(FONT, "B", 13)
        self.set_text_color(*ACCENT)
        self.multi_cell(0, 7, text, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def para(self, text: str, size: float = 10, bold: bool = False, muted: bool = False) -> None:
        self.set_font(FONT, "B" if bold else "", size)
        self.set_text_color(*(MUTED if muted else INK))
        self.multi_cell(0, size * 0.55, text, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def bullets(self, items: list[str]) -> None:
        for item in items:
            self.para(f"• {item}")
            self.ln(0.5)


def build_report_pdf(
    result: FullResult, role: str, region: str | None, created_at: str, language: Language
) -> bytes:
    pdf = _Document(language)
    pdf.add_page()

    def t(key: str, **values: object) -> str:
        return say(language, key, **values)

    pdf.para(t("pdf.title"), size=18, bold=True)
    place = region_name(language, region or result.region)
    pdf.para(f"{role} · {place}", size=12)
    pdf.para(t("pdf.prepared", date=_day(created_at), as_of=result.as_of), size=9, muted=True)
    pdf.ln(3)
    pdf.para(t("pdf.score", score=result.score), size=15, bold=True)
    level = t(f"pdf.confidence.{result.confidence.level}")
    pdf.para(t("pdf.confidence", level=level), muted=True)
    if result.confidence.reasons:
        pdf.bullets(result.confidence.reasons)

    pdf.heading(t("pdf.breakdown"))
    for category in result.categories:
        pdf.para(
            f"{category.label}: {t('pdf.points', points=category.points, max=category.max_points)}",
            bold=True,
        )
        pdf.para(category.reason)
        pdf.ln(1)
    if result.not_scored:
        pdf.para(t("pdf.not_scored", items=", ".join(result.not_scored)), muted=True)

    if result.salary:
        salary = result.salary
        pdf.heading(t("pdf.salary"))
        pdf.para(
            t(
                "pdf.salary_range",
                low=_money(salary.low, language),
                high=_money(salary.high, language),
                median=_money(salary.market_median, language),
                currency=salary.currency,
            )
        )
        pdf.para(
            t("pdf.salary_basis", count=salary.sample_size, region=region_name(language, salary.region)),
            muted=True,
        )

    pdf.heading(t("pdf.skills"))
    for label, skills in ((t("pdf.required"), result.required_skills), (t("pdf.preferred"), result.preferred_skills)):
        if skills:
            pdf.para(label, bold=True)
            pdf.bullets([f"{skill.name}: {t(f'pdf.level.{skill.level}')}" for skill in skills])

    report = result.report
    if report:
        if report.gaps:
            pdf.heading(t("pdf.gaps"))
            pdf.bullets([f"{gap.title}: {gap.detail}" for gap in report.gaps])

        pdf.heading(t("pdf.plan"))
        for key, items in (
            ("pdf.plan.thirty", report.plan.thirty_days),
            ("pdf.plan.sixty", report.plan.sixty_days),
            ("pdf.plan.ninety", report.plan.ninety_days),
            ("pdf.plan.later", report.plan.later),
        ):
            if items:
                pdf.para(t(key), bold=True)
                pdf.bullets(items)

        if report.actions:
            pdf.heading(t("pdf.actions"))
            for action in report.actions:
                pdf.para(action.title, bold=True)
                pdf.para(
                    t(
                        "pdf.action_meta",
                        weeks=weeks(language, action.effort_weeks),
                        priority=t(f"pdf.priority.{action.priority}"),
                    ),
                    size=9,
                    muted=True,
                )
                pdf.para(action.details)
                if action.expected_result:
                    pdf.para(action.expected_result, muted=True)
                if action.providers:
                    pdf.para(t("pdf.where", providers=", ".join(action.providers)), size=9, muted=True)
                if action.uncertain:
                    pdf.para(t("pdf.unsure"), size=9, muted=True)
                pdf.ln(2)

        if report.rewrites:
            pdf.heading(t("pdf.rewrites"))
            for rewrite in report.rewrites:
                pdf.para(f"{t('pdf.before')}: {rewrite.before}", muted=True)
                pdf.para(f"{t('pdf.after')}: {rewrite.after}")
                pdf.ln(2)

        if report.alternative_roles:
            pdf.heading(t("pdf.alternatives"))
            for role_option in report.alternative_roles:
                pdf.para(
                    t("pdf.alternative", name=role_option.occupation_name, score=role_option.score),
                    bold=True,
                )
                pdf.para(role_option.reason)
                pdf.ln(1)

        if report.notes:
            pdf.heading(t("pdf.notes"))
            pdf.bullets(report.notes)

    pdf.heading(t("pdf.about"))
    pdf.para(result.disclaimer, size=9, muted=True)
    return bytes(pdf.output())


def report_file_name(created_at: str) -> str:
    try:
        day = datetime.fromisoformat(created_at).date()
    except ValueError:
        day = date.today()
    return f"careerfit-report-{day.isoformat()}.pdf"
