# form_to_pdf.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import mm
from reportlab.lib.colors import black, HexColor

# ==========
# نموذج (Schema) متوقع
# ==========
# schema = {
#   "title": "Vollmacht / Power of Attorney",
#   "locale": "de",
#   "page": {"size": "A4", "margins_mm": [15, 15, 15, 15]},
#   "layout": {"columns": 2, "gutter_mm": 8, "label_width_mm": 40, "field_height_mm": 8},
#   "sections": [
#     {"key": "personal", "title": "Persönliche Daten", "fields": [
#       {"key":"first_name", "label":"Vorname", "type":"text", "required":True, "placeholder":"Max"},
#       {"key":"last_name",  "label":"Nachname", "type":"text", "required":True},
#       {"key":"birthday",   "label":"Geburtsdatum", "type":"date"},
#       {"key":"gender",     "label":"Geschlecht", "type":"radio", "options":[
#           {"label":"m", "value":"m"}, {"label":"w", "value":"w"}, {"label":"div", "value":"d"}
#       ]},
#       {"key":"newsletter","label":"Newsletter", "type":"checkbox"},
#       {"key":"country",   "label":"Land", "type":"select", "options":[
#           {"label":"Deutschland","value":"DE"},
#           {"label":"Österreich", "value":"AT"},
#           {"label":"Schweiz",    "value":"CH"},
#       ]},
#       {"key":"about",     "label":"Bemerkungen", "type":"textarea", "rows":4},
#     ]},
#   ]
# }

# ==========
# إعدادات الرسم
# ==========
@dataclass
class PageSpec:
    size: str = "A4"              # "A4" أو "LETTER"
    margins_mm: List[float] = field(default_factory=lambda: [15, 15, 15, 15])  # left, right, top, bottom

    def pagesize(self):
        return A4 if self.size.upper() == "A4" else letter

@dataclass
class LayoutSpec:
    columns: int = 2
    gutter_mm: float = 8.0
    label_width_mm: float = 40.0
    field_height_mm: float = 8.0
    row_gap_mm: float = 4.0
    section_gap_mm: float = 8.0
    headline_gap_mm: float = 6.0

# ==========
# أداة تخطيط بسيطة بعمودين
# ==========
class FlowLayout:
    def __init__(self, c: canvas.Canvas, page_spec: PageSpec, layout: LayoutSpec):
        self.c = c
        self.page_spec = page_spec
        self.layout = layout

        self.page_w, self.page_h = page_spec.pagesize()
        ml, mr, mt, mb = [x * mm for x in page_spec.margins_mm]
        self.left = ml
        self.right = self.page_w - mr
        self.top = self.page_h - mt
        self.bottom = mb

        # أعمدة
        total_inner_w = (self.right - self.left)
        gutters_total = (layout.columns - 1) * (layout.gutter_mm * mm)
        self.col_w = (total_inner_w - gutters_total) / layout.columns
        self.col_x = [self.left + i * (self.col_w + layout.gutter_mm * mm) for i in range(layout.columns)]

        self.cursor_y = self.top
        self.current_col = 0

    def new_line(self, height_mm: float):
        self.cursor_y -= height_mm * mm + self.layout.row_gap_mm * mm
        if self.cursor_y < (self.bottom + 20 * mm):  # هامش سفلي إضافي للأمان
            self.new_page()

    def new_page(self):
        self.c.showPage()
        # إعادة ضبط الصفحة
        self.page_w, self.page_h = self.page_spec.pagesize()
        self.cursor_y = self.top
        self.current_col = 0

    def next_column(self):
        self.current_col += 1
        if self.current_col >= self.layout.columns:
            self.current_col = 0
            # سطر جديد (عملياً الانتقال لصف جديد عموديًا)
            self.cursor_y -= self.layout.field_height_mm * mm + self.layout.row_gap_mm * mm

    def place_label_and_field(self, label: str, field_w_mm: float, field_h_mm: float) -> tuple[float, float, float, float]:
        """ترسم التسمية وتعيد إحداثيات الحقل (x, y, w, h)."""
        x = self.col_x[self.current_col]
        y = self.cursor_y

        label_w = self.layout.label_width_mm * mm
        field_w = field_w_mm * mm
        field_h = field_h_mm * mm

        # رسم التسمية
        self.c.setFont("Helvetica", 9)
        self.c.setFillColor(black)
        self.c.drawString(x, y, label or "")

        # موضع الحقل: بجانب التسمية
        fx = x + label_w + 2 * mm
        fy = y - (field_h - 6)  # إنزال بسيط ليكون داخل الإطار
        # إطار مرئي خفيف (اختياري)
        self.c.setStrokeColor(HexColor("#999999"))
        self.c.rect(fx, fy, field_w, field_h, stroke=1, fill=0)

        # بعد الرسم، تقدّم في التخطيط
        self.next_column()
        return fx, fy, field_w, field_h

