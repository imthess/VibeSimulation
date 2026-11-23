"""Proof that the chips do what the drawn circuit does.

``ChipSim`` simulates a plan at chip level (every package behaves like its datasheet, driven only through the pin
numbers of the plan).  ``check`` runs the original circuit and the chip version side by side and compares every
output pin and LED.  Parts that have no 74xx chip ("blocks") cannot be simulated, so such plans are not checked.
"""
import itertools
import random

from vibesimulation.workspaces.logisim.core import sim as SIM
from vibesimulation.workspaces.logisim.ic import catalog as K
from vibesimulation.workspaces.logisim.ic.mapper import GND, VCC

SEQ = ("DFF", "JKFF", "DREG", "CNT4", "SIPO8")
_SEG7 = {0: "abcdef", 1: "bc", 2: "abdeg", 3: "abcdg", 4: "bcfg", 5: "acdfg", 6: "cdefg", 7: "abc", 8: "abcdefg", 9: "abcfg"}


def _val(net, v):
    return 1 if net == VCC else 0 if net == GND else v.get(net)


class ChipSim:
    def __init__(self, plan):
        self.plan, self.v = plan, {}
        self.units = []                       # (chip, unit index, unit, {role: pin(s)})
        for ch in plan.chips:
            cat = ch.chip
            for i in range(len(cat.units)):             # every unit, used or not: a rewired spare gate must act too
                self.units.append((ch, cat, cat.units[i], dict(cat.units[i].pins) | dict(cat.common)))
        self.state = {}
        for ch, cat, u, r in self.units: self.state[(ch.ref, cat.units.index(u))] = {"q": 0, "clk": None, "v": [0] * 8}

    # ---- pins <-> values
    def pin(self, ch, p, v): return _val(ch.pins.get(p), v)

    def get(self, ch, roles, role, v):
        p = roles[role]
        return [self.pin(ch, x, v) for x in p] if isinstance(p, tuple) else self.pin(ch, p, v)

    def put(self, ch, roles, role, value, v):
        p = roles.get(role)
        if p is None: return
        net = ch.pins.get(p)
        if net is not None and net not in (VCC, GND): v[net] = value

    # ---- combinational behaviour of one unit / package
    def comb(self, ch, cat, u, roles, st, v):
        f, g = u.func, lambda r: self.get(ch, roles, r, v)
        out = lambda r, x: self.put(ch, roles, r, x, v)
        if f in ("NOT", "BUF"):
            x = g("in")[0]
            out("out", None if x is None else (1 - x if f == "NOT" else x)); return
        if f[:-1].isalpha() and f[-1].isdigit() and f[:-1] in ("AND", "NAND", "OR", "NOR", "XOR", "XNOR"):
            xs = g("in")
            if any(x is None for x in xs): out("out", None); return
            kind = f[:-1]
            r = {"AND": all(xs), "NAND": not all(xs), "OR": any(xs), "NOR": not any(xs), "XOR": sum(xs) % 2 == 1, "XNOR": sum(xs) % 2 == 0}[kind]
            out("out", int(r)); return
        if f in ("MUX2", "MUX4", "MUX8"):
            n = {"MUX2": 1, "MUX4": 2, "MUX8": 3}[f]
            sel = [g("S")] if f == "MUX2" else [g(c) for c in ("A", "B", "C")[:n]]
            if g("G_n") == 1: out("Y", 0); return
            if None in sel or g("G_n") is None: out("Y", None); return
            out("Y", g(f"D{sum(b << i for i, b in enumerate(sel))}")); return
        if f in ("DEC2", "DEC3"):
            if f == "DEC2": sel = [g("A"), g("B")]; en = g("G_n") == 0
            else: sel = [g("A"), g("B"), g("C")]; en = g("G1") == 1 and g("G2A_n") == 0 and g("G2B_n") == 0
            for i in range(4 if f == "DEC2" else 8):
                out(f"Y{i}_n", None if None in sel else int(not (en and sum(b << k for k, b in enumerate(sel)) == i)))
            return
        if f == "BCD7":
            d = sum((g(c) or 0) << i for i, c in enumerate("ABCD"))
            on = _SEG7.get(d, "")
            for n in "abcdefg": out(f"{n}_n", 0 if n in on else 1)
            return
        if f == "ADD4":
            a = [g(f"A{i}") for i in range(1, 5)]; b = [g(f"B{i}") for i in range(1, 5)]; c = g("CIN")
            if None in a + b + [c]:
                for i in range(1, 5): out(f"S{i}", None)
                out("COUT", None); return
            t = sum(x << i for i, x in enumerate(a)) + sum(x << i for i, x in enumerate(b)) + c
            for i in range(4): out(f"S{i + 1}", (t >> i) & 1)
            out("COUT", t >> 4); return
        if f == "CMP4":
            a = sum((g(f"A{i}") or 0) << i for i in range(4)); b = sum((g(f"B{i}") or 0) << i for i in range(4))
            if a > b: r = (1, 0, 0)
            elif a < b: r = (0, 0, 1)
            else: r = (g("GTI"), g("EQI"), g("LTI"))
            out("GTO", r[0]); out("EQO", r[1]); out("LTO", r[2]); return
        # sequential parts: the outputs come from the remembered state
        q = st["q"]
        if f in ("DFF", "JKFF"):
            out("Q", q); out("QN", 1 - q)
        elif f == "DREG": out("Q", q)
        elif f == "CNT4":
            for i, L in enumerate("ABCD"): out(f"Q{L}", (q >> i) & 1)
            out("RCO", int(g("ENT") == 1 and q == 15))
        elif f == "SIPO8":
            for i, L in enumerate("ABCDEFGH"): out(f"Q{L}", st["v"][i])

    # ---- what a clock edge does
    def step(self, ch, cat, u, roles, st, v):
        f, g = u.func, lambda r: self.get(ch, roles, r, v)
        new = {"q": st["q"], "clk": g("CLK"), "v": list(st["v"])}
        old = st["clk"]
        rising = old == 0 and new["clk"] == 1
        falling = old == 1 and new["clk"] == 0
        if f == "DFF":
            if g("CLR_n") == 0: new["q"] = 0
            elif g("PRE_n") == 0: new["q"] = 1
            elif rising and g("D") is not None: new["q"] = g("D")
        elif f == "JKFF":
            j, k = g("J"), g("K")
            if g("CLR_n") == 0: new["q"] = 0
            elif g("PRE_n") == 0: new["q"] = 1
            elif falling and j is not None and k is not None:
                new["q"] = {(0, 0): st["q"], (0, 1): 0, (1, 0): 1, (1, 1): 1 - st["q"]}[(j, k)]
        elif f == "DREG":
            if ch.part == "74173":
                if g("CLR") == 1: new["q"] = 0
                elif rising and g("G1_n") == 0 and g("G2_n") == 0 and g("D") is not None: new["q"] = g("D")
            elif ch.part == "74377":
                if rising and g("E_n") == 0 and g("D") is not None: new["q"] = g("D")
            else:
                if g("CLR_n") == 0: new["q"] = 0
                elif rising and g("D") is not None: new["q"] = g("D")
        elif f == "CNT4":
            if g("CLR_n") == 0: new["q"] = 0
            elif rising:
                if g("LOAD_n") == 0: new["q"] = sum((g(L) or 0) << i for i, L in enumerate("ABCD"))
                elif g("ENP") == 1 and g("ENT") == 1: new["q"] = (st["q"] + 1) & 15
        elif f == "SIPO8":
            if g("CLR_n") == 0: new["v"] = [0] * 8
            elif rising: new["v"] = [int(g("A") == 1 and g("B") == 1)] + st["v"][:7]
        return new

    def settle(self, inputs, limit=200):
        """inputs: net -> 0/1 for every switch and clock.  Returns {net: value}."""
        for _ in range(limit):
            v = dict(inputs)
            for _p in range(len(self.units) + 3):               # relax the logic until nothing changes
                before = dict(v)
                for ch, cat, u, roles in self.units: self.comb(ch, cat, u, roles, self.state[(ch.ref, cat.units.index(u))], v)
                if v == before: break
            new = {key: (self.step(ch, cat, u, roles, self.state[key], v) if u.func in SEQ else self.state[key])
                   for ch, cat, u, roles in self.units for key in [(ch.ref, cat.units.index(u))]}
            if new == self.state: return v
            self.state = new
        return v


