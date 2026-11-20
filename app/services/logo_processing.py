"""Module xử lý và chuẩn hóa logo công ty (Vanilla Python + Pillow).
Tuân thủ techrecruit-rules: thuần túy, <= 120 dòng, không phụ thuộc DB/web framework.
"""
import io
from PIL import Image, ImageChops, ImageOps

Image.MAX_IMAGE_PIXELS = 25_000_000
MAX_RAW_BYTES = 2 * 1024 * 1024
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP", "GIF"}


class LogoError(Exception):
    """Lỗi xử lý logo với mã lỗi tương ứng."""
    def __init__(self, code: str, message: str = ""):
        self.code = code
        self.message = message or code
        super().__init__(self.message)


def _autocrop(img: Image.Image) -> Image.Image:
    """Tự cắt viền trong suốt hoặc nền đơn sắc đồng nhất theo màu 4 góc."""
    alpha = img.getchannel("A")
    amin, amax = alpha.getextrema()
    if amin < 250:
        mask = alpha.point(lambda a: 255 if a > 15 else 0)
        bbox = mask.getbbox()
        if not bbox:
            raise LogoError("blank_image")
        return img.crop(bbox)

    rgb = img.convert("RGB")
    w, h = rgb.size
    corners = [rgb.getpixel((0, 0)), rgb.getpixel((w - 1, 0)), rgb.getpixel((0, h - 1)), rgb.getpixel((w - 1, h - 1))]
    bg_r = sum(c[0] for c in corners) // 4
    bg_g = sum(c[1] for c in corners) // 4
    bg_b = sum(c[2] for c in corners) // 4

    if all(abs(c[0] - bg_r) <= 30 and abs(c[1] - bg_g) <= 30 and abs(c[2] - bg_b) <= 30 for c in corners):
        bg_img = Image.new("RGB", (w, h), (bg_r, bg_g, bg_b))
        diff_l = ImageChops.difference(rgb, bg_img).convert("L")
        mask = diff_l.point(lambda p: 255 if p > 15 else 0)
        bbox = mask.getbbox()
        if not bbox:
            raise LogoError("blank_image")
        return img.crop(bbox)

    return img


def process_logo(raw: bytes) -> dict[int, bytes]:
    """Xử lý logo thô -> {256: bytes_webp, 512: bytes_webp}."""
    if not raw:
        raise LogoError("empty_file")
    if len(raw) > MAX_RAW_BYTES:
        raise LogoError("too_large")

    try:
        img = Image.open(io.BytesIO(raw))
    except Image.DecompressionBombError:
        raise LogoError("decompression_bomb")
    except Exception:
        raise LogoError("corrupt_image")

    fmt = (img.format or "").upper()
    if fmt not in ALLOWED_FORMATS:
        raise LogoError("unsupported_format")

    if (img.width * img.height) > Image.MAX_IMAGE_PIXELS:
        raise LogoError("decompression_bomb")

    if getattr(img, "is_animated", False):
        try:
            img.seek(0)
        except Exception:
            pass

    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    try:
        img = img.convert("RGBA")
    except Exception:
        raise LogoError("corrupt_image")

    img = _autocrop(img)
    crop_w, crop_h = img.size

    if min(crop_w, crop_h) < 48:
        raise LogoError("too_small")

    ratio = crop_w / crop_h
    if ratio < 0.5 or ratio > 2.0:
        raise LogoError("not_logo_shape")

    results: dict[int, bytes] = {}
    for size in (256, 512):
        inner_dim = round(size * (1 - 2 * 0.10))  # lề 10% mỗi bên (không cắt, không giãn)
        scale = min(inner_dim / crop_w, inner_dim / crop_h)
        new_w = max(1, round(crop_w * scale))
        new_h = max(1, round(crop_h * scale))

        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.paste(resized, ((size - new_w) // 2, (size - new_h) // 2), resized)

        out_io = io.BytesIO()
        canvas.save(out_io, format="WEBP", quality=90, method=6)
        results[size] = out_io.getvalue()

    return results
