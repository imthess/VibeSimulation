"""Make a photo of a drawing look like a scan (like CamScanner): cut away the paper around the drawing, flatten shadows and folds,
white paper with dark lines, and a limited size. A cleaner, smaller picture is easier for the AI to read and cheaper to send.

Pure Pillow (no numpy). ``ScanOptions`` are the user's settings (Settings > AI & Import), ``scan`` does the work, ``encode`` makes the bytes to send."""
import io
from dataclasses import dataclass, fields

try:
    from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps
except Exception:                                                           # Pillow is optional: without it the picture is sent as it is
    Image = None

LOOKS = ("bw", "gray", "colour")
LOOK_NAMES = {"bw": "Black & white", "gray": "Grey", "colour": "Colour"}


@dataclass
class ScanOptions:
    crop: bool = True        # cut away the paper around the drawing
    flatten: bool = True     # remove shadows, folds and uneven light
    look: str = "bw"         # bw | gray | colour
    contrast: int = 50       # 0..100, 50 = normal; higher = harder, blacker lines
    ink: int = 50            # 0..100: how faint a stroke may be and still be kept (higher keeps fainter lines)
    size: int = 1280         # longest side in pixels; 0 keeps the size
    margin: int = 4          # % of the drawing's size kept around the crop


def from_cfg(cfg):
    """ScanOptions from the saved settings (keys ``scan_*``); unknown or broken values fall back to the defaults."""
    o = ScanOptions()
    for f in fields(o):
        v = cfg.get("scan_" + f.name, getattr(o, f.name))
        try: v = type(getattr(o, f.name))(v)
        except (TypeError, ValueError): v = getattr(o, f.name)
        setattr(o, f.name, v)
    o.look = o.look if o.look in LOOKS else "bw"
    o.contrast, o.ink, o.margin = (max(0, min(100, o.contrast)), max(0, min(100, o.ink)), max(0, min(40, o.margin)))
    o.size = 0 if o.size <= 0 else max(400, min(4000, o.size))
    return o


def open_image(data):
    """Pillow image from bytes, upright (camera rotation applied), in RGB."""
    im = Image.open(io.BytesIO(data)); im.load()
    return ImageOps.exif_transpose(im).convert("RGB")


def _paper(gray):
    """The brightness of the paper at every point (shadows and folds included), found on a small copy for speed."""
    w, h = gray.size; f = max(1.0, max(w, h) / 256)
    small = gray.resize((max(1, int(w / f)), max(1, int(h / f))), Image.BILINEAR)
    small = small.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(5))        # lines are thin: the max filter looks "through" them to the paper
    return small.resize((w, h), Image.BICUBIC)


def _darkness(gray, flatten):
    """How much darker than the paper each pixel is (0..255)."""
    if flatten: return ImageChops.subtract(_paper(gray), gray)
    return ImageChops.invert(ImageOps.autocontrast(gray, cutoff=2))


def _strokes(gray, ink, flatten):
    """Mask (0..255) of the strokes: a pixel must be darker than the paper by a threshold that depends on ``ink``."""
    lo = int(70 - 0.55 * ink)                                                 # ink 50 -> 42; ink 100 -> 15; ink 0 -> 70
    return _darkness(gray, flatten).point(lambda v: 255 if v > lo else 0)


