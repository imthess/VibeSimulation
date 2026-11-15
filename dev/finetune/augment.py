"""Make clean computer drawings look like photos and scans, so the model also copes with real pictures."""
import io
import random

from PIL import Image, ImageEnhance, ImageFilter


def _paper(rng, size):
    base = rng.choice(((255, 255, 255), (250, 247, 235), (240, 240, 240), (255, 253, 245)))
    return Image.new("RGB", size, base)


def augment(img: Image.Image, rng: random.Random, strength=1.0):
    """strength 0 = leave as is, 1 = typical, 2 = rough."""
    if strength <= 0: return img
    s = rng.uniform(0.6, 1.4)
    img = img.resize((max(64, int(img.width * s)), max(64, int(img.height * s))), Image.LANCZOS)
    if rng.random() < 0.6:                                                     # slight tilt of the page
        a = rng.uniform(-4, 4) * strength
        img = img.rotate(a, resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))
    if rng.random() < 0.5:                                                     # margin around the drawing, like a photo of a page
        m = int(rng.uniform(0.02, 0.15) * max(img.size))
        bg = _paper(rng, (img.width + 2 * m, img.height + 2 * m)); bg.paste(img, (m, m)); img = bg
    if rng.random() < 0.7:                                                     # uneven light
        w, h = img.size
        grad = Image.linear_gradient("L").resize((w, h))
        if rng.random() < 0.5: grad = grad.transpose(Image.ROTATE_90).resize((w, h))
        shade = Image.merge("RGB", [grad.point(lambda v: 255 - int((255 - v) * 0.25 * strength))] * 3)
        from PIL import ImageChops
        img = ImageChops.multiply(img, shade)
    if rng.random() < 0.5: img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.3) * strength))
    img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.75, 1.2))
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.85, 1.1))
    if rng.random() < 0.5:                                                     # sensor noise
        noise = Image.effect_noise(img.size, 14 * strength).convert("RGB")
        img = Image.blend(img, noise, 0.06 * strength)
    if rng.random() < 0.6:                                                     # JPEG artefacts
        out = io.BytesIO(); img.save(out, "JPEG", quality=rng.randint(40, 90)); out.seek(0); img = Image.open(out).convert("RGB")
    return img
