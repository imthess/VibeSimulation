"""PDF report (circuit drawing + truth table) written without any extra library."""
import datetime

from ..core.bits import fmt
from ..core.render import ACCENT, BAD, FILL, LABEL, MUTED, OFF, ON, OUTLINE, Renderer
from ..layout.painter import CircuitPainter, extent

PALETTE = {OUTLINE: "#151a2d", FILL: "#ffffff", MUTED: "#6a7285", ON: "#16a34a", OFF: "#9aa3b5", LABEL: "#4f46e5", ACCENT: "#4f46e5", BAD: "#d92d20"}


def _rgb(h):
    h = h.lstrip("#"); return " ".join(f"{int(h[i:i + 2], 16) / 255:.3f}" for i in (0, 2, 4))


def _tw(s, size, bold=False):
    w = 0
    for ch in s:
        w += 0.556 if ch.isdigit() else 0.69 if ch.isupper() else 0.28 if ch in " ilj.,:;|!'" else 0.53
    return w * size * (1.07 if bold else 1)


def _esc(s):
    s = s.replace("Ω", "ohm").replace("→", "->").replace("−", "-")
    return s.encode("cp1252", "replace").decode("cp1252").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class _Page:
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
        s = str(s); w = _tw(s, size, bold)
        x = x - w / 2 if align == "c" else x - w if align == "r" else x
        self.o.append(f"BT /F{2 if bold else 1} {size:.1f} Tf {_rgb(col)} rg {x:.2f} {y:.2f} Td ({_esc(s)}) Tj ET")


def _assemble(pages):
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