# ==========
# مُكوّنات الحقول التفاعلية
# ==========
def add_textfield(c: canvas.Canvas, name: str, x: float, y: float, w: float, h: float, multiline=False, value: str = "", tooltip: str = ""):
    c.acroForm.textfield(
        name=name, tooltip=tooltip or name, x=x, y=y, width=w, height=h,
        value=value or "", borderStyle='underlined' if not multiline else 'solid',
        fontName="Helvetica", fontSize=10, textColor=black, forceBorder=True,
        multiline=multiline
    )

def add_checkbox(c: canvas.Canvas, name: str, x: float, y: float, size: float = 10, checked=False, tooltip: str = ""):
    c.acroForm.checkbox(
        name=name, tooltip=tooltip or name, x=x, y=y, size=size,
        checked=checked, buttonStyle='check', borderColor=black
    )

def add_radio_group(c: canvas.Canvas, base_name: str, options: List[Dict[str, Any]], x: float, y: float, size: float = 10):
    # يرسم أزرارًا أفقية مع تسميات
    gap = 18
    cur_x = x
    for opt in options:
        value = str(opt.get("value", ""))
        label = str(opt.get("label", value))
        c.acroForm.radio(
            name=base_name, value=value, selected=False, x=cur_x, y=y, size=size,
            borderColor=black
        )
        c.setFont("Helvetica", 9)
        c.setFillColor(black)
        c.drawString(cur_x + size + 2, y + 1, label)
        cur_x += size + gap

def add_select(c: canvas.Canvas, name: str, x: float, y: float, w: float, h: float, options: List[Dict[str, Any]], value: Optional[str] = None):
    opts = [(o.get("label", o.get("value", "")), o.get("value", "")) for o in options]
    c.acroForm.choice(
        name=name, tooltip=name, x=x, y=y, width=w, height=h,
        options=opts, value=value or (opts[0][1] if opts else "")
    )

