"""Circuit -> chips.

``plan(circuit)`` goes through every part of a (flattened) circuit and replaces it with 74xx *cells* (one cell = one
unit of a chip: one NAND gate, one flip-flop, one 3-to-8 decoder ...).  The cells are then packed into packages
(four NAND gates share one 7400 ...) and every pin of every package is connected to a *net*.

Everything is worked out bit by bit: a 4-bit AND gate becomes four AND cells, a splitter or combiner is only wiring
(two names for the same net).  The result is an ``ICPlan``: chips, nets, external parts (switches, LEDs, displays),
warnings and the parts that have no 74xx equivalent in Logisim's library.
"""
from dataclasses import dataclass, field

from vibesimulation.workspaces.logisim.ic import catalog as K

VCC, GND = "VCC", "GND"
TIES = (VCC, GND)

# which chip implements which gate function (7400 -> NAND2, 7404 -> NOT ...)
GATE_PART = {}
for _c in K.CHIPS.values():
    for _u in _c.units:
        if _c.family == "Gates" or _u.func in ("NOT", "BUF"): GATE_PART.setdefault(_u.func, _c.part)
FINAL = {"AND": (2, 3, 4), "NAND": (2, 3, 4, 8), "OR": (2,), "NOR": (2, 3), "XOR": (2,), "XNOR": (2,)}     # sizes of the last gate
BASE = {"AND": ("AND", 4), "NAND": ("AND", 4), "OR": ("OR", 2), "NOR": ("OR", 2), "XOR": ("XOR", 2), "XNOR": ("XOR", 2)}   # first-level gate
INVERTING = {"NAND", "NOR", "XNOR"}
IDLE_HIGH = {"AND": VCC, "NAND": VCC}          # an unused input of these stays high; every other kind stays low

NO_74XX = {
    "RAM": "memory is not a 74xx chip (use a static RAM such as the 6116 or 62256 with the same address and data pins)",
    "ROM": "memory is not a 74xx chip (use an EEPROM such as the 28C16 or 28C64 with the same address and data pins)",
    "Multiplier": "Logisim's TTL library has no multiplier chip (the 74xx family has no 4-bit multiplier)",
    "Divider": "Logisim's TTL library has no divider chip",
    "Shifter": "Logisim's TTL library has no barrel shifter (a 74194 shifts one place per clock, which is not the same)",
    "BitFinder": "no 74xx chip in Logisim's library finds the first 0 or 1 of a bus",
    "BitAdder": "no 74xx chip in Logisim's library counts the 1 bits of a bus",
    "BITSELECTOR": "build it with a 74151 / 74153 data selector fed from the bus",
    "ENCODER": "the priority encoder (74148) is not in Logisim's TTL library",
}


@dataclass
class Cell:
    """One unit of one chip: ``roles`` says which net goes to which role of the unit (see catalog)."""
    part: str
    roles: dict
    origin: str = ""
    order: int = 0
    note: str = ""


@dataclass
class ChipInst:
    ref: str
    part: str
    slots: list                    # one Cell (or None = unused) per unit of the package
    common: dict                   # role -> net / tie, the pins all units share
    pins: dict = field(default_factory=dict)       # pin number -> net key / "VCC" / "GND" / None (not connected)
    order: int = 0

    @property
    def chip(self): return K.chip(self.part)

    def used(self): return sum(1 for s in self.slots if s)

    def free(self): return len(self.slots) - self.used()


@dataclass
class External:
    """A part that is not a 74xx chip: switch, LED, clock, display, or a block with no 74xx equivalent."""
    kind: str                      # switch, led, clock, display_cc, display_ca, block
    ref: str
    label: str
    pins: dict                     # pin name -> net key (or None)
    note: str = ""
    src: tuple = None              # (signal name, bit) of the circuit pin / part this stands for (used by the checker)
    outs: tuple = ()               # names of the pins that are outputs of the part (blocks and displays)