def auto_box(im, opts=None):
    """(x0, y0, x1, y1) around the drawing: the densest group of strokes, plus a margin. Faint marks (pencil ghosts, dust) are ignored."""
    o = opts or ScanOptions(); W, H = im.size; f = 4
    small = _strokes(ImageOps.grayscale(im), o.ink, True).resize((max(1, W // f), max(1, H // f)), Image.BOX).point(lambda v: 255 if v > 40 else 0)
    small = ImageChops.subtract(small, small.filter(ImageFilter.MinFilter(9)).filter(ImageFilter.MaxFilter(15)))      # wide dark areas (the table behind the page, a page edge) are not strokes
    w, h = small.size; px = small.load()
    cols = [sum(px[x, y] for y in range(h)) for x in range(w)]; rows = [sum(px[x, y] for x in range(w)) for y in range(h)]
    def run(prof, gap):
        idx = [i for i, v in enumerate(prof) if v > 255 * 0.8]                # at least ~1 stroke pixel per 4 px column
        if not idx: return None
        groups = [[idx[0], idx[0]]]
        for i in idx[1:]:
            if i - groups[-1][1] <= gap: groups[-1][1] = i
            else: groups.append([i, i])
        return max(groups, key=lambda g: sum(prof[g[0]:g[1] + 1]))
    gx, gy = run(cols, 25), run(rows, 25)
    if not gx or not gy: return (0, 0, W, H)
    x0, x1, y0, y1 = gx[0] * f, (gx[1] + 1) * f, gy[0] * f, (gy[1] + 1) * f
    mx, my = max(8, int((x1 - x0) * o.margin / 100)), max(8, int((y1 - y0) * o.margin / 100))
    return (max(0, x0 - mx), max(0, y0 - my), min(W, x1 + mx), min(H, y1 + my))


def clean_box(box, size):
    """A crop box inside the picture, at least 20 px wide and high."""
    W, H = size; x0, y0, x1, y1 = (int(v) for v in box)
    x0, x1 = sorted((max(0, min(W - 20, x0)), max(20, min(W, x1)))); y0, y1 = sorted((max(0, min(H - 20, y0)), max(20, min(H, y1))))
    return (x0, y0, max(x1, x0 + 20), max(y1, y0 + 20))


def scan(im, opts=None, box=None):
    """The scanned picture (Pillow image). ``box`` is the crop in picture pixels; None = automatic (when ``opts.crop`` is on) or the whole picture."""
    o = opts or ScanOptions()
    if box is None and o.crop: box = auto_box(im, o)
    if box is not None: im = im.crop(clean_box(box, im.size))
    gray = ImageOps.grayscale(im)
    if o.look == "colour":
        out = ImageOps.autocontrast(im, cutoff=1) if not o.flatten else _flatten_colour(im, gray)
        out = ImageEnhance.Contrast(out).enhance(max(0.2, 1 + (o.contrast - 50) / 100))
    else:
        dark = _darkness(gray, o.flatten)
        if o.look == "bw":
            lo = int(70 - 0.55 * o.ink)                                              # strokes fainter than this are dropped
            band = max(6, int(80 - o.contrast * 0.7))                                # width of the grey edge: contrast 50 -> 45, 100 -> 10 (hard)
            out = dark.point(lambda v: 255 - max(0, min(255, int((v - lo) * 255 / band)))).convert("RGB")
        else:
            k = 1.2 + (o.contrast - 50) / 40
            out = dark.point(lambda v: 255 - max(0, min(255, int(v * k)))).convert("RGB")
    if o.size and max(out.size) > o.size:
        s = o.size / max(out.size); out = out.resize((max(1, round(out.width * s)), max(1, round(out.height * s))), Image.LANCZOS)
    return out


def _flatten_colour(im, gray):
    paper = _paper(gray)
    r, g, b = im.split()
    def lift(c): return ImageChops.add(c, ImageChops.subtract(Image.new("L", c.size, 255), paper))
    return Image.merge("RGB", (lift(r), lift(g), lift(b)))


def encode(im, look="bw"):
    """(bytes, mime) of a picture to send: PNG for black & white / grey line art, JPEG for colour."""
    out = io.BytesIO()
    if look == "colour": im.convert("RGB").save(out, "JPEG", quality=90); return out.getvalue(), "image/jpeg"
    im.convert("L").save(out, "PNG", optimize=True); return out.getvalue(), "image/png"


def prepare(data, mime, opts, box=None):
    """What to send for a picture: (bytes, mime, info). On any problem (or without Pillow) the original is returned unchanged."""
    if Image is None: return data, mime, {"scanned": False, "why": "Pillow is not installed"}
    try:
        im = open_image(data); sc = scan(im, opts, box)
        b, m = encode(sc, opts.look)
        return b, m, {"scanned": True, "size": sc.size, "from": im.size, "bytes": len(b)}
    except Exception as e:
        return data, mime, {"scanned": False, "why": str(e)}