def check(circuit, plan, trials=60, seed=1, exhaustive_bits=10):
    """Compare chip version and circuit.  Returns (number of comparisons, list of mismatch descriptions) or None if not checkable."""
    if plan.unmapped: return None
    flat = circuit.flat(); rnd = random.Random(seed)
    names = [(p.name, p.width) for p in flat.inputs]
    seq = flat.has_seq() if hasattr(flat, "has_seq") else False
    sw = [e for e in plan.externals if e.kind == "switch"]
    ck = [e for e in plan.externals if e.kind == "clock"]
    leds = [e for e in plan.externals if e.kind == "led" and e.src and e.src[0] is not None]
    bad, n = [], 0
    if seq:
        combos = [{nm: rnd.randrange(1 << w) for nm, w in names} for _ in range(trials)]
    else:
        total = sum(w for _, w in names)
        combos = [dict(zip([x for x, _ in names], c)) for c in itertools.product(*[range(1 << w) for _, w in names])] if total <= exhaustive_bits else \
                 [{nm: rnd.randrange(1 << w) for nm, w in names} for _ in range(max(trials, 40))]
    st = SIM.fresh(flat) if seq else None
    cs = ChipSim(plan)
    prev = {e.pins["out"]: 0 for e in ck}                  # clocks start low, like Vibe's: the chips must see the low level before a rising edge
    for step, inv in enumerate(combos):
        if seq:
            v, osc = SIM.settle(flat, inv, st, step + 1)
        else: v = flat.simulate(inv)
        ins = {}
        for e in sw: nm, bit = e.src; ins[e.pins["out"]] = (inv.get(nm, 0) >> bit) & 1
        for e in ck:
            x = v.get(e.src[0]); ins[e.pins["out"]] = 0 if x is None else x & 1
        if ck: cs.settle({**ins, **prev})                  # inputs changed while the clock still has its old value
        got = cs.settle(ins)
        prev = {e.pins["out"]: ins[e.pins["out"]] for e in ck}
        for e in leds:
            nm, bit = e.src; want = v.get(nm); net = e.pins["anode"]
            have = _val(net, got)
            n += 1
            if want is None or have is None: continue
            if ((want >> bit) & 1) != have: bad.append(f"{e.label}: circuit {(want >> bit) & 1}, chips {have} for inputs {inv} (step {step})")
        if len(bad) > 5: break
    return n, bad