@dataclass
class ICPlan:
    chips: list
    externals: list
    names: dict                    # net key -> display name
    warnings: list
    unmapped: list                 # (component id, type, reason)
    options: dict
    shorts: list = field(default_factory=list)
    edited: set = field(default_factory=set)       # (chip ref, pin) the user rewired in the X-ray view

    # ---- nets
    def nets(self):
        """net key -> list of endpoints: ('chip', ref, pin) or ('ext', ref, pin name).  Rails included."""
        out = {}
        for ch in self.chips:
            for pin, net in sorted(ch.pins.items()):
                if net is not None: out.setdefault(net, []).append(("chip", ch.ref, pin))
        for e in self.externals:
            for pin, net in e.pins.items():
                if net is not None: out.setdefault(net, []).append(("ext", e.ref, pin))
        return out

    def chip(self, ref): return next((c for c in self.chips if c.ref == ref), None)

    def external(self, ref): return next((e for e in self.externals if e.ref == ref), None)

    def name(self, net): return net if net in TIES else self.names.get(net, net)

    def counts(self):
        """part -> number of packages."""
        out = {}
        for c in self.chips: out[c.part] = out.get(c.part, 0) + 1
        return out

    def gate_stats(self):
        """(units used, units available) over all packages."""
        used = sum(c.used() for c in self.chips); total = sum(len(c.slots) for c in self.chips)
        return used, total


# =====================================================================================================================
class NetBook:
    """Union-find over net names: a splitter, a combiner or a wire is just 'these two names are the same net'."""
    def __init__(self):
        self.p = {VCC: VCC, GND: GND}; self.keys = []; self.shorts = []

    def find(self, k):
        if k not in self.p: self.p[k] = k; self.keys.append(k)
        r = k
        while self.p[r] != r: r = self.p[r]
        while self.p[k] != r: self.p[k], k = r, self.p[k]
        return r

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb: return
        if ra in TIES and rb in TIES: self.shorts.append((a, b)); return
        if rb in TIES: ra, rb = rb, ra
        self.p[rb] = ra


def _bits_key(sig, width, i): return sig if width == 1 else f"{sig}[{i}]"


