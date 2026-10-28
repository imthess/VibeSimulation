"""Draws the app icon (needs Pillow): packaging/icon.png, icon.ico, icon.icns (icns only on macOS builds)."""
from pathlib import Path
from PIL import Image, ImageDraw

here = Path(__file__).parent
S = 1024
im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
d.rounded_rectangle((40, 40, S - 40, S - 40), 200, fill=(79, 70, 229, 255))
w = (255, 255, 255, 255)
d.line([(200, 400), (420, 400)], w, 40); d.line([(200, 620), (420, 620)], w, 40); d.line([(700, 510), (860, 510)], w, 40)
d.polygon([(420, 300), (560, 300), (700, 510), (560, 720), (420, 720)], fill=w)
im.save(here / "icon.png")
im.save(here / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
try: im.save(here / "icon.icns")
except Exception: pass
