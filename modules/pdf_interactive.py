# modules/pdf_interactive.py
"""
Interactive PDF (AcroForm) generator with two modes:

1) Layout JSON mode (preferred):
   - Read forms/<form_key>/layout.json
   - Optional backgrounds (per page)
   - Place fields by exact coordinates (x, y, w, h) in points.
   - Supported types: text, textarea, checkbox, rect, line, label
   - Multipage via "page" (1-based)

   Example layout.json:
   {
     "pagesize": "A4",
     "draw_boxes": true,
     "backgrounds": ["forms/obdachlosigkeit/background_page1.png"],
     "fields": [
       {"name":"person_name","label_i18n":"person.name","type":"text","page":1,"x":330,"y":750,"w":200,"h":16},
       {"name":"erst_gruende","label_i18n":"erst.gruende","type":"textarea","page":1,"x":330,"y":560,"w":200,"h":70},
       {"name":"erst_checked","label_i18n":"option.checked","type":"checkbox","page":1,"x":520,"y":645,"w":12,"h":12},
       {"type":"rect","page":1,"x":330,"y":135,"w":150,"h":30},
       {"type":"label","text_i18n":"signature.title","page":1,"x":300,"y":172,"size":10},
       {"type":"line","page":1,"x1":330,"y1":170,"x2":480,"y2":170,"width":0.8}
     ]
   }

2) Auto layout fallback:
   - Clean single-column layout derived from schema sections/fields.

Coordinate system: ReportLab default (origin at bottom-left). A4 ≈ (595 x 842) pt.
"""

from __future__ import annotations
import json
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors

# ------------- AcroForm flags -------------
FF_MULTILINE = 1 << 12  # 4096

# ------------- Helpers -------------

_FIELD_TYPE_TEXT = {"text", "input", "string"}
_FIELD_TYPE_TEXTAREA = {"textarea", "multiline"}
_FIELD_TYPE_CHECKBOX = {"checkbox", "bool", "boolean"}

def _read_layout(form_key: str | None) -> dict | None:
    if not form_key:
        return None
    p = Path(f"forms/{form_key}/layout.json")
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None

def _label_from_i18n(i18n: dict, item: dict, fallback_key: str = "name") -> str:
    return i18n.get(item.get("label_i18n", ""), item.get(fallback_key, ""))

def _text_from_i18n(i18n: dict, item: dict, key: str = "text", i18n_key: str = "text_i18n") -> str:
    if item.get(i18n_key):
        return i18n.get(item[i18n_key], item.get(key, ""))
    return item.get(key, "")

# ------------- Public API -------------

def build_interactive_pdf(
    schema: dict,
    i18n: dict,
    *,
    pdf_options: dict | None = None,
    file_title: str | None = None,
    form_key: str | None = None,
) -> bytes:
    pdf_options = pdf_options or {}
    page_w, page_h = A4

    mem = BytesIO()
    c = canvas.Canvas(mem, pagesize=A4)
    c.setAuthor("vollmacht_all")
    if file_title:
        c.setTitle(file_title)

    layout = _read_layout(form_key or schema.get("__form_key__", None))
    if layout:
        _render_by_layout_json(c, layout, i18n, page_w, page_h)
        c.save()
        mem.seek(0)
        return mem.read()

    _render_auto_layout(c, schema, i18n, pdf_options, page_w, page_h)
    c.save()
    mem.seek(0)
    return mem.read()

# ------------- Renderers -------------

