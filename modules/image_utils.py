from PIL import Image, ImageChops

def trim_whitespace(img: Image.Image) -> Image.Image:
    """Trim white or transparent margins from an image."""
    if img.mode in ("LA", "RGBA"):
        alpha = img.split()[-1]
        bbox = alpha.getbbox()
        return img.crop(bbox) if bbox else img

    rgb = img.convert("RGB")
    bg = Image.new("RGB", rgb.size, (255, 255, 255))
    diff = ImageChops.difference(rgb, bg)
    bbox = diff.getbbox()
    return img.crop(bbox) if bbox else img