# ==========
# المُحوّل الرئيسي
# ==========
def schema_to_interactive_pdf(schema: Dict[str, Any], output_path: str):
    # إعداد الصفحة
    page_spec = PageSpec(
        size=schema.get("page", {}).get("size", "A4"),
        margins_mm=schema.get("page", {}).get("margins_mm", [15, 15, 15, 15]),
    )
    layout = LayoutSpec(**schema.get("layout", {}))
    page_w, page_h = page_spec.pagesize()

    c = canvas.Canvas(output_path, pagesize=page_spec.pagesize())

    # العنوان
    title = schema.get("title", "")
    if title:
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(page_w / 2, page_h - page_spec.margins_mm[2] * mm, title)

    flow = FlowLayout(c, page_spec, layout)
    flow.cursor_y = flow.top - (layout.headline_gap_mm * mm) - 6

    # معالجة الأقسام والحقول
    for sec in schema.get("sections", []):
        sec_title = sec.get("title") or sec.get("key", "")
        if sec_title:
            # عنوان قسم
            c.setFont("Helvetica-Bold", 11)
            c.setFillColor(black)
            c.drawString(flow.col_x[0], flow.cursor_y, sec_title)
            flow.cursor_y -= (layout.field_height_mm * mm + layout.section_gap_mm * mm)

        for fld in sec.get("fields", []):
            ftype = fld.get("type", "text")
            key = f'{sec.get("key","sec")}.{fld.get("key","field")}'
            label = fld.get("label", fld.get("key", key))
            tooltip = (fld.get("placeholder") or "").strip()

            # حساب عرض الحقل
            # إن كانت textarea: نعطي ارتفاعًا أكبر
            rows = int(fld.get("rows", 0) or (4 if ftype == "textarea" else 0))
            field_h_mm = (layout.field_height_mm * (rows if rows > 0 else 1))
            fx, fy, fw, fh = flow.place_label_and_field(
                label=label,
                field_w_mm=(flow.col_w / mm - layout.label_width_mm - 4),  # العرض داخل العمود ناقص عرض التسمية
                field_h_mm=field_h_mm
            )

            if ftype in ("text", "date"):
                add_textfield(c, name=key, x=fx, y=fy, w=fw, h=fh, multiline=False, tooltip=tooltip)
            elif ftype == "textarea":
                add_textfield(c, name=key, x=fx, y=fy, w=fw, h=fh, multiline=True, tooltip=tooltip)
            elif ftype == "checkbox":
                # استبدال الإطار الافتراضي بمربع صغير + تسمية كانت مرسومة مسبقًا
                # نعيد رسم المربع داخل الإطار المرسوم
                box_size = min(fh, 12)
                add_checkbox(c, name=key, x=fx + 2, y=fy + 2, size=box_size)
            elif ftype == "radio":
                opts = fld.get("options", [])
                # امسح المستطيل المرسوم (اختياري: نتجاهله ونضع الراديو فوقه)
                add_radio_group(c, base_name=key, options=opts, x=fx + 2, y=fy + 2, size=10)
            elif ftype == "select":
                opts = fld.get("options", [])
                add_select(c, name=key, x=fx, y=fy, w=fw, h=fh, options=opts, value=fld.get("value"))
            else:
                # نوع غير معروف -> حقل نصي افتراضي
                add_textfield(c, name=key, x=fx, y=fy, w=fw, h=fh, multiline=False, tooltip=tooltip)

            # سطر جديد عموديًا عند انتهاء الأعمدة
            if flow.current_col == 0:
                pass  # تم النزول تلقائيًا في next_column عند اكتمال الأعمدة

        # مسافة بعد القسم
        flow.cursor_y -= (layout.section_gap_mm * mm)

    # تذييل/ملاحظات
    c.setFont("Helvetica", 7)
    c.setFillColor(HexColor("#666666"))
    c.drawRightString(flow.right, flow.bottom - 6, "Generated by schema_to_interactive_pdf (ReportLab/AcroForm)")

    c.save()

# ==========
# مثال تشغيل سريع
# ==========
if __name__ == "__main__":
    example_schema = {
        "title": "Interactive Form Example",
        "page": {"size": "A4", "margins_mm": [15, 15, 18, 18]},
        "layout": {"columns": 2, "gutter_mm": 8, "label_width_mm": 38, "field_height_mm": 8},
        "sections": [
            {"key": "personal", "title": "Personal Data", "fields": [
                {"key":"first_name", "label":"First name", "type":"text", "required":True, "placeholder":"e.g. Max"},
                {"key":"last_name",  "label":"Last name",  "type":"text", "required":True},
                {"key":"birthday",   "label":"Birthday",   "type":"date"},
                {"key":"gender",     "label":"Gender", "type":"radio", "options":[
                    {"label":"Male","value":"m"},{"label":"Female","value":"f"},{"label":"Other","value":"o"}
                ]},
                {"key":"agree_news","label":"Agree newsletter", "type":"checkbox"},
                {"key":"country",   "label":"Country", "type":"select", "options":[
                    {"label":"Germany","value":"DE"},
                    {"label":"Austria","value":"AT"},
                    {"label":"Switzerland","value":"CH"},
                ]},
                {"key":"notes",     "label":"Notes", "type":"textarea", "rows":4},
            ]},
        ]
    }
    schema_to_interactive_pdf(example_schema, "interactive_form_example.pdf")
    print("Done: interactive_form_example.pdf")
