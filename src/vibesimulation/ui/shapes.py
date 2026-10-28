"""Drawing helpers: rounded rectangles and colour maths (used by every custom widget)."""
import base64
import math
import struct
import tkinter as tk
import zlib


def rr_points(x1, y1, x2, y2, r):
    """Polygon points of a rounded rectangle (corner radius r, clipped to half the shorter side)."""
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    if r < 1: return [x1, y1, x2, y1, x2, y2, x1, y2]
    pts, n = [], max(3, int(r / 2) + 2)
    for cx, cy, a0 in ((x2 - r, y1 + r, -90), (x2 - r, y2 - r, 0), (x1 + r, y2 - r, 90), (x1 + r, y1 + r, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n); pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
    return pts


_IMG = {}


def _png(w, h, rgba_rows):
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    raw = b"".join(b"\x00" + bytes(row) for row in rgba_rows)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")


def corner(cv, r, color, quad):
    """Anti-aliased quarter disc (quad 0=top-left, 1=top-right, 2=bottom-right, 3=bottom-left) as a PhotoImage with real transparency."""
    key = (id(cv.tk), r, color, quad); img = _IMG.get(key)
    if img is not None: return img
    if len(_IMG) > 900: _IMG.clear()
    R, G, B = (v >> 8 for v in cv.winfo_rgb(color)); S = 4; rows = []
    for j in range(r):
        row = []
        for i in range(r):
            ii, jj = (i, j) if quad == 0 else (r - 1 - i, j) if quad == 1 else (r - 1 - i, r - 1 - j) if quad == 2 else (i, r - 1 - j)
            n = 0
            for sy in range(S):
                for sx in range(S):
                    dx, dy = r - (ii + (sx + .5) / S), r - (jj + (sy + .5) / S)
                    if dx * dx + dy * dy <= r * r: n += 1
            row += (R, G, B, round(255 * n / (S * S)))
        rows.append(row)
    img = tk.PhotoImage(master=cv, data=base64.b64encode(_png(r, r, rows))); _IMG[key] = img
    return img


def rrect(cv, x1, y1, x2, y2, r, fill="", outline="", width=1, tags=(), **kw):
    """Rounded rectangle. A filled shape without outline is drawn with anti-aliased corners (smooth at any radius);
    shapes with an outline fall back to a polygon."""
    if fill and not outline and r >= 3 and not kw:
        x1, y1, x2, y2 = (int(round(v)) for v in (x1, y1, x2, y2)); r = int(min(r, (x2 - x1) // 2, (y2 - y1) // 2))
        if r >= 3:
            kw = dict(fill=fill, width=0, outline="", tags=tags)
            ids = [cv.create_rectangle(x1 + r, y1, x2 - r, y2, **kw)]
            if y2 - y1 > 2 * r:
                ids += [cv.create_rectangle(x1, y1 + r, x1 + r, y2 - r, **kw), cv.create_rectangle(x2 - r, y1 + r, x2, y2 - r, **kw)]
            for q, (cx, cy) in enumerate(((x1, y1), (x2 - r, y1), (x2 - r, y2 - r), (x1, y2 - r))):
                ids.append(cv.create_image(cx, cy, image=corner(cv, r, fill, q), anchor="nw", tags=tags))
            return ids[0]
    return cv.create_polygon(rr_points(x1, y1, x2, y2, r), fill=fill, outline=outline, width=width, tags=tags, **kw)


def rgb(h):
    h = h.lstrip("#")
    if len(h) == 3: h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hexc(c): return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in c)


def mix(a, b, t):
    """Colour a blended towards b by t (0..1)."""
    (r1, g1, b1), (r2, g2, b2) = rgb(a), rgb(b)
    return hexc((r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t))


def lum(h):
    r, g, b = (v / 255 for v in rgb(h)); return 0.2126 * r + 0.7152 * g + 0.0722 * b


def on_color(h): return "#ffffff" if lum(h) < 0.5 else "#0b0d14"
