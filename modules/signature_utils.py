from io import BytesIO
from typing import List
from reportlab.platypus import Image as RLImage, Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from PIL import Image as PILImage
from modules.image_utils import trim_whitespace


def build_signature_block(
    signature_bytes: bytes | None,
    pdf_options: dict,
    *,
    label_text: str = "Unterschrift"
) -> List:
    """
    Create a signature block (image + line + label) ready to be added to PDF elements.

    Args:
        signature_bytes (bytes | None): Byte content of the signature image.
        pdf_options (dict): Options for PDF rendering (e.g., dimensions, scaling, alignment).
        label_text (str, optional): Label below the signature line. Defaults to "Unterschrift".

    Returns:
        List: List of ReportLab Flowable elements representing the signature block.
    """
    styles = getSampleStyleSheet()
    block = []

    if signature_bytes:
        try:
            pil = PILImage.open(BytesIO(signature_bytes)).convert("RGBA")
            if bool(pdf_options.get("signature_trim", True)):
                pil = trim_whitespace(pil)

            box_w = float(
                pdf_options.get("signature_box_w_pt",
                                pdf_options.get("signature_width_pt", 180))
            )
            box_h = float(
                pdf_options.get("signature_box_h_pt",
                                pdf_options.get("signature_max_height_pt", 80))
            )
            mode = pdf_options.get("signature_scale_mode", "fit")
            align = pdf_options.get("signature_align", "LEFT")

            if mode == "stretch":
                out_w, out_h = box_w, box_h
            else:
                w, h = pil.size
                aspect = (h / w) if w else 1.0
                out_w = box_w
                out_h = out_w * aspect
                if out_h > box_h:
                    out_h = box_h
                    out_w = out_h / aspect

            tmp = BytesIO()
            pil.save(tmp, format="PNG")
            tmp.seek(0)

            sig_img = RLImage(
                tmp,
                width=out_w,
                height=out_h,
                hAlign=align if align in ("LEFT", "CENTER", "RIGHT") else "LEFT"
            )
            block += [sig_img, Spacer(1, -12)]
        except Exception:
            pass

    block += [
        Paragraph("_________________________", styles["Normal"]),
        Paragraph(label_text, styles["Normal"]),
    ]
    return block