def _render_by_layout_json(
    c: canvas.Canvas,
    layout: dict,
    i18n: dict,
    page_w: float,
    page_h: float,
) -> None:
    """Render using explicit coordinates with optional backgrounds."""
    draw_boxes = bool(layout.get("draw_boxes", True))
    fields: list[dict[str, Any]] = list(layout.get("fields", []) or [])
    backgrounds: list[str] = list(layout.get("backgrounds", []) or [])

    def _draw_background(page_index: int):
        if 0 <= page_index < len(backgrounds):
            bg_path = backgrounds[page_index]
            try:
                c.drawImage(bg_path, 0, 0, width=page_w, height=page_h, preserveAspectRatio=False, mask='auto')
            except Exception:
                # ignore missing/invalid background silently
                pass

    c.setFont("Helvetica", 10)
    current_page = 1
    _draw_background(0)  # first page background if present

    for f in fields:
        page = int(f.get("page", 1))
        # Advance to requested page
        while page > current_page:
            c.showPage()
            c.setFont("Helvetica", 10)
            current_page += 1
            _draw_background(current_page - 1)

        kind = (f.get("type") or "text").lower()

        # Decorative/guide primitives
        if kind == "rect":
            x, y, w, h = float(f["x"]), float(f["y"]), float(f["w"]), float(f["h"])
            c.setFillColorRGB(1, 1, 1)
            c.rect(x, y, w, h, stroke=1, fill=0)
            c.setFillColor(colors.black)
            continue

        if kind == "line":
            x1, y1 = float(f.get("x1", 0)), float(f.get("y1", 0))
            x2, y2 = float(f.get("x2", 0)), float(f.get("y2", 0))
            width = float(f.get("width", 0.8))
            c.setLineWidth(width)
            c.line(x1, y1, x2, y2)
            continue

        if kind == "label":
            txt = _text_from_i18n(i18n, f, key="text", i18n_key="text_i18n")
            size = int(f.get("size", 10))
            c.setFont("Helvetica-Bold" if f.get("bold") else "Helvetica", size)
            c.drawString(float(f.get("x", 0)), float(f.get("y", 0)), txt)
            c.setFont("Helvetica", 10)
            continue

        # Form fields
        x, y, w, h = float(f["x"]), float(f["y"]), float(f["w"]), float(f["h"])
        label = _label_from_i18n(i18n, f)

        if kind == "checkbox":
            if draw_boxes:
                _fill_box(c, x, y, h, h)
            c.acroForm.checkbox(
                name=f.get("name"),
                tooltip=label,
                x=x,
                y=y,
                size=min(w, h),
                borderStyle="solid",
                borderWidth=1,
                checked=bool(f.get("checked", False)),
                buttonStyle=f.get("buttonStyle", "check"),
            )
            continue

        # text / textarea
        if draw_boxes:
            _fill_box(c, x, y, w, h)
        flags = FF_MULTILINE if kind == "textarea" else 0
        c.acroForm.textfield(
            name=f.get("name"),
            tooltip=label,
            x=x,
            y=y,
            width=w,
            height=h,
            borderStyle=f.get("borderStyle", "inset"),
            borderWidth=float(f.get("borderWidth", 1)),
            forceBorder=bool(f.get("forceBorder", True)),
            fieldFlags=flags,
        )