class Builder:
    def __init__(self, circuit, options):
        self.src = circuit
        self.c = circuit.flat()
        self.opt = options
        self.adder = options.get("adder", "7483")
        self.nb = NetBook()
        self.cells = []
        self.ext = []
        self.warn = []
        self.unmapped = []
        self._inv = {}
        self._n = 0
        self.origin = ""
        self.names = {}
        self.counter = {"SW": 0, "LED": 0, "DS": 0, "CLK": 0, "X": 0}

    # ---- nets
    def R(self, k):
        """Canonical net of a key (rails stay VCC / GND)."""
        return self.nb.find(k) if k is not None else None

    def new(self, hint):
        self._n += 1
        k = f"{hint}#{self._n}" if self.origin == "" else f"{self.origin}.{hint}#{self._n}"
        self.names[k] = k.split("#")[0]
        return self.nb.find(k)

    def bits(self, c, port):
        """Nets of an input or output pin of component c, lowest bit first.  Unconnected: the pin's default value / None."""
        p = c.port(port)
        sig = (c.ins if p.direction == "in" else c.outs).get(port)
        if sig is None:
            if p.direction == "in": return [VCC if (int(p.default or 0) >> i) & 1 else GND for i in range(p.width)]
            return [None] * p.width
        return [self.R(_bits_key(sig, p.width, i)) for i in range(p.width)]

    def one(self, c, port): return self.bits(c, port)[0]

    def inv(self, net):
        """The inverse of a net (one shared NOT cell per net); a rail gives the other rail."""
        if net == VCC: return GND
        if net == GND: return VCC
        if net not in self._inv: self._inv[net] = self.gate("NOT", [net], None, hint="n_" + self.names.get(net, str(net)).split("#")[0])
        return self._inv[net]

    # ---- cells
    def cell(self, part, **roles):
        cell = Cell(part, roles, self.origin, len(self.cells))
        self.cells.append(cell)
        return cell

    def gate_cell(self, func, ins, out):
        part = GATE_PART[func]
        return self.cell(part, **{"in": tuple(ins), "out": out})

    def gate(self, kind, ins, out, hint="y"):
        """One gate of this kind with these inputs (wider than any chip: a tree of gates).  Returns the output net."""
        out = out if out is not None else self.new(hint)
        ins = list(ins)
        if kind in ("NOT", "BUF"):
            self.gate_cell(kind, ins, out); return out
        if len(ins) == 1:                         # a one-input AND / OR / XOR is a wire, NAND / NOR / XNOR an inverter
            if kind in INVERTING: self.gate_cell("NOT", ins, out)
            else: self.nb.union(out, ins[0])
            return self.R(out)
        base, bmax = BASE[kind]; sizes = FINAL[kind]; nets = ins
        while len(nets) > max(sizes):
            chunk, rest = nets[:bmax], nets[bmax:]
            nets = rest + [self.gate(base, chunk, None, hint="t")]
        size = min(s for s in sizes if s >= len(nets))
        pad = [IDLE_HIGH.get(kind, GND)] * (size - len(nets))
        self.gate_cell(f"{kind}{size}", nets + pad, out)
        return out

    PREFIX = {"switch": "SW", "led": "LED", "clock": "CLK", "display_cc": "DS", "display_ca": "DS", "block": "X"}

    def external(self, kind, label, pins, note="", src=None, outs=()):
        pre = self.PREFIX[kind]
        self.counter[pre] += 1
        self.ext.append(External(kind, f"{pre}{self.counter[pre]}", label, pins, note, src, tuple(outs)))

    # ---- first pass: parts that are only wiring
    def wiring(self):
        for c in self.c.components:
            t = c.type_name
            if t == "Splitter":
                src = self.bits(c, "In"); k = 0
                for i, w in enumerate(c.parts()):
                    sig = c.outs.get(f"Out{i}")
                    for j in range(w):
                        if sig is not None: self.nb.union(_bits_key(sig, w, j), src[k + j])
                    k += w
            elif t == "Combiner":
                out = c.outs.get("Out")
                k = 0
                for i, w in enumerate(c.parts()):
                    src = self.bits(c, f"In{i}")
                    for j in range(w):
                        if out is not None: self.nb.union(_bits_key(out, c.bus_width(), k + j), src[j])
                    k += w
            elif t == "BitExtender":
                out = c.outs.get("Out")
                if out is None: continue
                iw, ow, fill = c.attrs["in_width"], c.attrs["out_width"], c.attrs["fill"]
                src = self.bits(c, "In")
                for j in range(ow):
                    key = _bits_key(out, ow, j)
                    if j < min(iw, ow): self.nb.union(key, src[j])
                    else: self.nb.union(key, {"zero": GND, "one": VCC, "sign": src[iw - 1]}[fill])
            elif t in ("Constant", "Ground", "Power"):
                out = c.outs.get("Out")
                if out is None: continue
                w = c.attrs["width"]
                val = c.attrs["value"] if t == "Constant" else (0 if t == "Ground" else (1 << w) - 1)
                for j in range(w): self.nb.union(_bits_key(out, w, j), VCC if (val >> j) & 1 else GND)

    # ---- second pass: every other part
    def parts(self):
        order = self.c.order() or self.c.components
        for c in order:
            t = c.type_name
            if t in ("Splitter", "Combiner", "BitExtender", "Constant", "Ground", "Power", "Probe"): continue
            self.origin = c.id
            h = getattr(self, "p_" + _ident(t), None)
            if h is None:
                self.block(c, NO_74XX.get(t, f"no matching chip in Logisim's TTL library for a '{t}'"))
                continue
            try: h(c)
            except _Unsupported as e: self.block(c, str(e))
        self.origin = ""

    def block(self, c, why):
        pins, outs = {}, []
        for p in c.active_ports():
            if (c.ins if p.direction == "in" else c.outs).get(p.name) is None: continue
            nets = self.bits(c, p.name)
            for i, n in enumerate(nets):
                nm = p.name if len(nets) == 1 else f"{p.name}[{i}]"
                pins[nm] = n
                if p.direction == "out": outs.append(nm)
        self.unmapped.append((c.id, c.type_name, why))
        self.external("block", f"{c.type_name} {c.id}", pins, why, outs=outs)

    # ---------------------------------------------------------------- gates
    def _gate_part(self, c, kind):
        w = c.attrs["width"]
        outs = self.bits(c, "Out")
        if all(o is None for o in outs): return
        ins = [self.bits(c, f"In{k + 1}") for k in range(c.n)]
        for i in range(w):
            if outs[i] is None: continue
            self.origin = f"{c.id}[{i}]" if w > 1 else c.id
            self.gate(kind, [x[i] for x in ins], outs[i], hint="y")

    def p_and(self, c): self._gate_part(c, "AND")
    def p_nand(self, c): self._gate_part(c, "NAND")
    def p_or(self, c): self._gate_part(c, "OR")
    def p_nor(self, c): self._gate_part(c, "NOR")
    def p_xor(self, c): self._gate_part(c, "XOR")
    def p_xnor(self, c): self._gate_part(c, "XNOR")
    def p_not(self, c): self._gate_part(c, "NOT")
    def p_buffer(self, c): self._gate_part(c, "BUF")

    def _parity(self, c, even):
        out = self.one(c, "Out")
        if out is None: return
        allbits = [b for k in range(c.n) for b in self.bits(c, f"In{k + 1}")]
        self.gate("XNOR" if even else "XOR", allbits, out)

    def p_oddparity(self, c): self._parity(c, False)
    def p_evenparity(self, c): self._parity(c, True)

    # ---------------------------------------------------------------- flip-flops
    def _clk(self, c, falling_chip):
        """Clock net for a chip that triggers on the rising (or falling) edge."""
        trig = c.attrs.get("trigger", "rising")
        net = self.one(c, "Clk")
        if trig in ("high", "low"):
            self.warn.append(f"{c.id}: a level-triggered ({trig}) {c.type_name} has no 74xx chip here; it was built edge-triggered instead.")
            trig = "rising" if trig == "high" else "falling"
        want_fall = trig == "falling"
        return net if want_fall == falling_chip else self.inv(net)

    def _ff_common(self, c):
        clr = self.inv(self.one(c, "Clr")); pre = self.inv(self.one(c, "Pre"))
        return clr, pre

    def p_d_flip_flop(self, c):
        clr, pre = self._ff_common(c)
        self.cell("7474", D=self.one(c, "D"), CLK=self._clk(c, False), PRE_n=pre, CLR_n=clr, Q=self.one(c, "Q"), QN=self.one(c, "Qn"))

    def p_t_flip_flop(self, c):
        clr, pre = self._ff_common(c); t = self.one(c, "T")
        self.cell("7476", J=t, K=t, CLK=self._clk(c, True), PRE_n=pre, CLR_n=clr, Q=self.one(c, "Q"), QN=self.one(c, "Qn"))

    def p_j_k_flip_flop(self, c):
        clr, pre = self._ff_common(c)
        self.cell("7476", J=self.one(c, "J"), K=self.one(c, "K"), CLK=self._clk(c, True), PRE_n=pre, CLR_n=clr, Q=self.one(c, "Q"), QN=self.one(c, "Qn"))

    def p_s_r_flip_flop(self, c):
        clr, pre = self._ff_common(c)
        self.warn.append(f"{c.id}: the S-R flip-flop is built from a 7476 J-K flip-flop (J=S, K=R). With S=R=1 the 7476 toggles, while the S-R flip-flop keeps its value.")
        self.cell("7476", J=self.one(c, "S"), K=self.one(c, "R"), CLK=self._clk(c, True), PRE_n=pre, CLR_n=clr, Q=self.one(c, "Q"), QN=self.one(c, "Qn"))

    # ---------------------------------------------------------------- registers, counters, shift registers
    def p_register(self, c):
        w = c.attrs["width"]; d = self.bits(c, "D"); q = self.bits(c, "Q")
        clk = self._clk(c, False); en_net = self.one(c, "En"); clr = self.one(c, "Clr")
        has_en, has_clr = en_net != VCC, clr != GND
        if has_clr:      # 74173: clear is active HIGH, enable (active low) is G1, G2 stays low, outputs on (M, N low)
            g1 = self.inv(en_net)
            for i in range(w):
                self.origin = f"{c.id}[{i}]"
                self.cell("74173", D=d[i], Q=q[i], CLK=clk, CLR=clr, G1_n=g1, G2_n=GND, M_n=GND, N_n=GND)
        elif has_en:     # 74377: octal D register with an active-low clock enable
            e = self.inv(en_net)
            for i in range(w):
                self.origin = f"{c.id}[{i}]"
                self.cell("74377", D=d[i], Q=q[i], CLK=clk, E_n=e)
        else:            # 74175 (4 bits) or 74273 (8 bits): the clear input is not used, so it stays high
            rest = w % 8
            for i in range(w):
                self.origin = f"{c.id}[{i}]"
                part = "74273" if (i < w - rest or rest > 4) else "74175"
                self.cell(part, D=d[i], Q=q[i], CLK=clk, CLR_n=VCC)

    def p_counter(self, c):
        a = c.attrs; w = a["width"]
        if w % 4: raise _Unsupported(f"the 74161 counts 4 bits at a time; a {w}-bit counter would need extra logic to wrap at {1 << w}")
        if a["max"] not in (0, (1 << w) - 1) or a["ongoal"] != "wrap":
            raise _Unsupported("only a counter that wraps around at its largest value maps onto the 74161")
        if c.ins.get("UD") is not None:
            raise _Unsupported("an up/down counter needs a 74193 (separate count-up and count-down clocks), which this view does not build yet")
        clk = self._clk(c, False); en = self.one(c, "En"); ld = self.inv(self.one(c, "Ld")); clr = self.inv(self.one(c, "Clr"))
        d = self.bits(c, "D"); q = self.bits(c, "Q"); carry = self.one(c, "Carry")
        ent = en
        for k in range(w // 4):
            self.origin = f"{c.id}[{4 * k + 3}:{4 * k}]" if w > 4 else c.id
            last = k == w // 4 - 1
            rco = carry if last else self.new("rco")
            self.cell("74161", CLR_n=clr, CLK=clk, A=d[4 * k], B=d[4 * k + 1], C=d[4 * k + 2], D=d[4 * k + 3], ENP=en, LOAD_n=ld, ENT=ent,
                      QA=q[4 * k], QB=q[4 * k + 1], QC=q[4 * k + 2], QD=q[4 * k + 3], RCO=rco)
            ent = rco

    def p_shift_register(self, c):
        a = c.attrs; n, w = a["length"], a["width"]
        if w != 1: raise _Unsupported("only 1-bit shift registers map onto the 74164")
        if c.ins.get("Ld") is not None or any(c.ins.get(f"D{i}") is not None for i in range(n)):
            raise _Unsupported("parallel load needs a 74165 / 74194, which this view does not build yet")
        if c.ins.get("Sh") is not None: raise _Unsupported("a Shift-enable pin would have to gate the clock (a 74194 does this properly)")
        clk = self._clk(c, False); clr = self.inv(self.one(c, "Clr")); d = self.one(c, "In")
        out = self.one(c, "Out")
        # Vibe: Q0 is the newest stage (next to In), Out the oldest = the last stage.  A 74164 chain: QA is the newest stage.
        stage = [self.one(c, f"Q{i}") if a["parallel"] and c.outs.get(f"Q{i}") is not None else None for i in range(n)]
        if out is not None:
            if stage[n - 1] is None: stage[n - 1] = out
            else: self.nb.union(out, stage[n - 1])
        for s_ in range(7, n - 1, 8):
            if stage[s_] is None: stage[s_] = self.new("sr")
        for k in range((n + 7) // 8):
            self.origin = f"{c.id}[{k}]"
            roles = {f"Q{L}": (stage[8 * k + j] if 8 * k + j < n else None) for j, L in enumerate("ABCDEFGH")}
            self.cell("74164", A=d, B=d, CLK=clk, CLR_n=clr, **roles)
            d = stage[8 * k + 7] if 8 * k + 7 < n else None

    # ---------------------------------------------------------------- plexers
    def _mux_one(self, ins, sels, en, out):
        s = len(sels)
        if s == 0: self.nb.union(out, ins[0]); return
        g = self.inv(en) if en is not None else GND
        if s == 1: self.cell("74157", S=sels[0], G_n=g, D0=ins[0], D1=ins[1], Y=out)
        elif s == 2: self.cell("74153", A=sels[0], B=sels[1], G_n=g, D0=ins[0], D1=ins[1], D2=ins[2], D3=ins[3], Y=out)
        elif s == 3: self.cell("74151", A=sels[0], B=sels[1], C=sels[2], G_n=g, **{f"D{i}": ins[i] for i in range(8)}, Y=out)
        else:
            first = []
            for k in range(0, len(ins), 8):
                y = self.new("m8"); self._mux_one(ins[k:k + 8], sels[:3], None, y); first.append(y)
            self._mux_one(first, sels[3:], en, out)

    def p_mux(self, c):
        s, w = c.attrs["select"], c.attrs["width"]
        ins = [self.bits(c, f"In{i}") for i in range(1 << s)]; sel = self.bits(c, "Sel")
        en = self.one(c, "En") if c.ins.get("En") is not None else None
        out = self.bits(c, "Out")
        for i in range(w):
            if out[i] is None: continue
            self.origin = f"{c.id}[{i}]" if w > 1 else c.id
            self._mux_one([x[i] for x in ins], sel, en, out[i])

    def _decode(self, sel, en, outs):
        """outs[i] = 1 when sel == i (and en); outs may hold None for unused outputs."""
        s = len(sel)
        if s > 4: raise _Unsupported("a decoder with more than 4 select bits needs more than two 74138 chips; not built yet")
        if s == 1:
            if outs[0] is not None:
                if en == VCC: self.gate("NOT", [sel[0]], outs[0])
                else: self.gate("AND", [self.inv(sel[0]), en], outs[0])
            if outs[1] is not None:
                if en == VCC: self.nb.union(outs[1], sel[0])
                else: self.gate("AND", [sel[0], en], outs[1])
        elif s == 2:
            ys = [self.new(f"Y{i}_n") if outs[i] is not None else None for i in range(4)]
            self.cell("74139", G_n=self.inv(en), A=sel[0], B=sel[1], **{f"Y{i}_n": ys[i] for i in range(4)})
            for i in range(4):
                if ys[i] is not None: self.gate("NOT", [ys[i]], outs[i])
        elif s == 3:
            self._dec3(sel[:3], en, GND, outs)
        else:       # 4 bits: two 74138, the fourth select bit picks one of them through the enable pins
            self._dec3(sel[:3], en, sel[3], outs[:8])
            self._dec3(sel[:3], sel[3] if en == VCC else self.gate("AND", [en, sel[3]], None), GND, outs[8:])

    def _dec3(self, sel, g1, g2a_n, outs):
        ys = [self.new(f"Y{i}_n") if outs[i] is not None else None for i in range(8)]
        self.cell("74138", A=sel[0], B=sel[1], C=sel[2], G1=g1, G2A_n=g2a_n, G2B_n=GND, **{f"Y{i}_n": ys[i] for i in range(8)})
        for i in range(8):
            if ys[i] is not None: self.gate("NOT", [ys[i]], outs[i])

    def p_decoder(self, c):
        n = 1 << c.attrs["select"]
        outs = [self.one(c, f"Out{i}") for i in range(n)]
        if all(o is None for o in outs): return
        self._decode(self.bits(c, "Sel"), self.one(c, "En"), outs)

    def p_demux(self, c):
        s, w = c.attrs["select"], c.attrs["width"]; n = 1 << s
        data = self.bits(c, "In"); en = self.one(c, "En"); sel = self.bits(c, "Sel")
        outs = [self.bits(c, f"Out{i}") for i in range(n)]
        for b in range(w):
            if all(o[b] is None for o in outs): continue
            self.origin = f"{c.id}[{b}]" if w > 1 else c.id
            e = data[b] if en == VCC else self.gate("AND", [data[b], en], None)
            self._decode(sel, e, [o[b] for o in outs])

    # ---------------------------------------------------------------- arithmetic
    def _add_chain(self, a, b, cin, sums, cout):
        """a, b: bit nets (lowest first); sums: output nets or None; cout: net or None.  A chain of 74283 chips."""
        w = len(a); carry = cin; base = self.origin
        for k in range((w + 3) // 4):
            lo = 4 * k; m = min(4, w - lo); last = lo + 4 >= w
            r = {}
            for j in range(4):
                r[f"A{j + 1}"] = a[lo + j] if j < m else GND
                r[f"B{j + 1}"] = b[lo + j] if j < m else GND
                r[f"S{j + 1}"] = sums[lo + j] if j < m else None
            if last:
                if m < 4: r[f"S{m + 1}"] = cout; r["COUT"] = None       # the carry shows up on the first padded sum bit
                else: r["COUT"] = cout
            else: r["COUT"] = self.new("c")
            self.origin = f"{base}[{lo + m - 1}:{lo}]" if w > 4 else base
            self.cell(self.adder, CIN=carry, **r)
            carry = r["COUT"]
        self.origin = base

    def p_adder(self, c):
        self._add_chain(self.bits(c, "A"), self.bits(c, "B"), self.one(c, "Cin"), self.bits(c, "Sum"), self.one(c, "Cout"))

    def p_subtractor(self, c):
        a, b = self.bits(c, "A"), self.bits(c, "B"); w = len(a)
        nb_ = [self.inv(x) for x in b]
        cin = self.inv(self.one(c, "Bin")); bout = self.one(c, "Bout")
        cout = self.new("cout") if bout is not None else None
        self._add_chain(a, nb_, cin, self.bits(c, "Diff"), cout)
        if bout is not None: self.gate("NOT", [cout], bout)

    def p_negator(self, c):
        a = self.bits(c, "In")
        self._add_chain([self.inv(x) for x in a], [GND] * len(a), VCC, self.bits(c, "Out"), None)

    def p_comparator(self, c):
        a, b = list(self.bits(c, "A")), list(self.bits(c, "B")); w = len(a)
        if c.attrs["mode"] == "signed":          # two's complement order = unsigned order with the top bit flipped
            a[-1], b[-1] = self.inv(a[-1]), self.inv(b[-1])
        gt, eq, lt = self.one(c, "GT"), self.one(c, "EQ"), self.one(c, "LT")
        cas = {"GTI": GND, "EQI": VCC, "LTI": GND}
        for k in range((w + 3) // 4):
            lo = 4 * k; last = lo + 4 >= w
            r = {}
            for j in range(4):
                r[f"A{j}"] = a[lo + j] if lo + j < w else GND
                r[f"B{j}"] = b[lo + j] if lo + j < w else GND
            outs = {"GTO": gt, "EQO": eq, "LTO": lt} if last else {"GTO": self.new("gt"), "EQO": self.new("eq"), "LTO": self.new("lt")}
            self.origin = f"{c.id}[{lo + min(4, w - lo) - 1}:{lo}]" if w > 4 else c.id
            self.cell("7485", **r, **cas, **outs)
            cas = {"GTI": outs["GTO"], "EQI": outs["EQO"], "LTI": outs["LTO"]}

    # ---------------------------------------------------------------- displays, LEDs, clock
    def p_led(self, c): self.external("led", f"LED {c.id}", {"anode": self.one(c, "In")}, src=(c.ins.get("In"), 0))

    def p_clock(self, c): self.external("clock", f"Clock {c.id}", {"out": self.one(c, "Out")}, note=f"{c.attrs['low']} tick(s) low, {c.attrs['high']} tick(s) high", src=(c.outs.get("Out"), 0))

    def p_sevenseg(self, c):
        pins = {n.lower(): self.one(c, n) if c.ins.get(n) is not None else None for n in "ABCDEFG"}
        pins["dp"] = self.one(c, "DP") if c.ins.get("DP") is not None else None
        self.external("display_cc", f"7-segment {c.id}", pins, note="common cathode (the common pin goes to GND)")

    def p_hexdisplay(self, c):
        d = self.bits(c, "In"); seg = {n: self.new(f"seg_{n}") for n in "abcdefg"}
        self.cell("7447", A=d[0], B=d[1], C=d[2], D=d[3], LT_n=VCC, BI_n=VCC, RBI_n=VCC, **{f"{n}_n": seg[n] for n in "abcdefg"})
        pins = dict(seg)
        pins["dp"] = self.inv(self.one(c, "DP")) if c.ins.get("DP") is not None else None
        self.external("display_ca", f"7-segment {c.id}", pins, note="common anode (the common pin goes to VCC)")
        self.warn.append(f"{c.id}: the 7447 shows 0-9 as digits; the values 10-15 light odd patterns instead of A-F.")

    # ---------------------------------------------------------------- the circuit's own pins
    def pins(self):
        for p in self.c.inputs:
            for i in range(p.width):
                k = _bits_key(p.name, p.width, i)
                self.external("switch", f"Input {k}", {"out": self.R(k)}, src=(p.name, i))
        w = self.c.signals()
        for p in self.c.outputs:
            if p.floating: continue
            wd = w.get(p.name, p.width)
            for i in range(wd):
                self.external("led", f"Output {_bits_key(p.name, wd, i)}", {"anode": self.R(_bits_key(p.name, wd, i))}, src=(p.name, i))


class _Unsupported(Exception):
    pass


def _ident(t):
    return "".join(ch if ch.isalnum() else "_" for ch in t.lower()).strip("_")


# =====================================================================================================================
def idle(part, role):
    """What an unused input of a package is tied to: active-low controls stay high, everything else low."""
    return VCC if role.endswith("_n") else GND


def build_chip(ref, part, slots, order):
    ch = K.chip(part)
    cells = [s for s in slots if s]
    common = {}
    for role, _pin in ch.common:
        common[role] = cells[0].roles.get(role, idle(part, role)) if cells else idle(part, role)
    inst = ChipInst(ref, part, list(slots), common, {}, order)
    pins = {n: None for n in range(1, ch.pins + 1)}
    pins[ch.vcc], pins[ch.gnd] = VCC, GND
    for role, pin in ch.common: pins[pin] = common[role]
    for i, unit in enumerate(ch.units):
        cell = slots[i] if i < len(slots) else None
        for role, pin in unit.pins:
            outpin = ch.pin_kind(pin[0] if isinstance(pin, tuple) else pin) in ("out", "io")
            val = cell.roles.get(role) if cell else None
            if isinstance(pin, tuple):
                vals = list(val) if val is not None else [idle(part, role)] * len(pin)
                for p_, v_ in zip(pin, vals): pins[p_] = v_
            elif outpin: pins[pin] = val
            else: pins[pin] = val if val is not None else idle(part, role)
    inst.pins = pins
    return inst


def _share_key(ch, cell):
    return tuple(cell.roles.get(r, idle(ch.part, r)) for r, _ in ch.common)


def pack(cells):
    groups = {}
    for cell in cells:
        ch = K.chip(cell.part)
        groups.setdefault((cell.part, _share_key(ch, cell)), []).append(cell)
    chips = []
    for (part, _key), cs in groups.items():
        n = len(K.chip(part).units)
        for i in range(0, len(cs), n):
            sl = cs[i:i + n]
            chips.append(build_chip("?", part, sl + [None] * (n - len(sl)), min(c.order for c in sl)))
    chips.sort(key=lambda c: c.order)
    return chips


# ---- optional: let a spare NAND / NOR / XOR gate act as an inverter instead of buying another 7404
_NOT_VIA = {"7400": lambda x: (x, x), "7402": lambda x: (x, x), "7410": lambda x: (x, x, x), "7427": lambda x: (x, x, x),
            "7420": lambda x: (x, x, x, x), "7486": lambda x: (x, VCC), "74266": lambda x: (x, GND)}


def reuse_spare_gates(chips):
    by_free = lambda: [(ch, i) for ch in chips if ch.part in _NOT_VIA for i, s in enumerate(ch.slots) if s is None]
    for ch in sorted([c for c in chips if c.part == "7404"], key=lambda c: c.used()):
        cells = [s for s in ch.slots if s]
        spots = by_free()
        if len(spots) < len(cells): continue
        for cell, (dest, i) in zip(cells, spots):
            x = cell.roles["in"][0]
            dest.slots[i] = Cell(dest.part, {"in": _NOT_VIA[dest.part](x), "out": cell.roles["out"]}, cell.origin, cell.order,
                                 note=f"inverter made from a spare {K.chip(dest.part).units[0].func} gate")
        chips.remove(ch)
    return [build_chip("?", c.part, c.slots, c.order) if c.part in _NOT_VIA else c for c in chips]


# =====================================================================================================================
def plan(circuit, reuse_spare=False, adder="7483"):
    """Everything the IC view shows, for a circuit (a Vibe ``Circuit``; subcircuits are expanded).
    adder: "7483" (the pinout of the lab sheets) or "74283" (the chip Logisim has)."""
    b = Builder(circuit, {"reuse_spare": reuse_spare, "adder": adder})
    b.wiring(); b.parts(); b.pins()
    fin = lambda n: n if n is None or n in TIES else b.nb.find(n)       # later merges (a wire) may have renamed a net
    for cell in b.cells:
        cell.roles = {r: (tuple(fin(x) for x in v) if isinstance(v, tuple) else fin(v)) for r, v in cell.roles.items()}
    for e in b.ext: e.pins = {p: fin(n) for p, n in e.pins.items()}
    chips = pack(b.cells)
    if reuse_spare: chips = reuse_spare_gates(chips)
    chips.sort(key=lambda c: c.order)
    for i, ch in enumerate(chips, 1): ch.ref = f"U{i}"
    return ICPlan(chips, b.ext, _names(b, chips), b.warn, b.unmapped, {"reuse_spare": reuse_spare, "adder": adder}, b.nb.shorts)


def _names(b, chips):
    """Readable net names: a circuit input / output name wins over the generated ones; clashes get a number."""
    used = {n for ch in chips for n in ch.pins.values() if n} | {n for e in b.ext for n in e.pins.values() if n}
    roots = {}
    for k in list(b.nb.p): roots.setdefault(b.nb.find(k), []).append(k)
    pri = {p.name for p in b.c.inputs} | {p.name for p in b.c.outputs}
    names = {}
    for r, keys in roots.items():
        if r in TIES or r not in used: continue
        pick = sorted(keys, key=lambda k: (k.split("[")[0] not in pri, "#" in k, "/" in k, len(k), k))[0]
        names[r] = pick.split("#")[0]
    seen = {}
    for k in sorted(names): seen.setdefault(names[k], []).append(k)
    for nm, ks in seen.items():
        if len(ks) > 1:
            for j, k in enumerate(ks): names[k] = f"{nm}_{j + 1}"
    return names
