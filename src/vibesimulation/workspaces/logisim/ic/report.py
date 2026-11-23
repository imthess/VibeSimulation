"""Text versions of the IC plan: parts list, wiring list, netlist and a step-by-step build guide."""
import csv
import io

from vibesimulation.workspaces.logisim.ic.mapper import GND, TIES, VCC


def endpoint(plan, ep):
    """Human text for a wire end: ('chip', 'U1', 3) -> 'U1 pin 3 (1Y)'."""
    kind, ref, pin = ep
    if kind == "chip":
        ch = plan.chip(ref)
        return f"{ref} ({ch.part}) pin {pin} [{ch.chip.pin_name(pin)}]"
    if kind == "ext":
        e = plan.external(ref)
        return f"{ref} ({e.label}) {pin}" if pin not in ("out", "anode") else f"{ref} ({e.label})"
    return "+5 V rail" if ref == VCC else "GND rail"


def bom(plan, board=None):
    """Rows (qty, item, note) of everything to buy."""
    rows = []
    for part, n in sorted(plan.counts().items(), key=lambda kv: (len(kv[0]), kv[0])):
        from vibesimulation.workspaces.logisim.ic import catalog as K
        c = K.chip(part)
        rows.append((n, f"{part}", c.title[0].upper() + c.title[1:] + (f"  [{c.pins}-pin DIP]" if c.pins != 14 else "")))
    kinds = {}
    for e in plan.externals: kinds[e.kind] = kinds.get(e.kind, 0) + 1
    if kinds.get("switch"): rows.append((kinds["switch"], "Toggle switch / DIP switch", "one per input; with a 10 kΩ pull-down resistor to GND each"))
    if kinds.get("switch"): rows.append((kinds["switch"], "Resistor 10 kΩ", "input pull-down"))
    nled = kinds.get("led", 0)
    if nled: rows.append((nled, "LED", "one per output"))
    segs = sum(len([p for p in e.pins.values() if p]) for e in plan.externals if e.kind in ("display_cc", "display_ca"))
    if nled + segs: rows.append((nled + segs, "Resistor 330 Ω", "current limit for every LED / display segment"))
    for e in plan.externals:
        if e.kind == "display_cc": rows.append((1, "7-segment display, common cathode", f"{e.ref}: common pin to GND"))
        if e.kind == "display_ca": rows.append((1, "7-segment display, common anode", f"{e.ref}: common pin to +5 V"))
    if kinds.get("clock"): rows.append((kinds["clock"], "Clock source", "a 555 astable (about 1 Hz to watch it) or a debounced push button"))
    pull = sum(1 for ch in plan.chips if ch.part == "74266" for c in ch.slots if c and c.roles.get("out") is not None)
    if pull: rows.append((pull, "Resistor 1 kΩ", "pull-up to +5 V on every 74266 output (open-collector)"))
    if plan.chips:
        rows.append((len(plan.chips), "Capacitor 100 nF", "decoupling: one across VCC and GND next to every IC (recommended)"))
        rows.append((1, "5 V supply", "regulated 5 V (for example a 7805 regulator or a USB supply); 74LS / 74HC need 5 V"))
    if board:
        rows.append((board.rows, "Breadboard (63 columns)", "or one long board"))
        rows.append((len(board.wires), "Jumper wires", "see the wiring list"))
    return rows


def wire_rows(board):
    plan = board.plan
    out = []
    for i, w in enumerate(board.wires, 1):
        out.append((i, w.name, endpoint(plan, w.a), endpoint(plan, w.b), w.color_name, w.holes))
    return out


def netlist(plan):
    """[(net name, [endpoint text ...])] for every signal net."""
    rows = []
    for net, ends in sorted(plan.nets().items(), key=lambda kv: (kv[0] in TIES, plan.name(kv[0]))):
        if net in TIES: continue
        rows.append((plan.name(net), [endpoint(plan, e) for e in ends]))
    return rows


def summary(plan):
    used, total = plan.gate_stats()
    parts = ", ".join(f"{n}× {p}" for p, n in sorted(plan.counts().items(), key=lambda kv: (len(kv[0]), kv[0])))
    if not plan.chips: return "No chips needed." + (" (Nothing in this circuit has a 74xx equivalent.)" if plan.unmapped else "")
    return f"{len(plan.chips)} IC{'s' if len(plan.chips) != 1 else ''}: {parts}.  {used} of {total} gates / flip-flops / blocks inside them are in use."


