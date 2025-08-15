from io import BytesIO
from PIL import Image as PILImage, ImageChops
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
    Table, TableStyle, KeepTogether, Indenter
)
from reportlab.lib.styles import getSampleStyleSheet

from modules.pdf_utils import base_table_style, checkbox_box, checkbox_row
from modules.signature_utils import build_signature_block


def _bool(value) -> bool:
    """Convert a given value to a boolean based on common truthy indicators.

    Args:
        value: Any input that can be converted to string and evaluated.

    Returns:
        bool: True if the value represents a truthy indicator, else False.
    """
    string_value = (str(value or "")).strip().lower()
    return string_value in {
        "1", "true", "ja", "yes", "y", "on", "x", "✓", "checked"
    }


def _trim(img: PILImage.Image) -> PILImage.Image:
    """Trim white or transparent borders from an image.

    Args:
        img (PILImage.Image): The input image.

    Returns:
        PILImage.Image: Cropped image without extra borders.
    """
    if img.mode in ("LA", "RGBA"):
        bbox = img.split()[-1].getbbox()
        return img.crop(bbox) if bbox else img

    rgb_img = img.convert("RGB")
    diff = ImageChops.difference(
        rgb_img, PILImage.new("RGB", rgb_img.size, (255, 255, 255))
    )
    bbox = diff.getbbox()
    return img.crop(bbox) if bbox else img


def section_header(title_text: str, checked: bool):
    """Create a section header with a checkbox and title text.

    Args:
        title_text (str): The header text.
        checked (bool): Whether the checkbox is checked.

    Returns:
        Table: ReportLab Table containing the header.
    """
    table = Table(
        [[checkbox_box(checked, size=12), f"  {title_text}"],],
        colWidths=[12, 508]
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TEXTCOLOR", (1, 0), (1, 0), colors.black),
    ]))
    return table


def build_pdf(
    data: dict,
    i18n: dict,
    pdf_options: dict,
    signature_bytes: bytes | None = None
) -> bytes:
    """Build a PDF document for reporting involuntary homelessness.

    Args:
        data (dict): Data for filling in the PDF fields.
        i18n (dict): Internationalization dictionary for text.
        pdf_options (dict): Configuration for PDF layout and style.
        signature_bytes (bytes | None): Optional image bytes for signature.

    Returns:
        bytes: Generated PDF file content.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=pdf_options.get("leftMargin", 40),
        rightMargin=pdf_options.get("rightMargin", 40),
        topMargin=pdf_options.get("topMargin", 36),
        bottomMargin=pdf_options.get("bottomMargin", 36),
    )

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    title_style = styles["Title"]

    elements = []

    elements.append(Paragraph(
        f"<b>{i18n.get(pdf_options.get('title_i18n', 'app.title'), 'Anzeige von unfreiwilliger Obdachlosigkeit')}</b>",
        title_style
    ))
    elements.append(Spacer(1, 8))

    table_style = base_table_style()

    has_relatives = _bool(data.get("person_has_relatives"))
    relatives_line = (data.get("person_relatives_text") or "").strip()

    relatives_table = Table([
        [checkbox_row("keine Angehörige", not has_relatives, size=12, label_width=150)],
        [checkbox_row(f"Angehörige: {relatives_line}", has_relatives, size=12, label_width=150)],
    ], colWidths=[180], rowHeights=[42, 42])
    relatives_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))

    top_table = Table([
        [i18n.get("person.name", "Name, Vorname"),
         i18n.get("person.geb", "Geburtsdatum"),
         "Angehörige"],
        [data.get("person_name", ""),
         data.get("person_geb", ""),
         relatives_table]
    ], colWidths=[220, 120, 180])
    top_table.setStyle(table_style)
    elements += [top_table, Spacer(1, 14)]

    def box_line(label_text: str, height_pt=None):
        col_widths = [520]
        if height_pt:
            table = Table([[label_text]], colWidths=col_widths, rowHeights=[height_pt])
        else:
            table = Table([[label_text]], colWidths=col_widths)
        table.setStyle(table_style)
        return table

    elements += [
        section_header(i18n.get("section.erst", "Erstzuweisung"), _bool(data.get("erst_checked"))),
        Spacer(1, 4),
        Paragraph("Ich/ Meine Familie benötigt einen Platz im Wohnheim, um nicht auf der Straße schlafen zu müssen.", normal),
        Spacer(1, 4),
        Paragraph(i18n.get("erst.gruende", "Gründe …"), normal),
        box_line(data.get("erst_gruende", "")),
        Spacer(1, 10),
    ]

    elements += [
        section_header(i18n.get("section.unterb", "Zuweisung nach Unterbrechung"), _bool(data.get("unterb_checked"))),
        Spacer(1, 4),
        Paragraph(i18n.get("unterb.gruende", "Gründe …"), normal),
        box_line(data.get("unterb_gruende", "")),
        Spacer(1, 10),
    ]

    end_date = (data.get("verl_endet_am", "") or "").strip()
    elements += [
        section_header(i18n.get("section.verl", "Verlängerung der Zuweisung"), _bool(data.get("verl_checked"))),
        Spacer(1, 4),
        Paragraph(f"Die Zuweisung für das Wohnheim endet/e am: {end_date}", normal),
        Paragraph("Es ist mir nicht gelungen, eine Wohnung anzumieten oder woanders unterzukommen.", normal),
        Spacer(1, 10),
    ]

    elements += [
        section_header(i18n.get("section.wechsel", "Wechsel des Wohnheimes"), _bool(data.get("wechsel_checked"))),
        Spacer(1, 4),
        Paragraph(i18n.get("wechsel.gruende", "Ich/Wir benötige/n aus folgenden Gründen einen neuen Wohnheimplatz"), normal),
        box_line(data.get("wechsel_gruende", ""), height_pt=170.08),
    ]

    city = data.get("stadt", "")
    date_field = data.get("datum", "")
    elements.append(Paragraph(f"{i18n.get('field.ort', 'Ort')}: {city}    {i18n.get('field.datum', 'Datum')}: {date_field}", normal))
    elements.append(Spacer(1, 12))

    signature_block = build_signature_block(
        signature_bytes,
        pdf_options,
        label_text="Unterschrift des Vollmachtgebers"
    )
    elements += [Indenter(left=0), KeepTogether(signature_block), Indenter(left=0)]

    doc.build(elements)
    buffer.seek(0)
    return buffer.read()
