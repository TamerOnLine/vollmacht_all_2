# modules/pdf_utils.py
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle

def base_table_style() -> TableStyle:
    return TableStyle([
        ("BOX", (0,0), (-1,-1), 1, colors.black),
        ("INNERGRID", (0,0), (-1,-1), 0.5, colors.black),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ])

def checkbox_box(checked: bool, size=12) -> Table:
    t = Table([["X" if checked else ""]], colWidths=[size], rowHeights=[size])
    t.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 1, colors.black),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("FONTSIZE", (0,0), (-1,-1), size),
        ("LEADING", (0,0), (-1,-1), size),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    return t

def checkbox_row(label: str, checked: bool, *, size=12, label_width=150) -> Table:
    t = Table([[checkbox_box(checked, size=size), label]],
              colWidths=[size+2, label_width], rowHeights=[size])
    t.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 2),
        ("TOPPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    return t