def chip_notes(plan, ch):
    """What each unit of a chip does, for the chip card and the guide."""
    lines = []
    for i, c in enumerate(ch.slots, 1):
        if c is None: lines.append(f"unit {i}: unused (its inputs are tied off so they do not float)")
        else: lines.append(f"unit {i}: {c.origin or '-'}" + (f"  ({c.note})" if c.note else ""))
    return lines


def to_csv(rows, header):
    f = io.StringIO(); w = csv.writer(f); w.writerow(header); w.writerows(rows)
    return f.getvalue()


def guide(plan, board, title="Circuit"):
    """A plain-text build guide: parts, chip pinouts with signals, wires."""
    L = [f"BUILD GUIDE  -  {title}", "=" * 60, "", summary(plan), ""]
    if plan.warnings or plan.unmapped:
        L.append("NOTES")
        L += [f"  - {w}" for w in plan.warnings]
        L += [f"  - NOT BUILT: {t} {i}: {why}" for i, t, why in plan.unmapped]
        L.append("")
    L += ["PARTS", "-----"] + [f"  {q:>3} x  {item}  -  {note}" for q, item, note in bom(plan, board)] + [""]
    L += ["POWER", "-----", "  Put +5 V on the red rails and GND on the blue rails; every chip below also gets VCC and GND on the pins listed.", ""]
    L += ["CHIPS (pin numbers count anticlockwise from the notch; pin 1 is at the bottom left on the breadboard)", "-----"]
    for ch in plan.chips:
        cat = ch.chip
        L.append(f"  {ch.ref}  {ch.part}  {cat.title}")
        if cat.notes: L.append(f"      note: {cat.notes}")
        for p in range(1, cat.pins + 1):
            net = ch.pins.get(p)
            what = "NC" if cat.pin_kind(p) == "nc" else ("-" if net is None else "+5 V" if net == VCC else "GND" if net == GND else plan.name(net))
            L.append(f"      pin {p:>2}  {cat.pin_name(p):<6} {what}")
        for ln in chip_notes(plan, ch): L.append(f"      {ln}")
        L.append("")
    L += ["WIRES", "-----"]
    for n, name, a, b, color, holes in wire_rows(board):
        L.append(f"  {n:>3}. {color:<7} {a}  ->  {b}     [{name}]")
    if plan.externals:
        L += ["", "OFF-BOARD PARTS", "-----"]
        for e in plan.externals:
            pins = ", ".join(f"{k}: {plan.name(v)}" for k, v in e.pins.items() if v)
            L.append(f"  {e.ref}  {e.label}  {pins}" + (f"   ({e.note})" if e.note else ""))
    return "\n".join(L) + "\n"


def logisim_rows(circuit, plan):
    """Rows (qty, Logisim part, note) of the circuit as the Logisim tab knows it, with the chips that replace each part."""
    chip_of = {}
    for ch in plan.chips:
        for c in ch.slots:
            if c is not None and c.origin: chip_of.setdefault(c.origin, set()).add(f"{ch.ref} ({ch.part})")
    groups = {}
    for comp in circuit.components:
        w = getattr(comp, "attrs", {}).get("width", 1); n = getattr(comp, "n", None)
        label = comp.type_name + (f" gate, {n} inputs" if n and n > 1 and comp.library == "Gates" else " gate" if comp.library == "Gates" else "") + (f", {w} bits" if w != 1 else "")
        g = groups.setdefault(label, [0, set()]); g[0] += 1
        g[1] |= chip_of.get(comp.id, set())
    rows = []
    if circuit.inputs: rows.append((len(circuit.inputs), "Input pin", ", ".join(p.name for p in circuit.inputs[:12]) + (" …" if len(circuit.inputs) > 12 else "")))
    for label, (n, chips) in sorted(groups.items()):
        rows.append((n, label, ("built with " + ", ".join(sorted(chips))) if chips else "no chip in the IC version (drawn as a block)"))
    if circuit.outputs: rows.append((len(circuit.outputs), "Output pin", ", ".join(p.name for p in circuit.outputs[:12]) + (" …" if len(circuit.outputs) > 12 else "")))
    return rows
