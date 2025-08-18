from __future__ import annotations
from io import BytesIO
from typing import Dict, Any

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from PIL import Image as PILImage, ImageChops

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

def _booly(x: Any) -> bool:
    s = str(x or "").strip().lower()
    return s in {"1", "true", "y", "yes", "ja", "on", "x", "✓", "checked"}

def _checkbox_interactive(c, name, tooltip, x, y, size=12, checked=False):
    c.acroForm.checkbox(
        name=name,
        tooltip=tooltip,
        x=x,
        y=y,
        size=size,
        borderStyle="solid",
        borderWidth=0,
        checked=bool(checked),
        buttonStyle="check",
    )

def _textfield_interactive(c, name, tooltip, x, y, w, h, *, multiline=False, value: str = ""):
    flags = FF_MULTILINE if multiline else 0
    c.acroForm.textfield(
        name=name,
        tooltip=tooltip,
        x=x, y=y, width=w, height=h,
        borderStyle="inset",
        borderWidth=0,
        forceBorder=False,
        fieldFlags=flags,
        value=value,
        fillColor=colors.white,        # الخلفية بيضاء
        textColor=colors.black,
    )

def _trim_pil(img: PILImage.Image) -> PILImage.Image:
    if img.mode in ("LA", "RGBA"):
        bbox = img.split()[-1].getbbox()
        return img.crop(bbox) if bbox else img
    rgb = img.convert("RGB")
    diff = ImageChops.difference(rgb, PILImage.new("RGB", rgb.size, (255, 255, 255)))
    bbox = diff.getbbox()
    return img.crop(bbox) if bbox else img

def _draw_signature_image(c, raw_bytes: bytes, x: float, y: float, w_box: float, h_box: float, *, trim=True, mode="fit"):
    pil = PILImage.open(BytesIO(raw_bytes)).convert("RGBA")
    if trim:
        pil = _trim_pil(pil)
    if mode.lower() == "stretch":
        dw, dh = w_box, h_box
    else:
        w_img, h_img = pil.size
        aspect = h_img / float(w_img or 1)
        dw = w_box
        dh = dw * aspect
        if dh > h_box:
            dh = h_box
            dw = dh / (aspect or 1)
    img = ImageReader(pil)
    c.drawImage(img, x, y, width=dw, height=dh, mask="auto")

