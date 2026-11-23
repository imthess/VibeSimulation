"""PDF writer without any extra library: ``Page`` (drawing calls), ``PdfRenderer`` (a Renderer that draws onto a page) and ``assemble``.
The Logisim and Multisim reports built on top of it live in ``workspaces/<tab>/export/pdf.py``."""
import datetime

from vibesimulation.common.render import ACCENT, BAD, FILL, LABEL, MUTED, OFF, ON, OUTLINE, Renderer
PALETTE = {OUTLINE: "#151a2d", FILL: "#ffffff", MUTED: "#6a7285", ON: "#16a34a", OFF: "#9aa3b5", LABEL: "#4f46e5", ACCENT: "#4f46e5", BAD: "#d92d20"}


def _rgb(h):
    h = h.lstrip("#"); return " ".join(f"{int(h[i:i + 2], 16) / 255:.3f}" for i in (0, 2, 4))


def text_width(s, size, bold=False):
    w = 0
    for ch in s:
        w += 0.556 if ch.isdigit() else 0.69 if ch.isupper() else 0.28 if ch in " ilj.,:;|!'" else 0.53
    return w * size * (1.07 if bold else 1)


def _esc(s):
    s = s.replace("Ω", "ohm").replace("→", "->").replace("−", "-")
    return s.encode("cp1252", "replace").decode("cp1252").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class Page:
    def __init__(self, w, h): self.w, self.h, self.o = w, h, []

    def line(self, x1, y1, x2, y2, col="#000000", wd=1):
        self.o.append(f"{_rgb(col)} RG {wd:.2f} w 1 J {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def poly(self, pts, fill=None, stroke="#000000", wd=1):
        d = f"{pts[0][0]:.2f} {pts[0][1]:.2f} m " + " ".join(f"{x:.2f} {y:.2f} l" for x, y in pts[1:]) + " h"
        self.o.append((f"{_rgb(fill)} rg " if fill else "") + (f"{_rgb(stroke)} RG {wd:.2f} w 1 j " if stroke else "") + d + (" B" if fill and stroke else " f" if fill else " S"))

    def path(self, pts, col="#000000", wd=1):
        self.o.append(f"{_rgb(col)} RG {wd:.2f} w 1 j 1 J {pts[0][0]:.2f} {pts[0][1]:.2f} m " + " ".join(f"{x:.2f} {y:.2f} l" for x, y in pts[1:]) + " S")

    def circle(self, cx, cy, r, fill=None, stroke="#000000", wd=1):
        k = 0.5523 * r
        d = (f"{cx + r:.2f} {cy:.2f} m {cx + r:.2f} {cy + k:.2f} {cx + k:.2f} {cy + r:.2f} {cx:.2f} {cy + r:.2f} c "
             f"{cx - k:.2f} {cy + r:.2f} {cx - r:.2f} {cy + k:.2f} {cx - r:.2f} {cy:.2f} c "
             f"{cx - r:.2f} {cy - k:.2f} {cx - k:.2f} {cy - r:.2f} {cx:.2f} {cy - r:.2f} c "
             f"{cx + k:.2f} {cy - r:.2f} {cx + r:.2f} {cy - k:.2f} {cx + r:.2f} {cy:.2f} c h")
        self.o.append((f"{_rgb(fill)} rg " if fill else "") + (f"{_rgb(stroke)} RG {wd:.2f} w " if stroke else "") + d + (" B" if fill and stroke else " f" if fill else " S"))

    def rect(self, x, y, w, h, fill=None, stroke=None, wd=1):
        self.o.append((f"{_rgb(fill)} rg " if fill else "") + (f"{_rgb(stroke)} RG {wd:.2f} w " if stroke else "") + f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re" + (" B" if fill and stroke else " f" if fill else " S"))

    def text(self, x, y, s, size=10, col="#000000", bold=False, align="l"):
        s = str(s); w = text_width(s, size, bold)
        x = x - w / 2 if align == "c" else x - w if align == "r" else x
        self.o.append(f"BT /F{2 if bold else 1} {size:.1f} Tf {_rgb(col)} rg {x:.2f} {y:.2f} Td ({_esc(s)}) Tj ET")


def assemble(pages):
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", None,
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"]
    kids = []
    for pg in pages:
        body = "\n".join(pg.o).encode("cp1252", "replace")
        pid, cid = len(objs) + 1, len(objs) + 2; kids.append(f"{pid} 0 R")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {pg.w} {pg.h}] /Contents {cid} 0 R /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> >>".encode())
        objs.append(b"<< /Length %d >>\nstream\n" % len(body) + body + b"\nendstream")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>".encode()
    out = bytearray(b"%PDF-1.4\n"); offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(out)); out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info << /Title (VibeSimulation report) /Producer (VibeSimulation) >> >>\nstartxref\n{x}\n%%EOF\n".encode()
    return bytes(out)


class PdfRenderer(Renderer):
    """Draws circuit shapes onto a PDF page; circuit units are mapped to page units by ``tf``."""
    def __init__(self, page, tf, scale):
        self.pg, self.tf, self.s = page, tf, scale

    def _c(self, role):
        return PALETTE.get(role, role)

    def line(self, pts, width=2, role=OUTLINE, tags=()):
        self.pg.path([self.tf(*q) for q in pts], self._c(role), max(0.8, width * self.s * 0.8))

    def polygon(self, pts, fill=FILL, outline=OUTLINE, width=2, tags=()):
        self.pg.poly([self.tf(*q) for q in pts], self._c(fill) if fill else None, self._c(outline) if outline else None, max(0.8, width * self.s * 0.8))

    def circle(self, cx, cy, r, fill=FILL, outline=OUTLINE, width=2, tags=()):
        X, Y = self.tf(cx, cy)
        self.pg.circle(X, Y, r * self.s, self._c(fill) if fill else None, self._c(outline) if outline else None, max(0.6, width * self.s * 0.8))

    def rect(self, x0, y0, x1, y1, fill=FILL, outline=OUTLINE, width=2, tags=()):
        self.polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill, outline, width)

    def text(self, x, y, s, size=10, role=MUTED, bold=False, anchor="c", tags=()):
        X, Y = self.tf(x, y)
        fs = max(5.5, size * self.s * 0.85)
        v = "n" if anchor.startswith("n") and len(anchor) > 1 or anchor == "n" else "s" if anchor.startswith("s") else "c"
        h = "w" if anchor.endswith("w") else "e" if anchor.endswith("e") else "c"
        dy = {"c": -fs * 0.35, "n": -fs * 0.85, "s": fs * 0.15}[v]
        self.pg.text(X, Y + dy, s, fs, self._c(role), bold, {"c": "c", "w": "l", "e": "r"}[h])


def head(pg, W, H, name, sub):
    pg.rect(0, H - 54, W, 54, fill="#f3f4f9"); pg.rect(0, H - 54, 6, 54, fill=PALETTE[ACCENT])
    pg.text(34, H - 33, name, 20, PALETTE[OUTLINE], True); pg.text(34 + text_width(name, 20, True) + 12, H - 32, sub, 10.5, PALETTE[MUTED])
    pg.text(W - 34, H - 32, datetime.date.today().isoformat(), 10, PALETTE[MUTED], align="r")
