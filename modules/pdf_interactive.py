from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from PIL import Image as PILImage

from modules.image_utils import trim_whitespace  # قص الهوامش الموحّد

FF_MULTILINE = 1 << 12  # 4096


def _read_layout(form_key: Optional[str]) -> Optional[Dict[str, Any]]:
    if not form_key:
        return None
    p = Path(f"forms/{form_key}/layout.json")
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _label_from_i18n(i18n: Dict[str, str], item: Dict[str, Any], fallback_key: str = "name") -> str:
    return i18n.get(item.get("label_i18n", ""), item.get(fallback_key, ""))


def _text_from_i18n(i18n: Dict[str, str], item: Dict[str, Any], key: str = "text", i18n_key: str = "text_i18n") -> str:
    if item.get(i18n_key):
        return i18n.get(item[i18n_key], item.get(key, ""))
    return item.get(key, "")


def _booly(x: Any) -> bool:
    s = str(x or "").strip().lower()
    return s in {"1", "true", "y", "yes", "ja", "on", "x", "✓", "checked"}


def _fill_box(c: canvas.Canvas, x: float, y: float, w: float, h: float, *, fill_rgb=(1.0, 1.0, 1.0)) -> None:
    c.setFillColorRGB(*fill_rgb)
    c.rect(x, y, w, h, stroke=1, fill=1)
    c.setFillColor(colors.black)


def build_interactive_pdf(
    schema: Dict[str, Any],
    i18n: Dict[str, str],
    *,
    pdf_options: Optional[Dict[str, Any]] = None,
    file_title: Optional[str] = None,
    form_key: Optional[str] = None,
    form_data: Optional[Dict[str, Any]] = None,
    flatten: bool = False,
) -> bytes:
    pdf_options = pdf_options or {}
    data = form_data or {}
    page_w, page_h = A4

    mem = BytesIO()
    c = canvas.Canvas(mem, pagesize=A4)
    c.setAuthor("vollmacht_all")
    if file_title:
        c.setTitle(file_title)

    layout = _read_layout(form_key or schema.get("__form_key__"))
    if layout:
        _render_by_layout_json(c, layout, i18n, page_w, page_h, data, flatten=flatten)
        c.save()
        mem.seek(0)
        return mem.read()

    _render_auto_layout(c, schema, i18n, pdf_options, page_w, page_h, data, flatten=flatten)
    c.save()
    mem.seek(0)
    return mem.read()


