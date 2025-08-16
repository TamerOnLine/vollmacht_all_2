# forms/obdachlosigkeit/interactive_builder.py
from __future__ import annotations
from io import BytesIO
from typing import Dict, Any

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# AcroForm flags
FF_MULTILINE = 1 << 12  # 4096


def _pt(v: float) -> float:
    return float(v)


def _draw_box(c, x, y, w, h, *, fill=None, stroke=1, dash=None):
    if dash:
        c.setDash(dash, 0)
    else:
        c.setDash()
    if fill is not None:
        c.setFillColor(fill)
        c.rect(x, y, w, h, stroke=stroke, fill=1)
        c.setFillColor(colors.black)
    else:
        c.rect(x, y, w, h, stroke=stroke, fill=0)


def _text(c, x, y, txt, size=10, bold=False):
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawString(x, y, txt)


def _checkbox(c, name, tooltip, x, y, size=12, checked=False):
    c.acroForm.checkbox(
        name=name,
        tooltip=tooltip,
        x=x, y=y,
        size=size,
        borderStyle="solid",
        borderWidth=1,
        checked=bool(checked),
        buttonStyle="check",
    )


def _textfield(c, name, tooltip, x, y, w, h, *, multiline=False):
    flags = FF_MULTILINE if multiline else 0
    c.acroForm.textfield(
        name=name,
        tooltip=tooltip,
        x=x, y=y,
        width=w, height=h,
        borderStyle="inset",
        borderWidth=1,
        forceBorder=True,
        fieldFlags=flags,
    )