def make_pdf(layout, circuit, invals, table, name="VibeSimulation", values=None):
    """table: (names, mids, outs, rows) from Circuit.table(), or None. Returns the PDF bytes."""
    W, H = 842, 595
    ACC, INK, MUT = PALETTE[ACCENT], PALETTE[OUTLINE], PALETTE[MUTED]
    values = values if values is not None else circuit.simulate(invals)
    pages = []

    def head(pg, sub):
        pg.rect(0, H - 54, W, 54, fill="#f3f4f9"); pg.rect(0, H - 54, 6, 54, fill=ACC)
        pg.text(34, H - 33, name, 20, INK, True); pg.text(34 + _tw(name, 20, True) + 12, H - 32, sub, 10.5, MUT)
        pg.text(W - 34, H - 32, datetime.date.today().isoformat(), 10, MUT, align="r")

    pg = _Page(W, H); head(pg, "circuit"); pages.append(pg)
    x0, y0, x1, y1 = extent(layout)
    ax, ay, aw, ah = 40, 60, W - 80, H - 54 - 60 - 60
    s = min(aw / (x1 - x0), ah / (y1 - y0), 1.6)
    ox = ax + (aw - (x1 - x0) * s) / 2 - x0 * s
    top = ay + ah - (ah - (y1 - y0) * s) / 2
    tf = lambda x, y: (ox + x * s, top - (y - y0) * s)
    CircuitPainter(PdfRenderer(pg, tf, s)).paint(layout, circuit, values, invals)
    pg.text(40, 36, f"{len(circuit.inputs)} inputs  ·  {len(circuit.components)} components  ·  {len(circuit.outputs)} outputs   |   input values shown: "
            + " ".join(f"{p.name}={fmt(invals.get(p.name, 0), p.width)}" for p in circuit.inputs[:8]) + ("…" if len(circuit.inputs) > 8 else ""), 9, MUT)
    if table:
        names, mids, outs, rows = table
        widths = circuit.signals()
        heads = names + mids + outs
        n_in, n_mid = len(names), len(mids)
        rh, topy, bot = 17, H - 54 - 50, 50
        per = int((topy - bot) // rh) - 1
        cws = [max(30, 12 + 6.2 * max(len(h), widths.get(h, 1))) for h in heads]
        gap = 12
        total = sum(cws) + gap * (int(n_mid > 0) + 1)
        scale = min(1, (W - 80) / total)
        cws = [c * scale for c in cws]
        total = sum(cws) + gap * (int(n_mid > 0) + 1)
        px0 = (W - total) / 2
        npg = max(1, -(-len(rows) // per))
        green = "#157f3b"
        fz = min(1, scale + 0.2)
        for k in range(npg):
            pg = _Page(W, H); head(pg, f"truth table  ·  page {k + 1} of {npg}"); pages.append(pg)
            xs, x = [], px0
            for i in range(len(heads)):
                if i in (n_in, n_in + n_mid) and i != 0 and (i == n_in or n_mid): x += gap
                xs.append(x); x += cws[i]
            y = topy - rh
            for i, nm in enumerate(heads):
                col = ACC if i < n_in else MUT if i < n_in + n_mid else green
                pg.rect(xs[i], y, cws[i], rh, fill={ACC: "#eceffd", MUT: "#eceef7", green: "#e6f6ec"}[col])
                pg.text(xs[i] + cws[i] / 2, y + 5, nm, 9.5 * fz, col, True, "c")
            for r_, row in enumerate(rows[k * per:(k + 1) * per]):
                y -= rh
                for i, v in enumerate(row):
                    if r_ % 2 == 0: pg.rect(xs[i], y, cws[i], rh, fill="#f6f7fb")
                    on = bool(v) and i >= n_in + n_mid
                    pg.text(xs[i] + cws[i] / 2, y + 5, fmt(v, widths.get(heads[i], 1)), 9 * fz, "#16a34a" if on else INK, on, "c")
            pg.text(W / 2, 24, f"{name}  ·  page {len(pages)} of {npg + 1}", 8.5, MUT, align="c")
    pages[0].text(W / 2, 24, f"{name}  ·  page 1 of {len(pages)}", 8.5, MUT, align="c")
    return _assemble(pages)


def _head(pg, W, H, name, sub):
    pg.rect(0, H - 54, W, 54, fill="#f3f4f9"); pg.rect(0, H - 54, 6, 54, fill=PALETTE[ACCENT])
    pg.text(34, H - 33, name, 20, PALETTE[OUTLINE], True); pg.text(34 + _tw(name, 20, True) + 12, H - 32, sub, 10.5, PALETTE[MUTED])
    pg.text(W - 34, H - 32, datetime.date.today().isoformat(), 10, PALETTE[MUTED], align="r")


def make_analog_pdf(netlist, layout, volts, results, digits=4, name="VibeSimulation", phasors=None):
    """Multisim report: page 1 the schematic, then the DC results (node voltages, every part's voltage / current / power)
    and the parts list (type, value, the two nets it joins)."""
    from ..analog.painter import paint_schematic
    from ..analog.units import fmt_si
    W, H = 842, 595
    ACC, INK, MUT = PALETTE[ACCENT], PALETTE[OUTLINE], PALETTE[MUTED]
    pages = []
    pg = _Page(W, H); _head(pg, W, H, name, "analog circuit  ·  DC operating point"); pages.append(pg)
    x0, y0, x1, y1 = layout.extent()
    ax, ay, aw, ah = 40, 60, W - 80, H - 54 - 60 - 60
    s = min(aw / (x1 - x0), ah / (y1 - y0), 1.6)
    ox = ax + (aw - (x1 - x0) * s) / 2 - x0 * s
    top = ay + ah - (ah - (y1 - y0) * s) / 2
    tf = lambda x, y: (ox + x * s, top - (y - y0) * s)
    paint_schematic(PdfRenderer(pg, tf, s), layout, volts, digits, tagged=False, results=results)
    pg.text(40, 36, f"{len(netlist.parts)} parts  ·  {len(netlist.nets())} nets (+ ground)" + (f"  ·  {netlist.title}" if netlist.title else ""), 9, MUT)

    # ---- data pages: one list of rows, split over as many pages as needed
    rows = [("h", "NODE VOLTAGES"), ("c", ("Net", "Voltage")), ("r", ("0 (ground)", "0 V"))]
    rows += [("r", (n, fmt_si(volts.get(n), "V", digits))) for n in netlist.nets()]
    rows += [("h", "PARTS: DC RESULTS"), ("c", ("Part", "Type", "Value", "Nets", "Voltage", "Current a→b", "Power"))]
    for p in netlist.parts:
        v, i, pw = results[p.id]
        val = p.caption(digits)
        rows.append(("r", (p.id, p.type_name, val, f"{p.nodes[0]} → {p.nodes[1]}", fmt_si(v, "V", digits), fmt_si(i, "A", digits), fmt_si(pw, "W", digits))))
    tot = sum(r_[2] for r_ in results.values() if r_[2] > 0)
    rows.append(("n", f"Total power delivered to parts: {fmt_si(tot, 'W', digits)}"))
    act = [p for p in netlist.parts if p.nterm != 2]
    if act:                                                           # transistors, op-amps, transformers: operating region and bias values
        rows += [("h", "OPERATING POINT OF TRANSISTORS, OP-AMPS AND TRANSFORMERS")]
        rows += [("n", f"{p.id} ({p.type_name}): " + ", ".join(f"{k} {v}" for k, v in p.info(volts, {}))) for p in act]
    if phasors:                                                       # AC section: phasors (peak ∠ degrees), power and the summary line
        import cmath, math
        pt, pw = phasors; ph = lambda z, u: "" if z is None else (f"0 {u}" if abs(z) < 1e-15 else f"{fmt_si(abs(z), u, digits)} ∠ {math.degrees(cmath.phase(z)):.4g}°")
        rows += [("h", f"AC ANALYSIS AT {fmt_si(pt['f'], 'Hz', digits)} (peak values, angle in degrees)"), ("c", ("Net", "Voltage"))]
        rows += [("r", (n, ph(pt["V"][n], "V"))) for n in sorted(pt["V"]) if n != "0"]
        rows += [("c", ("Part", "Voltage", "Current a→b", "P", "Q"))]
        rows += [("r", (p.id, ph(pt["parts"][p.id]["v"], "V"), ph(pt["parts"][p.id]["i"], "A"), fmt_si(pt["parts"][p.id]["s"].real, "W", digits), fmt_si(pt["parts"][p.id]["s"].imag, "var", digits))) for p in netlist.parts]
        rows.append(("n", f"Sources deliver P = {fmt_si(pw['P'], 'W', digits)}, Q = {fmt_si(pw['Q'], 'var', digits)}, S = {fmt_si(pw['S'], 'VA', digits)}" + (f", power factor {pw['pf']:.4g}" if pw["pf"] is not None else "")))
    rh, topy, bot = 17, H - 54 - 36, 50
    per = int((topy - bot) // rh)
    cols = [60, 110, 90, 130, 100, 110, 100]
    chunks = [rows[i:i + per] for i in range(0, len(rows), per)]
    for k, chunk in enumerate(chunks):
        pg = _Page(W, H); _head(pg, W, H, name, "DC results" + (f"  ·  part {k + 1} of {len(chunks)}" if len(chunks) > 1 else "")); pages.append(pg)
        y = topy
        for kind, v in chunk:
            y -= rh
            if kind == "h":
                pg.rect(40, y, W - 80, rh, fill="#eceffd"); pg.text(48, y + 5, v, 9.5, ACC, True)
            elif kind == "n": pg.text(48, y + 5, v, 9.5, INK, True)
            else:
                x = 48
                if kind == "c": pg.rect(40, y, W - 80, rh, fill="#eceef7")
                elif int(y // rh) % 2 == 0: pg.rect(40, y, W - 80, rh, fill="#f6f7fb")
                for j, cell in enumerate(v):
                    w = cols[j] if len(v) > 2 else 200
                    pg.text(x, y + 5, cell, 9, MUT if kind == "c" else INK, kind == "c")
                    x += w + 6
    for i, p_ in enumerate(pages): p_.text(W / 2, 24, f"{name}  ·  page {i + 1} of {len(pages)}", 8.5, MUT, align="c")
    return _assemble(pages)
