"""Multisim report as a PDF: the schematic, the DC results and the parts list."""
from vibesimulation.common.pdf_writer import PALETTE, PdfRenderer, Page, assemble, head
from vibesimulation.common.render import ACCENT, MUTED, OUTLINE


def make_analog_pdf(netlist, layout, volts, results, digits=4, name="VibeSimulation", phasors=None):
    """Multisim report: page 1 the schematic, then the DC results (node voltages, every part's voltage / current / power)
    and the parts list (type, value, the two nets it joins)."""
    from vibesimulation.workspaces.multisim.layout.painter import paint_schematic
    from vibesimulation.workspaces.multisim.core.units import fmt_si
    W, H = 842, 595
    ACC, INK, MUT = PALETTE[ACCENT], PALETTE[OUTLINE], PALETTE[MUTED]
    pages = []
    pg = Page(W, H); head(pg, W, H, name, "analog circuit  ·  DC operating point"); pages.append(pg)
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
        pg = Page(W, H); head(pg, W, H, name, "DC results" + (f"  ·  part {k + 1} of {len(chunks)}" if len(chunks) > 1 else "")); pages.append(pg)
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
    return assemble(pages)