def build_pdf_interactive_obdachlosigkeit(
    data: Dict[str, Any] | None,
    *,
    i18n: Dict[str, str],
    pdf_options: Dict[str, Any] | None = None,
) -> bytes:
    """
    Generate an interactive (fillable) PDF for 'obdachlosigkeit' with a layout
    closely matching the visual builder.py version, but using AcroForm fields.

    Args:
        data: (unused for initial rendering; fields come empty)
        i18n: i18n dict (German expected for PDF text)
        pdf_options: margins etc. Uses keys: leftMargin/rightMargin/topMargin/bottomMargin.

    Returns:
        bytes of the generated PDF.
    """
    pdf_options = pdf_options or {}
    left = _pt(pdf_options.get("leftMargin", 40))
    right = _pt(pdf_options.get("rightMargin", 40))
    top = _pt(pdf_options.get("topMargin", 36))
    bottom = _pt(pdf_options.get("bottomMargin", 36))

    page_w, page_h = A4
    content_w = page_w - left - right

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setAuthor("vollmacht_all")

    # Title
    title_text = i18n.get("app.title", "Anzeige von unfreiwilliger Obdachlosigkeit")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left, page_h - top, title_text)
    y = page_h - top - 18

    # Shared fonts
    c.setFont("Helvetica", 10)

    # Table style constants similar to builder.py
    grid = {
        "box": 1,
        "inner": 0.5,
        "pad": 6,
        "row_h": 42,
        "row_h_small": 32,
        "label_h": 14
    }

    # Column widths like builder: [220, 120, 180] => sum 520. Content width ≈ 515–520 (margins ~40).
    col1 = 220.0
    col2 = 120.0
    col3 = 180.0
    table_w = col1 + col2 + col3
    table_x = left  # align left margin
    table_y = y - 8

    # ---- Top table: headers row ----
    # Header row height
    hdr_h = grid["row_h_small"]
    _draw_box(c, table_x, table_y - hdr_h, table_w, hdr_h, fill=None, stroke=1)

    # vertical lines (columns)
    c.line(table_x + col1, table_y, table_x + col1, table_y - hdr_h)
    c.line(table_x + col1 + col2, table_y, table_x + col1 + col2, table_y - hdr_h)

    # header labels
    _text(c, table_x + grid["pad"], table_y - 12, i18n.get("person.name", "Name, Vorname"))
    _text(c, table_x + col1 + grid["pad"], table_y - 12, i18n.get("person.geb", "Geburtsdatum"))
    _text(c, table_x + col1 + col2 + grid["pad"], table_y - 12, "Angehörige")

    # ---- Top table: data row ----
    data_h = 84  # give more height for relatives column (to fit two options)
    row_y = table_y - hdr_h - data_h
    _draw_box(c, table_x, row_y, table_w, data_h, fill=None, stroke=1)
    c.line(table_x + col1, table_y - hdr_h, table_x + col1, row_y)
    c.line(table_x + col1 + col2, table_y - hdr_h, table_x + col1 + col2, row_y)

    # Field: person_name (cell 1)
    tf_pad = 6
    tf_h = 16
    _textfield(
        c,
        name="person_name",
        tooltip=i18n.get("person.name", "Name, Vorname"),
        x=table_x + tf_pad,
        y=row_y + data_h - tf_pad - tf_h,
        w=col1 - 2 * tf_pad,
        h=tf_h,
    )

    # Field: person_geb (cell 2)
    _textfield(
        c,
        name="person_geb",
        tooltip=i18n.get("person.geb", "Geburtsdatum"),
        x=table_x + col1 + tf_pad,
        y=row_y + data_h - tf_pad - tf_h,
        w=col2 - 2 * tf_pad,
        h=tf_h,
    )

    # Relatives (cell 3) – two stacked checkbox rows + optional text
    rel_x = table_x + col1 + col2 + tf_pad
    rel_y_top = row_y + data_h - tf_pad - tf_h
    # Option 1: keine Angehörige
    _checkbox(
        c,
        name="person_no_relatives",
        tooltip="keine Angehörige",
        x=rel_x,
        y=rel_y_top,
        size=12,
        checked=False,
    )
    _text(c, rel_x + 16, rel_y_top + 2, "keine Angehörige")

    # Option 2: Angehörige (مع نص)
    rel2_y = rel_y_top - 24
    _checkbox(
        c,
        name="person_has_relatives",
        tooltip=i18n.get("person.has_relatives", "Angehörige (ankreuzen, falls vorhanden)"),
        x=rel_x,
        y=rel2_y,
        size=12,
        checked=False,
    )
    _text(c, rel_x + 16, rel2_y + 2, i18n.get("person.has_relatives", "Angehörige"))

    # relatives text
    _textfield(
        c,
        name="person_relatives_text",
        tooltip=i18n.get("person.relatives_text", "Angehörige: (optional ausführen)"),
        x=rel_x,
        y=rel2_y - 20,
        w=col3 - 2 * tf_pad,
        h=tf_h,
    )

    y = row_y - 16  # move down after the top table

    # Helper: section header with checkbox box at left of title line
    def section_header(title_text: str, checkbox_name: str, y_pos: float) -> float:
        # box + title (similar to builder.section_header)
        box_size = 12
        _draw_box(c, left, y_pos - box_size, box_size, box_size, fill=None, stroke=1)
        _checkbox(c, checkbox_name, tooltip=title_text, x=left, y=y_pos - box_size, size=box_size)
        _text(c, left + box_size + 6, y_pos - 10, title_text, size=11, bold=True)
        return y_pos - 18

    # Helper: labeled paragraph area (simple line + area)
    def paragraph_area(label: str, name: str, y_pos: float, height: float) -> float:
        _text(c, left, y_pos - 12, label)
        # box area
        bx_y = y_pos - 12 - height
        _draw_box(c, left, bx_y, table_w, height, fill=None, stroke=1)
        # textfield multiline
        _textfield(c, name, tooltip=label, x=left + 4, y=bx_y + 4, w=table_w - 8, h=height - 8, multiline=True)
        return bx_y - 14

    # ---- Section: Erstzuweisung ----
    y = section_header(i18n.get("section.erst", "Erstzuweisung"), "erst_checked", y)
    y = paragraph_area(i18n.get("erst.gruende", "Gründe …"), "erst_gruende", y, height=70)

    # ---- Section: Zuweisung nach Unterbrechung ----
    y = section_header(i18n.get("section.unterb", "Zuweisung nach Unterbrechung"), "unterb_checked", y)
    y = paragraph_area(i18n.get("unterb.gruende", "Gründe …"), "unterb_gruende", y, height=70)

    # ---- Section: Verlängerung der Zuweisung ----
    y = section_header(i18n.get("section.verl", "Verlängerung der Zuweisung"), "verl_checked", y)
    _text(c, left, y - 12, f"{i18n.get('verl.endet_am', 'Die Zuweisung für das Wohnheim endet/e am')}:")
    _textfield(
        c,
        name="verl_endet_am",
        tooltip=i18n.get("verl.endet_am", "Endet am"),
        x=left + 320,
        y=y - 16,
        w=150,
        h=16,
    )
    y -= 28
    _text(c, left, y - 12, "Es ist mir nicht gelungen, eine Wohnung anzumieten oder woanders unterzukommen.")
    y -= 22

    # ---- Section: Wechsel des Wohnheimes ----
    y = section_header(i18n.get("section.wechsel", "Wechsel des Wohnheimes"), "wechsel_checked", y)
    y = paragraph_area(
        i18n.get("wechsel.gruende", "Ich/Wir benötige/n aus folgenden Gründen einen neuen Wohnheimplatz"),
        "wechsel_gruende",
        y,
        height=170,
    )

    # ---- Footer: Ort / Datum ----
    # On one line
    _text(c, left, y - 12, i18n.get("field.ort", "Ort") + ":")
    _textfield(c, "stadt", tooltip=i18n.get("field.ort", "Ort"), x=left + 50, y=y - 16, w=150, h=16)

    _text(c, left + 220, y - 12, i18n.get("field.datum", "Datum") + ":")
    _textfield(c, "datum", tooltip=i18n.get("field.datum", "Datum"), x=left + 270, y=y - 16, w=120, h=16)
    y -= 36

    # ---- Signature block ----
    _text(c, left, y - 12, i18n.get("signature.title", "Unterschrift") + ":")
    _draw_box(c, left + 70, y - 36, 180, 28, fill=None, stroke=1)  # guide box
    y -= 50

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()