def build_pdf_interactive_obdachlosigkeit(
    data: Dict[str, Any] | None,
    *,
    i18n: Dict[str, str],
    pdf_options: Dict[str, Any] | None = None,
    flatten: bool = False,
) -> bytes:
    data = data or {}
    pdf_options = pdf_options or {}
    left = _pt(pdf_options.get("leftMargin", 40))
    top = _pt(pdf_options.get("topMargin", 36))

    page_w, page_h = A4
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setAuthor("vollmacht_all")

    title_text = i18n.get("app.title", "Anzeige von unfreiwilliger Obdachlosigkeit")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left, page_h - top, title_text)
    y = page_h - top - 18

    c.setFont("Helvetica", 10)
    styles = getSampleStyleSheet()
    psty = styles["Normal"]; psty.fontName="Helvetica"; psty.fontSize=10; psty.leading=12

    grid = {"pad": 6}
    col1, col2, col3 = 220.0, 120.0, 180.0
    table_w = col1 + col2 + col3
    table_x = left
    table_y = y - 8

    hdr_h = 32
    c.rect(table_x, table_y - hdr_h, table_w, hdr_h, stroke=1, fill=0)
    c.line(table_x + col1, table_y, table_x + col1, table_y - hdr_h)
    c.line(table_x + col1 + col2, table_y, table_x + col1 + col2, table_y - hdr_h)

    _text(c, table_x + grid["pad"], table_y - 12, i18n.get("person.name", "Name, Vorname"))
    _text(c, table_x + col1 + grid["pad"], table_y - 12, i18n.get("person.geb", "Geburtsdatum"))
    _text(c, table_x + col1 + col2 + grid["pad"], table_y - 12, "Angehörige")

    data_h = 84
    row_y = table_y - hdr_h - data_h
    c.rect(table_x, row_y, table_w, data_h, stroke=1, fill=0)
    c.line(table_x + col1, table_y - hdr_h, table_x + col1, row_y)
    c.line(table_x + col1 + col2, table_y - hdr_h, table_x + col1 + col2, row_y)

    tf_pad, tf_h = 6, 16

    def TF(name, tooltip, x, y, w, h, *, multiline=False, value=""):
        if flatten:
            if multiline:
                para = Paragraph((value or "").replace("\n", "<br/>"), psty)
                para.wrapOn(c, w - 2, h - 2)
                para.drawOn(c, x + 1, y + 1)
            else:
                c.setFont("Helvetica", 10)
                c.drawString(x + 1, y + h - 12, value or "")
        else:
            _textfield_interactive(c, name, tooltip, x, y, w, h, multiline=multiline, value=value)

    def CB(name, tooltip, x, y, size, checked):
        if flatten:
            c.rect(x, y, size, size, stroke=1, fill=0)
            if checked:
                c.setFont("Helvetica", 12); c.drawString(x + 2, y + 1, "✓"); c.setFont("Helvetica", 10)
        else:
            _checkbox_interactive(c, name, tooltip, x, y, size=size, checked=checked)

    TF("person_name", i18n.get("person.name", "Name, Vorname"),
       table_x + tf_pad, row_y + data_h - tf_pad - tf_h, col1 - 2 * tf_pad, tf_h,
       value=str(data.get("person_name", "")))

    TF("person_geb", i18n.get("person.geb", "Geburtsdatum"),
       table_x + col1 + tf_pad, row_y + data_h - tf_pad - tf_h, col2 - 2 * tf_pad, tf_h,
       value=str(data.get("person_geb", "")))

    rel_x = table_x + col1 + col2 + tf_pad
    rel_y_top = row_y + data_h - tf_pad - tf_h
    CB("person_no_relatives", "keine Angehörige", rel_x, rel_y_top, 12, checked=not _booly(data.get("person_has_relatives")))
    _text(c, rel_x + 16, rel_y_top + 2, "keine Angehörige")

    rel2_y = rel_y_top - 24
    CB("person_has_relatives", i18n.get("person.has_relatives", "Angehörige"), rel_x, rel2_y, 12, checked=_booly(data.get("person_has_relatives")))
    _text(c, rel_x + 16, rel2_y + 2, i18n.get("person.has_relatives", "Angehörige"))
    TF("person_relatives_text", i18n.get("person.relatives_text", "Angehörige:"),
       rel_x, rel2_y - 20, col3 - 2 * tf_pad, tf_h,
       value=str(data.get("person_relatives_text", "")))

    y = row_y - 16

    def section_header(title_text: str, checkbox_name: str, y_pos: float, checked: bool) -> float:
        box_size = 12
        CB(checkbox_name, title_text, left, y_pos - box_size, box_size, checked)
        _text(c, left + box_size + 6, y_pos - 10, title_text, size=11, bold=True)
        return y_pos - 18

    def paragraph_area(label: str, name: str, y_pos: float, height: float, value: str) -> float:
        _text(c, left, y_pos - 12, label)
        bx_y = y_pos - 12 - height
        c.rect(left, bx_y, col1 + col2 + col3, height, stroke=1, fill=0)
        TF(name, label, left + 4, bx_y + 4, col1 + col2 + col3 - 8, height - 8, multiline=True, value=value)
        return bx_y - 14

    y = section_header(i18n.get("section.erst", "Erstzuweisung"), "erst_checked", y, checked=_booly(data.get("erst_checked")))
    y = paragraph_area(i18n.get("erst.gruende", "Gründe …"), "erst_gruende", y, height=70, value=str(data.get("erst_gruende", "")))

    y = section_header(i18n.get("section.unterb", "Zuweisung nach Unterbrechung"), "unterb_checked", y, checked=_booly(data.get("unterb_checked")))
    y = paragraph_area(i18n.get("unterb.gruende", "Gründe …"), "unterb_gruende", y, height=70, value=str(data.get("unterb_gruende", "")))

    y = section_header(i18n.get("section.verl", "Verlängerung der Zuweisung"), "verl_checked", y, checked=_booly(data.get("verl_checked")))
    _text(c, left, y - 12, f"{i18n.get('verl.endet_am', 'Endet am')}:")
    TF("verl_endet_am", i18n.get("verl.endet_am", "Endet am"), left + 320, y - 16, 150, 16, value=str(data.get("verl_endet_am", "")))
    y -= 28
    _text(c, left, y - 12, "Es ist mir nicht gelungen, eine Wohnung anzumieten oder woanders unterzukommen.")
    y -= 22

    y = section_header(i18n.get("section.wechsel", "Wechsel des Wohnheimes"), "wechsel_checked", y, checked=_booly(data.get("wechsel_checked")))
    y = paragraph_area(i18n.get("wechsel.gruende", "Ich/Wir benötige/n …"), "wechsel_gruende", y, height=170, value=str(data.get("wechsel_gruende", "")))

    _text(c, left, y - 12, i18n.get("field.ort", "Ort") + ":")
    TF("stadt", i18n.get("field.ort", "Ort"), left + 50, y - 16, 150, 16, value=str(data.get("stadt", "")))

    _text(c, left + 220, y - 12, i18n.get("field.datum", "Datum") + ":")
    TF("datum", i18n.get("field.datum", "Datum"), left + 270, y - 16, 120, 16, value=str(data.get("datum", "")))
    y -= 36

    _text(c, left, y - 12, i18n.get("signature.title", "Unterschrift") + ":")
    sig_x, sig_y, sig_w, sig_h = left + 70, y - 36, 180, 28
    raw_sig = data.get("signature_bytes")

    if raw_sig:
        try:
            _draw_signature_image(c, raw_sig, sig_x, sig_y, sig_w, sig_h, trim=True, mode="fit")
        except Exception:
            c.rect(sig_x, sig_y, sig_w, sig_h, stroke=1, fill=0)
    else:
        c.rect(sig_x, sig_y, sig_w, sig_h, stroke=1, fill=0)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()