def _render_auto_layout(
    c: canvas.Canvas,
    schema: dict,
    i18n: dict,
    pdf_options: dict,
    page_w: float,
    page_h: float,
) -> None:
    """Fallback: single-column auto layout."""
    left = float(pdf_options.get("leftMargin", 40))
    right = float(pdf_options.get("rightMargin", 40))
    top = float(pdf_options.get("topMargin", 36))
    bottom = float(pdf_options.get("bottomMargin", 36))

    title_key = pdf_options.get("title_i18n", "app.title")
    doc_title = i18n.get(title_key, "Interactive Form")

    x_label = left
    x_field = left + 5.8 * cm
    field_w = page_w - right - x_field
    line_h = 18
    y = page_h - top

    c.setFont("Helvetica-Bold", 14)
    c.drawString(x_label, y, doc_title)
    y -= 1.0 * cm
    c.setFont("Helvetica", 10)

    def new_page():
        nonlocal y
        c.showPage()
        c.setFont("Helvetica", 10)
        y = page_h - top

    def draw_text(label: str, name: str):
        nonlocal y
        if y - line_h < bottom:
            new_page()
        c.drawString(x_label, y - 12, f"{label}:")
        _fill_box(c, x_field, y - 16, field_w, 16)
        c.acroForm.textfield(
            name=name,
            tooltip=label,
            x=x_field,
            y=y - 16,
            width=field_w,
            height=16,
            borderStyle="inset",
            borderWidth=1,
            forceBorder=True,
        )
        y -= line_h

    def draw_textarea(label: str, name: str, rows: int = 5):
        nonlocal y
        h = max(16 * rows + 4, 36)
        if y - h < bottom:
            new_page()
        c.drawString(x_label, y - 12, f"{label}:")
        _fill_box(c, x_field, y - h + 4, field_w, h - 8)
        c.acroForm.textfield(
            name=name,
            tooltip=label,
            x=x_field,
            y=y - h + 4,
            width=field_w,
            height=h - 8,
            borderStyle="inset",
            borderWidth=1,
            forceBorder=True,
            fieldFlags=FF_MULTILINE,
        )
        y -= h + 4

    def draw_checkbox(label: str, name: str):
        nonlocal y
        if y - line_h < bottom:
            new_page()
        box_size = 12
        _fill_box(c, x_field, y - 14, box_size, box_size)
        c.acroForm.checkbox(
            name=name,
            tooltip=label,
            x=x_field,
            y=y - 14,
            size=box_size,
            borderStyle="solid",
            borderWidth=1,
            checked=False,
            buttonStyle="check",
        )
        c.drawString(x_field + box_size + 6, y - 12, label)
        y -= line_h

    def draw_section(title: str):
        nonlocal y
        if y - 20 < bottom:
            new_page()
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(colors.black)
        c.drawString(x_label, y - 12, title)
        c.setFont("Helvetica", 10)
        y -= 8

    for section in schema.get("sections", []):
        title = i18n.get(section.get("title_i18n", section.get("key", "")), section.get("key", ""))
        draw_section(title)
        for fld in section.get("fields", []):
            key = fld.get("key", "")
            name = f"{section['key']}_{key}"
            label = i18n.get(fld.get("label_i18n", key), key)
            ftype = (fld.get("type") or "text").lower()
            if ftype in _FIELD_TYPE_TEXT:
                draw_text(label, name)
            elif ftype in _FIELD_TYPE_TEXTAREA:
                draw_textarea(label, name, rows=5)
            elif ftype in _FIELD_TYPE_CHECKBOX:
                draw_checkbox(label, name)
            else:
                draw_text(label, name)
        y -= 6

    misc = schema.get("misc", {})
    if ("stadt_default" in misc) or ("date_placeholder" in misc):
        if y - 40 < bottom:
            new_page()
        # Ort
        c.drawString(x_label, y - 12, i18n.get("field.ort", "Ort") + ":")
        _fill_box(c, x_field, y - 16, field_w / 2 - 10, 16)
        c.acroForm.textfield(
            name="stadt",
            tooltip=i18n.get("field.ort", "Ort"),
            x=x_field,
            y=y - 16,
            width=field_w / 2 - 10,
            height=16,
            borderStyle="inset",
            borderWidth=1,
            forceBorder=True,
        )
        # Datum
        c.drawString(x_field + field_w / 2 + 10, y - 12, i18n.get("field.datum", "Datum") + ":")
        _fill_box(c, x_field + field_w / 2 + 50, y - 16, field_w / 2 - 50, 16)
        c.acroForm.textfield(
            name="datum",
            tooltip=i18n.get("field.datum", "Datum"),
            x=x_field + field_w / 2 + 50,
            y=y - 16,
            width=field_w / 2 - 50,
            height=16,
            borderStyle="inset",
            borderWidth=1,
            forceBorder=True,
        )
        y -= 28

    # Signature guide box
    if y - 50 < bottom:
        new_page()
    c.drawString(x_label, y - 12, i18n.get("signature.title", "Unterschrift") + ":")
    _outline_box(c, x_field, y - 40, 6 * cm, 30)
    y -= 46

# ------------- Drawing primitives -------------

def _fill_box(c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
    c.setFillColorRGB(0.85, 0.89, 1.0)  # light bluish
    c.rect(x, y, w, h, stroke=1, fill=1)
    c.setFillColor(colors.black)

def _outline_box(c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
    c.setFillColorRGB(1, 1, 1)
    c.rect(x, y, w, h, stroke=1, fill=0)
    c.setFillColor(colors.black)
