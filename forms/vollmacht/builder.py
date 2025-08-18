from io import BytesIO
from PIL import Image as PILImage, ImageChops
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
    Table, Indenter, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet
from modules.pdf_utils import base_table_style
from modules.signature_utils import build_signature_block


def _trim_whitespace(img: PILImage.Image) -> PILImage.Image:
    """Trim whitespace or transparent borders from an image.

    Args:
        img (PILImage.Image): The input PIL Image.

    Returns:
        PILImage.Image: The cropped image without extra whitespace or transparent space.
    """
    if img.mode in ("LA", "RGBA"):
        alpha = img.split()[-1]
        bbox = alpha.getbbox()
        return img.crop(bbox) if bbox else img

    rgb = img.convert("RGB")
    bg = PILImage.new("RGB", rgb.size, (255, 255, 255))
    diff = ImageChops.difference(rgb, bg)
    bbox = diff.getbbox()
    return img.crop(bbox) if bbox else img


def build_pdf(
        data: dict,
        i18n: dict,
        pdf_options: dict,
        signature_bytes: bytes | None = None
) -> bytes:
    """Generate a PDF document containing authorization details.

    Args:
        data (dict): Dictionary containing form field values such as names, addresses, and dates.
        i18n (dict): Dictionary for internationalization, providing localized strings.
        pdf_options (dict): Options for PDF layout, margins, and signature display settings.
        signature_bytes (bytes | None, optional): Image data for the signature. Defaults to None.

    Returns:
        bytes: The generated PDF file as a byte stream.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=pdf_options.get("leftMargin", 40),
        rightMargin=pdf_options.get("rightMargin", 40),
        topMargin=pdf_options.get("topMargin", 36),
        bottomMargin=pdf_options.get("bottomMargin", 36),
    )

    styles = getSampleStyleSheet()
    elems = [
        Paragraph(
            f"<b>{i18n.get(pdf_options.get('title_i18n', 'app.title'), 'Vollmacht')}</b>",
            styles["Title"]
        ),
        Paragraph(
            "zur Abholung und Beantragung des Aufenthaltstitels/Reiseausweises",
            styles["Normal"]
        ),
        Spacer(1, 12),
        Paragraph("Ich:", styles["Normal"]),
        Paragraph("Vollmachtgeber", styles["Normal"]),
    ]

    table_style = base_table_style()

    tbl1 = Table(
        [
            ["Name:", data.get("vg_name", "")],
            ["Vorname:", data.get("vg_vorname", "")],
            ["Geburtsdatum:", data.get("vg_geb", "")],
            ["Anschrift:", data.get("vg_addr", "")],
        ],
        colWidths=[100, 350]
    )
    tbl1.setStyle(table_style)

    tbl2 = Table(
        [
            ["Name:", data.get("b_name", "")],
            ["Vorname:", data.get("b_vorname", "")],
            ["Geburtsdatum:", data.get("b_geb", "")],
            ["Anschrift:", data.get("b_addr", "")],
        ],
        colWidths=[100, 350]
    )
    tbl2.setStyle(table_style)

    elems += [
        tbl1,
        Spacer(1, 12),
        Paragraph("bevollmächtige", styles["Normal"]),
        Paragraph("Bevollmächtigter/-r", styles["Normal"]),
        tbl2,
        Spacer(1, 12),
        Paragraph(
            "den Aufenthaltstitel und Reiseausweis zu beantragen/abzuholen, "
            "unter Vorlage <u>meines</u> Personaldokuments.",
            styles["Normal"]
        ),
        Paragraph(
            "<b>Hinweis:</b> Der Bevollmächtigte muss sich bei Vorsprache "
            "zur Abholung durch Vorlage eines eigenen Personaldokuments ausweisen.",
            styles["Normal"]
        ),
        Spacer(1, 24),
        Paragraph(
            f"{data.get('stadt', '')}, den {data.get('datum', '')}",
            styles["Normal"]
        ),
        Spacer(1, 18),
    ]



    sig_block = build_signature_block(
        signature_bytes,
        pdf_options,
        label_text="Unterschrift des Vollmachtgebers"
    )
    elems += [Indenter(left=0), KeepTogether(sig_block), Indenter(left=0)]

    doc.build(elems)
    buf.seek(0)
    return buf.read()
