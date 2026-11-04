import io
import zipfile

import docx
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont


def text_pdf(text: str = "Senior accountant with ten years of experience", pages: int = 1) -> bytes:
    pdf = FPDF()
    pdf.set_font("Helvetica", size=12)
    for _ in range(pages):
        pdf.add_page()
        pdf.multi_cell(0, 10, text)
    return bytes(pdf.output())


def encrypted_pdf() -> bytes:
    pdf = FPDF()
    pdf.set_encryption(owner_password="owner", user_password="user")
    pdf.set_font("Helvetica", size=12)
    pdf.add_page()
    pdf.multi_cell(0, 10, "Secret resume")
    return bytes(pdf.output())


def _page_image(text: str | None) -> Image.Image:
    image = Image.new("RGB", (1654, 2339), "white")
    if text:
        ImageDraw.Draw(image).text(
            (150, 200), text, fill="black", font=ImageFont.load_default(size=72)
        )
    return image


def scanned_pdf(text: str | None = "Senior Accountant", pages: int = 1) -> bytes:
    images = [_page_image(text) for _ in range(pages)]
    buffer = io.BytesIO()
    images[0].save(
        buffer, format="PDF", resolution=200, save_all=True, append_images=images[1:]
    )
    return buffer.getvalue()


def sample_docx() -> bytes:
    document = docx.Document()
    document.sections[0].header.paragraphs[0].text = "Jordan Lee contact details"
    document.add_paragraph("Registered nurse with patient care experience")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Skills"
    table.rows[0].cells[1].text = "Triage and charting"
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def zip_with(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def docx_with(extra: dict[str, bytes]) -> bytes:
    return zip_with(
        {"[Content_Types].xml": b"<Types/>", "word/document.xml": b"<document/>", **extra}
    )
