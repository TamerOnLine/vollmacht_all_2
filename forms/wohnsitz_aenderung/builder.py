from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet

from modules.pdf_utils import base_table_style
from modules.signature_utils import build_signature_block

def build_pdf(data: dict, i18n: dict, pdf_options: dict, signature_bytes: bytes | None = None) -> bytes:
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
    title_style = styles["Title"]
    normal = styles["Normal"]

    elems = []

    # رأس الجهة الرسمية
    elems.append(Paragraph("<b>Bürgeramt / Meldebehörde</b><br/>Musterstraße 12, 10115 Berlin<br/>Tel: 030 123456", normal))
    elems.append(Spacer(1, 12))

    # العنوان الرئيسي
    elems.append(Paragraph(
        f"<b>{i18n.get(pdf_options.get('title_i18n', 'app.title'), 'Antrag auf Wohnsitzänderung')}</b>",
        title_style
    ))
    elems.append(Spacer(1, 12))

    # جدول البيانات
    tstyle = base_table_style()
    tbl = Table([
        [i18n.get("person.name"), data.get("person_name", "")],
        [i18n.get("person.geb"), data.get("person_geb", "")],
        [i18n.get("person.id_number"), data.get("person_id_number", "")],
        [i18n.get("person.customer_number"), data.get("person_customer_number", "")],
        [i18n.get("person.alt_addr"), data.get("person_alt_addr", "")],
        [i18n.get("person.neu_addr"), data.get("person_neu_addr", "")],
        [i18n.get("person.reason"), data.get("person_reason", "")]
    ], colWidths=[180, 320])
    tbl.setStyle(tstyle)
    elems += [tbl, Spacer(1, 16)]

    # إقرار قانوني
    elems.append(Paragraph(i18n.get("declaration.text"), normal))
    elems.append(Spacer(1, 12))

    # Ort / Datum
    elems.append(Paragraph(
        f"{i18n.get('field.ort')}: {data.get('stadt','')}    {i18n.get('field.datum')}: {data.get('datum','')}",
        normal
    ))
    elems.append(Spacer(1, 12))

    # توقيع مقدم الطلب
    sig_block = build_signature_block(
        signature_bytes,
        pdf_options,
        label_text=i18n.get("signature.title")
    )
    elems += sig_block

    elems.append(Spacer(1, 20))

    # توقيع الجهة الرسمية
    elems.append(Paragraph(i18n.get("signature.official"), normal))
    elems.append(Spacer(1, 30))
    elems.append(Paragraph("_________________________", normal))

    doc.build(elems)
    buf.seek(0)
    return buf.read()
