"""Logisim report as a PDF: the circuit drawing, then its truth table."""
import datetime

from vibesimulation.workspaces.logisim.core.bits import fmt
from vibesimulation.common.pdf_writer import PALETTE, PdfRenderer, Page, assemble, text_width
from vibesimulation.common.render import ACCENT, MUTED, OUTLINE
from vibesimulation.workspaces.logisim.layout.painter import CircuitPainter, extent


def make_pdf(layout, circuit, invals, table, name="VibeSimulation", values=None):
    """table: (names, mids, outs, rows) from Circuit.table(), or None. Returns the PDF bytes."""
    W, H = 842, 595
    ACC, INK, MUT = PALETTE[ACCENT], PALETTE[OUTLINE], PALETTE[MUTED]
    values = values if values is not None else circuit.simulate(invals)
    pages = []

    def head(pg, sub):
        pg.rect(0, H - 54, W, 54, fill="#f3f4f9"); pg.rect(0, H - 54, 6, 54, fill=ACC)
        pg.text(34, H - 33, name, 20, INK, True); pg.text(34 + text_width(name, 20, True) + 12, H - 32, sub, 10.5, MUT)
        pg.text(W - 34, H - 32, datetime.date.today().isoformat(), 10, MUT, align="r")

    pg = Page(W, H); head(pg, "circuit"); pages.append(pg)
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
            pg = Page(W, H); head(pg, f"truth table  ·  page {k + 1} of {npg}"); pages.append(pg)
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
    return assemble(pages)