def _render_by_layout_json(
    c: canvas.Canvas,
    layout: Dict[str, Any],
    i18n: Dict[str, str],
    page_w: float,
    page_h: float,
    data: Dict[str, Any],
    *,
    flatten: bool = False,
) -> None:
    draw_boxes_interactive = bool(layout.get("draw_boxes", True)) and (not flatten)
    fields: List[Dict[str, Any]] = list(layout.get("fields", []) or [])
    backgrounds: List[str] = list(layout.get("backgrounds", []) or [])

    styles = getSampleStyleSheet()
    pstyle = styles["Normal"]
    pstyle.fontName = "Helvetica"
    pstyle.fontSize = 10
    pstyle.leading = 12

    def _draw_background(page_index: int) -> None:
        if 0 <= page_index < len(backgrounds):
            bg_path = backgrounds[page_index]
            try:
                c.drawImage(bg_path, 0, 0, width=page_w, height=page_h, preserveAspectRatio=False, mask="auto")
            except Exception:
                pass

    c.setFont("Helvetica", 10)
    current_page = 1
    _draw_background(0)

    for f in fields:
        page = int(f.get("page", 1))
        while page > current_page:
            c.showPage()
            c.setFont("Helvetica", 10)
            current_page += 1
            _draw_background(current_page - 1)

        kind = (f.get("type") or "text").lower()

        if kind == "label":
            txt = _text_from_i18n(i18n, f, key="text", i18n_key="text_i18n")
            size = int(f.get("size", 10))
            c.setFont("Helvetica-Bold" if f.get("bold") else "Helvetica", size)
            c.drawString(float(f.get("x", 0)), float(f.get("y", 0)), txt)
            c.setFont("Helvetica", 10)
            continue

        if kind == "line":
            x1, y1 = float(f.get("x1", 0)), float(f.get("y1", 0))
            x2, y2 = float(f.get("x2", 0)), float(f.get("y2", 0))
            width = float(f.get("width", 0.8))
            c.setLineWidth(width)
            c.line(x1, y1, x2, y2)
            continue

        if kind == "rect":
            x, y, w, h = float(f["x"]), float(f["y"]), float(f["w"]), float(f["h"])
            c.setFillColorRGB(1, 1, 1)
            c.rect(x, y, w, h, stroke=1, fill=0)
            c.setFillColor(colors.black)
            continue

        x, y, w, h = float(f["x"]), float(f["y"]), float(f["w"]), float(f["h"])
        label = _label_from_i18n(i18n, f)

        if kind == "image":
            value_key = f.get("value_from") or f.get("name")
            raw = data.get(value_key)
            if raw:
                try:
                    pil = PILImage.open(BytesIO(raw)).convert("RGBA")
                    if f.get("trim", True):
                        pil = trim_whitespace(pil)
                    mode = (f.get("scale_mode") or "fit").lower()
                    w_box, h_box = w, h
                    w_img, h_img = pil.size
                    if mode == "stretch":
                        dw, dh = w_box, h_box
                    else:
                        aspect = h_img / float(w_img or 1)
                        dw = w_box
                        dh = dw * aspect
                        if dh > h_box:
                            dh = h_box
                            dw = dh / (aspect or 1)
                    img = ImageReader(pil)
                    c.drawImage(img, x, y, width=dw, height=dh, mask="auto")
                except Exception:
                    pass
            continue

        if kind == "checkbox":
            checked = f.get("checked")
            if "checked_from" in f:
                checked = _booly(data.get(f.get("checked_from")))
            elif checked is None:
                value_key = f.get("value_from") or f.get("name")
                checked = _booly(data.get(value_key))

            if flatten:
                size = min(w, h)
                c.rect(x, y, size, size, stroke=1, fill=0)
                if checked:
                    c.setFont("Helvetica", 12)
                    c.drawString(x + 2, y + 1, "✓")
                    c.setFont("Helvetica", 10)
            else:
                if draw_boxes_interactive:
                    col = tuple(f.get("fill_rgb", layout.get("fill_rgb", (1.0, 1.0, 1.0))))
                    _fill_box(c, x, y, min(w, h), min(w, h), fill_rgb=col)
                c.acroForm.checkbox(
                    name=f.get("name"),
                    tooltip=label,
                    x=x,
                    y=y,
                    size=min(w, h),
                    borderStyle="solid",
                    borderWidth=float(f.get("borderWidth", 0)),
                    checked=bool(checked),
                    buttonStyle=f.get("buttonStyle", "check"),
                )
            continue

        # text / textarea
        if flatten:
            val = str(data.get(f.get("value_from") or f.get("name"), f.get("default", "")) or "")
            styles = getSampleStyleSheet()
            pstyle = styles["Normal"]
            pstyle.fontName = "Helvetica"
            pstyle.fontSize = 10
            pstyle.leading = 12
            if kind in ("textarea", "multiline"):
                para = Paragraph(val.replace("\n", "<br/>"), pstyle)
                para.wrapOn(c, w - 2, h - 2)
                para.drawOn(c, x + 1, y + 1)
            else:
                c.setFont("Helvetica", 10)
                c.drawString(x + 1, y + h - 12, val)
        else:
            if draw_boxes_interactive:
                col = tuple(f.get("fill_rgb", layout.get("fill_rgb", (1.0, 1.0, 1.0))))
                _fill_box(c, x, y, w, h, fill_rgb=col)
            flags = FF_MULTILINE if kind in ("textarea", "multiline") else 0
            value_key = f.get("value_from") or f.get("name")
            default_value = f.get("default", "")
            value = str(data.get(value_key, default_value) or "")
            col_tuple = f.get("fill_rgb", layout.get("fill_rgb", (1.0, 1.0, 1.0)))
            fillColor = colors.Color(*col_tuple) if col_tuple else None

            c.acroForm.textfield(
                name=f.get("name"),
                tooltip=label,
                x=x,
                y=y,
                width=w,
                height=h,
                borderStyle=f.get("borderStyle", "inset"),
                borderWidth=float(f.get("borderWidth", 0)),
                forceBorder=bool(f.get("forceBorder", False)),
                fieldFlags=flags,
                value=value,
                fillColor=fillColor,
                textColor=colors.black,
            )


