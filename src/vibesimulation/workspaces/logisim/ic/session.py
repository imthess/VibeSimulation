"""One IC session per circuit document: the chips, the user's rewiring, and the live chip simulation.

The IC window and the truth-table player both use it, so pressing play runs the gates *and* the chips side by side.
Rewiring done in the X-ray view lives only here: it never touches the circuit or its JSON.  When the circuit changes the
chips are worked out again and the rewiring is re-applied wherever the chip and the signal still exist.
"""
from vibesimulation.workspaces.logisim.ic import mapper, verify
from vibesimulation.workspaces.logisim.ic.mapper import GND, TIES, VCC

NONE = "(not connected)"


def apply_edits(plan, edits):
    """edits: {(ref, part, pin): signal name | "GND" | "VCC" | NONE}.  Returns the edits that no longer fit."""
    by_name = {}
    for net in plan.nets():
        if net not in TIES: by_name.setdefault(plan.name(net), net)
    dropped = []
    for (ref, part, pin), val in list(edits.items()):
        ch = plan.chip(ref)
        if ch is None or ch.part != part or pin not in ch.pins: dropped.append(((ref, part, pin), val)); continue
        if val == NONE: net = None
        elif val in TIES: net = val
        elif val in by_name: net = by_name[val]
        else: dropped.append(((ref, part, pin), val)); continue
        ch.pins[pin] = net; plan.edited.add((ref, pin))
    return dropped


class ICSession:
    def __init__(self, doc, reuse=False, adder="7483"):
        self.doc, self.reuse, self.adder = doc, reuse, adder
        self.edits = {}
        self.dropped = []
        self._plan = None; self._dirty = True; self.sim = None
        self.prev = {}; self.nets = {}; self.mismatch = []; self.checked = False
        self.listeners = []
        doc.subscribe(self._on_doc)

    # ---- the plan
    def _on_doc(self, kind):
        if kind in ("changed", "circuits"): self._dirty = True
        elif kind == "values" and self._plan is not None and not self._dirty: self.update()
        for f in list(self.listeners): f(kind)

    def plan(self):
        """The ICPlan (with the user's rewiring applied), or None while the circuit is not valid."""
        if self._dirty or self._plan is None: self.rebuild()
        return self._plan

    def rebuild(self):
        self._dirty = False; self._plan = None; self.sim = None; self.dropped = []
        d = self.doc
        if not d.valid or d.circuit is None: return
        p = mapper.plan(d.circuit, self.reuse, self.adder)
        self.dropped = apply_edits(p, self.edits)
        for k, _v in self.dropped: self.edits.pop(k, None)
        self._plan = p; self.sim = verify.ChipSim(p); self.prev = {}
        self.update()

    def options(self, reuse=None, adder=None):
        changed = (reuse is not None and reuse != self.reuse) or (adder is not None and adder != self.adder)
        if reuse is not None: self.reuse = reuse
        if adder is not None: self.adder = adder
        if changed: self.edits.clear(); self._dirty = True              # the chips (and their numbers) change: old rewiring means nothing

    # ---- rewiring (X-ray)
    def set_pin(self, ref, pin, value):
        p = self.plan()
        ch = p.chip(ref) if p else None
        if ch is None: return
        self.edits[(ref, ch.part, pin)] = value
        self._dirty = True; self.rebuild()
        for f in list(self.listeners): f("changed")

    def reset_pin(self, ref, pin):
        for k in [k for k in self.edits if k[0] == ref and k[2] == pin]: self.edits.pop(k)
        self._dirty = True; self.rebuild()
        for f in list(self.listeners): f("changed")

    def clear_edits(self):
        self.edits.clear(); self._dirty = True; self.rebuild()
        for f in list(self.listeners): f("changed")

    # ---- the live chip simulation
    def update(self):
        """Run the chips with the circuit's current inputs (and clock values) and compare every output."""
        p, d = self._plan, self.doc
        if p is None or self.sim is None: return
        try: v = d.values()
        except Exception: return                                             # noqa: BLE001
        ins, clocks = {}, {}
        for e in p.externals:
            if e.kind == "switch" and e.src: ins[e.pins["out"]] = ((v.get(e.src[0]) or 0) >> e.src[1]) & 1
            elif e.kind == "clock" and e.src and e.src[0] is not None:
                x = v.get(e.src[0]); clocks[e.pins["out"]] = 0 if x is None else x & 1
        if clocks: self.sim.settle({**ins, **{n: self.prev.get(n, 0) for n in clocks}, })   # the chips see the old clock level first
        got = self.sim.settle({**ins, **clocks})
        self.prev = dict(clocks)
        self.nets = got
        self.checked = not p.unmapped
        self.mismatch = []
        if not self.checked: return
        for e in p.externals:
            if e.kind != "led" or not e.src or e.src[0] is None: continue
            want = v.get(e.src[0]); have = verify._val(e.pins["anode"], got)
            if want is None or have is None: continue
            w = (want >> e.src[1]) & 1
            if w != have: self.mismatch.append((e.label, w, have))

    def value(self, net):
        """0 / 1 / None of a net right now (rails included)."""
        return verify._val(net, self.nets) if net is not None else None

    def status(self):
        """Short text for the truth-table player: ' · chips ✓' / ' · chips ✗ Y' / ''."""
        if self._plan is None or self._dirty:
            if self.plan() is None: return ""
        else: self.update()
        if not self.checked: return ""
        if self.mismatch: return " · chips ✗ " + ", ".join(m[0].replace("Output ", "") for m in self.mismatch[:3])
        return " · chips ✓"


def session_for(doc, cfg=None):
    s = getattr(doc, "_ic_session", None)
    if s is None:
        cfg = cfg or {}
        s = ICSession(doc)               # no options: sharing spare gates or switching adders changed the circuit, so the chips are always built one-to-one
        doc._ic_session = s
    return s