def _render_auto_layout(
   c: canvas.Canvas,
   schema: Dict[str, Any],
   i18n: Dict[str, str],
   pdf_options: Dict[str, Any],
   page_w: float,
   page_h: float,
   data: Dict[str, Any],
   *,
   flatten: bool = False,
) -> None:
    left = float(pdf_options.get("leftMargin", 40))
    right = float(pdf_options.get("rightMargin", 40))
    top = float(pdf_options.get("topMargin", 36))
    bottom = float(pdf_options.get("bottomMargin", 36))
    draw_boxes = bool(pdf_options.get("interactive_draw_boxes", True)) and (not flatten)

    fill_rgb_opt = pdf_options.get("interactive_fill_rgb", (1.0, 1.0, 1.0))
    auto_fill = colors.Color(*fill_rgb_opt)

    title_key = pdf_options.get("title_i18n", "app.title")
    doc_title = i18n.get(title_key, "Interactive Form")

    x_label = left
    x_field = left + 250
    field_w = page_w - right - x_field
    line_h = 18
    y = page_h - top

    c.setFont("Helvetica-Bold", 14)
    c.drawString(x_label, y, doc_title)
    y -= 28
    c.setFont("Helvetica", 10)

    styles = getSampleStyleSheet()
    pstyle = styles["Normal"]
    pstyle.fontName = "Helvetica"
    pstyle.fontSize = 10
    pstyle.leading = 12

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
        if flatten:
            val = str(data.get(name, "") or "")
            c.drawString(x_field + 1, y - 12, val)
        else:
            if draw_boxes:
                _fill_box(c, x_field, y - 16, field_w, 16, fill_rgb=fill_rgb_opt)
            c.acroForm.textfield(
                name=name,
                tooltip=label,
                x=x_field, y=y - 16,
                width=field_w, height=16,
                borderStyle="inset",
                borderWidth=0,
                forceBorder=False,
                value=str(data.get(name, "")),
                fillColor=auto_fill,
                textColor=colors.black,
            )
        y -= line_h

    def draw_textarea(label: str, name: str, rows: int = 5):
        nonlocal y
        h = max(16 * rows + 4, 36)
        if y - h < bottom:
            new_page()
        c.drawString(x_label, y - 12, f"{label}:")
        if flatten:
            val = str(data.get(name, "") or "")
            para = Paragraph(val.replace("\n", "<br/>"), pstyle)
            para.wrapOn(c, field_w - 2, h - 8)
            para.drawOn(c, x_field + 1, y - h + 6)
        else:
            if draw_boxes:
                _fill_box(c, x_field, y - h + 4, field_w, h - 8, fill_rgb=fill_rgb_opt)
            c.acroForm.textfield(
                name=name,
                tooltip=label,
                x=x_field, y=y - h + 4,
                width=field_w, height=h - 8,
                borderStyle="inset",
                borderWidth=0,
                forceBorder=False,
                fieldFlags=FF_MULTILINE,
                value=str(data.get(name, "")),
                fillColor=auto_fill,
                textColor=colors.black,
            )
        y -= h + 4

    def draw_checkbox(label: str, name: str):
        nonlocal y
        if y - line_h < bottom:
            new_page()
        box_size = 12
        if flatten:
            c.rect(x_field, y - 14, box_size, box_size, stroke=1, fill=0)
            if _booly(data.get(name)):
                c.setFont("Helvetica", 12)
                c.drawString(x_field + 2, y - 13, "✓")
                c.setFont("Helvetica", 10)
            c.drawString(x_field + box_size + 6, y - 12, label)
        else:
            if draw_boxes:
                _fill_box(c, x_field, y - 14, box_size, box_size, fill_rgb=fill_rgb_opt)
            c.acroForm.checkbox(
                name=name,
                tooltip=label,
                x=x_field, y=y - 14,
                size=box_size,
                borderStyle="solid",
                borderWidth=0,
                checked=_booly(data.get(name)),
                buttonStyle="check",
            )
            c.drawString(x_field + box_size + 6, y - 12, label)
        y -= line_h

    def draw_section(title: str):
        nonlocal y
        if y - 20 < bottom:
            new_page()
        c.setFont("Helvetica-Bold", 11)
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
            if ftype in {"text", "input", "string"}:
                draw_text(label, name)
            elif ftype in {"textarea", "multiline"}:
                draw_textarea(label, name, rows=5)
            elif ftype in {"checkbox", "bool", "boolean"}:
                draw_checkbox(label, name)
            else:
                draw_text(label, name)
        y -= 6

    misc = schema.get("misc", {})
    if ("stadt_default" in misc) or ("date_placeholder" in misc):
        if y - 40 < bottom:
            new_page()
        c.drawString(x_label, y - 12, i18n.get("field.ort", "Ort") + ":")
        if flatten:
            c.drawString(x_field + 1, y - 12, str(data.get("stadt", "") or ""))
        else:
            if draw_boxes:
                _fill_box(c, x_field, y - 16, field_w / 2 - 10, 16, fill_rgb=fill_rgb_opt)
            c.acroForm.textfield(
                name="stadt",
                tooltip=i18n.get("field.ort", "Ort"),
                x=x_field, y=y - 16,
                width=field_w / 2 - 10, height=16,
                borderStyle="inset",
                borderWidth=0,
                forceBorder=False,
                value=str(data.get("stadt", "")),
                fillColor=auto_fill,
                textColor=colors.black,
            )
        c.drawString(x_field + field_w / 2 + 10, y - 12, i18n.get("field.datum", "Datum") + ":")
        if flatten:
            c.drawString(x_field + field_w / 2 + 52, y - 12, str(data.get("datum", "") or ""))
        else:
            if draw_boxes:
                _fill_box(c, x_field + field_w / 2 + 50, y - 16, field_w / 2 - 50, 16, fill_rgb=fill_rgb_opt)
            c.acroForm.textfield(
                name="datum",
                tooltip=i18n.get("field.datum", "Datum"),
                x=x_field + field_w / 2 + 50, y=y - 16,
                width=field_w / 2 - 50, height=16,
                borderStyle="inset",
                borderWidth=0,
                forceBorder=False,
                value=str(data.get("datum", "")),
                fillColor=auto_fill,
                textColor=colors.black,
            )
