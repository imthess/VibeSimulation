"""Analog parts. Each class knows its JSON, how it stamps the equations, how it is drawn and how SPICE writes it."""
import math
from abc import ABC, abstractmethod

from ..core.render import ACCENT, FILL, LABEL, MUTED, OUTLINE
from .units import fmt_si, parse_value

VT = 0.025852


class AnalogPart(ABC):
    type_name = ""
    aliases = ()
    letter = ""            # SPICE letter
    idp = ""               # prefix of ids the editor hands out (defaults to the letter)
    unit = ""
    default = None         # default value (None = no value)
    summary = ""

    extras = {}            # more settings written in the JSON: name -> default (e.g. a switch's "state", a Zener's "vz")
    nonlinear = False      # needs Newton iteration
    dc_path = True         # gives a DC path between its two nodes (capacitors, current sources, meters with no current do not)
    vmax = None            # forward voltage above which the part would be destroyed (the solver reports it)

    def __init__(self, cid, nodes, value=None, **extra):
        self.id, self.nodes = cid, list(nodes)
        self.value = value if value is not None else self.default
        self.pos = None        # (dx, dy): how far the user dragged the part away from its automatic place
        self.extra = {k: extra.get(k, d) for k, d in self.extras.items()}

    nterm = 2              # number of terminals (nodes); transistors have 3, a transformer 4
    nbranch = 1            # current unknowns of a branch part
    terminals = ()         # names of the terminals, in order (3+ terminals)

    def dc_links(self):
        """Pairs of nodes this part joins at DC (decides whether a net has a DC path to ground)."""
        return [(self.nodes[0], self.nodes[1])] if self.conducts() else []

    def caps(self):
        """Fixed capacitances inside the part: [(node a, node b, farads)] (used by the AC and transient analyses)."""
        return []

    def info(self, volts, bcur=None):
        """Extra lines for the results (operating region, gm ...): [(label, value text)]."""
        return []

    def result(self, volts, bcur):
        """(voltage across / between the first two terminals, current into the first terminal, power absorbed)."""
        va, vb = volts[self.nodes[0]], volts[self.nodes[1]]; i = self.res_current(volts, bcur)
        return (va - vb, i, (va - vb) * i)

    def spice_lines(self, node):
        """SPICE text; node() maps a net name to the netlist's name."""
        return [self.spice(node(self.nodes[0]), node(self.nodes[1]))]

    def clone(self):
        q = type(self)(self.id, list(self.nodes), self.value, **self.extra); q.pos = tuple(self.pos) if self.pos else None; return q

    def conducts(self):
        return self.dc_path

    def caption(self, digits=4):
        """Text under the symbol."""
        return "" if self.value is None else fmt_si(self.number(), self.unit, digits)

    def control_nodes(self):
        return []

    def res_current(self, volts, bcur):
        """Current a -> b through the part for the solved node voltages (and branch currents by part id)."""
        va, vb = volts[self.nodes[0]], volts[self.nodes[1]]
        return self.current(va, vb, bcur.get(self.id, 0.0))

    def number(self):
        return parse_value(self.value)

    def label(self, digits=4):
        return self.id if self.value is None else f"{self.id}  {fmt_si(self.number(), self.unit, digits)}"

    def check(self):
        errs = []
        if len(self.nodes) != self.nterm or not all(isinstance(n, (str, int)) and str(n).strip() for n in self.nodes):
            ex = ", ".join(f'"n{i + 1}"' for i in range(self.nterm - 1)) + ', "0"'
            errs.append(f"{self.id}: 'nodes' must list exactly {self.nterm} node names" + (f" ({', '.join(self.terminals)})" if self.terminals else "") + f", e.g. [{ex}]")
        if self.default is not None:
            try:
                v = self.number()
                if self.positive and v <= 0: errs.append(f"{self.id}: value must be greater than 0")
            except ValueError as e: errs.append(f"{self.id}: {e}")
        return errs

    positive = True

    def to_dict(self, layout=False):
        d = {"id": self.id, "type": self.type_name}
        if self.value is not None: d["value"] = self.value
        for k, dv in self.extras.items():
            if self.extra.get(k) != dv: d[k] = self.extra[k]
        d["nodes"] = list(self.nodes)
        if layout and self.pos and tuple(self.pos) != (0, 0): d["pos"] = [int(self.pos[0]), int(self.pos[1])]
        return d

    # ---- solver (Template Method hooks)
    branch = False         # needs an extra unknown (current through the part)

    @abstractmethod
    def stamp(self, s, volts):
        """Add this part's equations to the system s (see solver.System)."""

    def current(self, va, vb, branch_i):
        return 0.0

    # ---- drawing: horizontal, centre (cx,cy), terminals at cx-60 / cx+60
    @abstractmethod
    def draw(self, r, cx, cy, tags): ...

    def spice(self, a, b):
        return f"{self.spice_name()} {a} {b} {self.number():g}"

    def spice_name(self):
        return self.id if self.id[:1].upper() == self.letter else self.letter + self.id


def wire(r, cx, cy, x0, x1, tags):
    r.line([(cx - 60, cy), (cx + x0, cy)], 2, OUTLINE, tags); r.line([(cx + x1, cy), (cx + 60, cy)], 2, OUTLINE, tags)


class Resistor(AnalogPart):
    extras = {"tol": "0", "tc1": "0", "tc2": "0"}     # tolerance (Monte Carlo) and temperature coefficients
    type_name, aliases, letter, unit, default = "Resistor", ("R",), "R", "Ω", "1k"
    summary = "Resistor: current = voltage / resistance."

    def stamp(self, s, volts):
        s.conductance(self.nodes[0], self.nodes[1], 1.0 / self.number())

    def current(self, va, vb, i): return (va - vb) / self.number()

    def draw(self, r, cx, cy, tags):
        wire(r, cx, cy, -30, 30, tags)
        pts = [(cx - 30, cy)] + [(cx - 24 + 8 * i, cy + (-9 if i % 2 == 0 else 9)) for i in range(7)] + [(cx + 30, cy)]
        r.line(pts, 2, OUTLINE, tags)


class Capacitor(AnalogPart):
    extras = {"tol": "0", "tc1": "0", "tc2": "0"}     # tolerance (Monte Carlo) and temperature coefficients
    type_name, aliases, letter, unit, default = "Capacitor", ("C",), "C", "F", "1u"
    summary = "Capacitor (DC: open circuit, no current)."
    dc_path = False

    def stamp(self, s, volts): pass

    def draw(self, r, cx, cy, tags):
        wire(r, cx, cy, -5, 5, tags)
        r.line([(cx - 5, cy - 16), (cx - 5, cy + 16)], 3, OUTLINE, tags); r.line([(cx + 5, cy - 16), (cx + 5, cy + 16)], 3, OUTLINE, tags)


class Inductor(AnalogPart):
    extras = {"tol": "0", "tc1": "0", "tc2": "0"}     # tolerance (Monte Carlo) and temperature coefficients
    type_name, aliases, letter, unit, default = "Inductor", ("L",), "L", "H", "1m"
    summary = "Inductor (DC: short circuit)."
    branch = True

    def stamp(self, s, volts): s.branch_voltage(self, 0.0)

    def current(self, va, vb, i): return i

    def draw(self, r, cx, cy, tags):
        wire(r, cx, cy, -32, 32, tags)
        pts = []
        for k in range(4):
            for t in range(0, 11):
                a = math.pi * t / 10
                pts.append((cx - 32 + 16 * k + 8 - 8 * math.cos(a), cy - 9 * math.sin(a)))
        r.line(pts, 2, OUTLINE, tags)


class Waveform:
    """The time-varying part shared by both kinds of source: value (DC level) + ac * wave(2π f t + phase°).
    The same numbers are the phasor of the AC analysis: magnitude 'ac', angle 'phase' (sine-referenced, so only phase differences matter)."""
    WAVES = ("sine", "square", "triangle", "sawtooth")
    extras = {"ac": "0", "phase": "0", "freq": "1k", "wave": "sine", "duty": "50"}

    def ac_amp(self): return parse_value(self.extra["ac"])
    def ac_phase(self): return parse_value(self.extra["phase"])
    def freq(self): return parse_value(self.extra["freq"])
    def is_ac(self): return abs(self.ac_amp()) > 0

    def check_wave(self):
        errs = []
        for k in ("ac", "phase", "freq"):
            try: parse_value(self.extra[k])
            except ValueError as e: errs.append(f"{self.id}: '{k}': {e}")
        if not errs and self.freq() <= 0 and self.is_ac(): errs.append(f"{self.id}: freq must be greater than 0")
        if str(self.extra["wave"]).lower() not in self.WAVES: errs.append(f"{self.id}: wave must be one of {', '.join(self.WAVES)}")
        try:
            if not 0 < parse_value(self.extra["duty"]) < 100: errs.append(f"{self.id}: duty must be between 0 and 100 (percent)")
        except ValueError as e: errs.append(f"{self.id}: 'duty': {e}")
        return errs

    def duty(self): return min(0.999, max(0.001, parse_value(self.extra["duty"]) / 100.0))

    def at(self, t):
        """Value at time t seconds (DC level plus the waveform)."""
        v = self.number()
        if not self.is_ac(): return v
        th = 2 * math.pi * self.freq() * t + math.radians(self.ac_phase()); w = str(self.extra["wave"]).lower()
        if w == "square": x = (1.0 if math.sin(th) >= 0 else -1.0) if self.duty() == 0.5 else (1.0 if (th / (2 * math.pi)) % 1.0 < self.duty() else -1.0)
        elif w == "sawtooth": x = 2.0 * (((th / (2 * math.pi)) + 0.5) % 1.0) - 1.0
        elif w == "triangle": x = 2 / math.pi * math.asin(max(-1.0, min(1.0, math.sin(th))))
        else: x = math.sin(th)
        return v + self.ac_amp() * x

    def phasor(self):
        return self.ac_amp() * complex(math.cos(math.radians(self.ac_phase())), math.sin(math.radians(self.ac_phase())))

    def caption(self, digits=4):
        base = "" if parse_value(self.value) == 0 and self.is_ac() else fmt_si(self.number(), self.unit, digits)
        if not self.is_ac(): return base
        ph = self.ac_phase(); w = str(self.extra["wave"]).lower()
        ac = f"{fmt_si(self.ac_amp(), self.unit, digits)} {'' if w == 'sine' else w + ' '}@ {fmt_si(self.freq(), 'Hz', digits)}" + (f" ∠{ph:g}°" if ph else "")
        return f"{base} + {ac}" if base else ac

    def spice_tail(self):
        """'DC 5 AC 2 30 SIN(5 2 1k 0 0 30)' (square / triangle become PULSE of the same shape)."""
        t = f"DC {self.number():g}"
        if not self.is_ac(): return t
        a, f, ph, off = self.ac_amp(), self.freq(), self.ac_phase(), self.number()
        w = str(self.extra["wave"]).lower(); per = 1 / f; td = (-ph / 360.0) * per if ph else 0.0; tdt = ((-ph - 90) / 360.0) * per
        if w == "sine": return t + f" AC {a:g} {ph:g} SIN({off:g} {a:g} {f:g} 0 0 {ph:g})"
        if w == "square": return t + f" AC {a:g} {ph:g} PULSE({off - a:g} {off + a:g} {td % per:g} 1n 1n {per * self.duty():g} {per:g})"
        if w == "sawtooth": return t + f" AC {a:g} {ph:g} PULSE({off - a:g} {off + a:g} {(td + per / 2) % per:g} {per * 0.999:g} {per * 0.001:g} 1n {per:g})"
        return t + f" AC {a:g} {ph:g} PULSE({off - a:g} {off + a:g} {tdt % per:g} {per / 2:g} {per / 2:g} 1n {per:g})"


class VoltageSource(Waveform, AnalogPart):
    type_name, aliases, letter, unit, default = "VoltageSource", ("V", "Battery", "DCVoltage"), "V", "V", "5"
    summary = "Voltage source: DC level 'value' plus an optional AC part: 'ac' (peak), 'freq', 'phase' (degrees), 'wave' (sine / square / triangle). nodes = [plus, minus]."
    branch, positive = True, False

    def check(self): return AnalogPart.check(self) + self.check_wave()
    def stamp(self, s, volts): s.branch_voltage(self, (self.number() if s.t is None else self.at(s.t)) * s.scale)

    def current(self, va, vb, i): return i

    def spice(self, a, b): return f"{self.spice_name()} {a} {b} {self.spice_tail()}"

    def draw(self, r, cx, cy, tags):
        if self.is_ac(): return self.draw_ac(r, cx, cy, tags)
        wire(r, cx, cy, -12, 12, tags)
        r.line([(cx - 12, cy - 22), (cx - 12, cy + 22)], 3, OUTLINE, tags)       # long plate = positive (first terminal)
        r.line([(cx + 12, cy - 12), (cx + 12, cy + 12)], 5, OUTLINE, tags)
        r.text(cx - 24, cy - 22, "+", 12, ACCENT, True, "c", tags)

    def draw_ac(self, r, cx, cy, tags):
        wire(r, cx, cy, -20, 20, tags)
        r.circle(cx, cy, 20, FILL, OUTLINE, 2, tags)
        r.line([(cx - 11 + 22 * k / 16, cy - 8 * math.sin(2 * math.pi * k / 16)) for k in range(17)], 2, LABEL, tags)
        r.text(cx - 26, cy - 14, "+", 12, ACCENT, True, "c", tags)


class CurrentSource(Waveform, AnalogPart):
    type_name, aliases, letter, unit, default = "CurrentSource", ("I", "DCCurrent"), "I", "A", "1m"
    summary = "Current source: DC level 'value' plus an optional AC part ('ac', 'freq', 'phase', 'wave', as for a voltage source). Current flows from the first node through the source to the second."
    positive, dc_path = False, False

    def check(self): return AnalogPart.check(self) + self.check_wave()
    def stamp(self, s, volts): s.inject(self.nodes[0], self.nodes[1], (self.number() if s.t is None else self.at(s.t)) * s.scale)

    def current(self, va, vb, i): return self.number()

    def spice(self, a, b): return f"{self.spice_name()} {a} {b} {self.spice_tail()}"

    def draw(self, r, cx, cy, tags):
        wire(r, cx, cy, -20, 20, tags)
        r.circle(cx, cy, 20, FILL, OUTLINE, 2, tags)
        r.line([(cx - 11, cy), (cx + 11, cy)], 2, LABEL, tags); r.polygon([(cx + 12, cy), (cx + 4, cy - 5), (cx + 4, cy + 5)], LABEL, LABEL, 1, tags)


# Real diodes: saturation current IS (A) and emission coefficient N, as in the manufacturers' SPICE models (series resistance is not modelled).
DIODE_MODELS = {"1N4148": (2.68e-9, 1.836, "small-signal switching diode"), "1N914": (2.68e-9, 1.836, "small-signal switching diode"),
                "1N4001": (14.1e-9, 1.984, "1 A rectifier"), "1N4007": (14.1e-9, 1.984, "1 A rectifier, 1000 V"),
                "1N5819": (31.7e-6, 1.373, "Schottky rectifier (low forward voltage)"), "1N5817": (31.7e-6, 1.373, "Schottky rectifier"),
                "BAT54": (1.5e-7, 1.0, "small-signal Schottky diode"), "SI": (1e-14, 1.0, "generic silicon diode")}


class Diode(AnalogPart):
    type_name, aliases, letter, unit, default = "Diode", ("D",), "D", "", None
    summary = ("Diode. nodes = [anode, cathode]. Optional \"model\": one of " + ", ".join(sorted(DIODE_MODELS)) + " (default: a generic silicon diode).")
    IS, N = 1e-14, 1.0
    nonlinear, vmax = True, 1.2
    extras = {"model": ""}

    def __init__(self, cid, nodes, value=None, **extra):
        super().__init__(cid, nodes, value, **extra)
        m = DIODE_MODELS.get(str(self.extra.get("model", "")).strip().upper())
        if m: self.IS, self.N = m[0], m[1]

    def check(self):
        errs = AnalogPart.check(self); m = str(self.extra.get("model", "")).strip().upper()
        if m and m not in DIODE_MODELS: errs.append(f"{self.id}: unknown diode model '{self.extra['model']}' (known: {', '.join(sorted(DIODE_MODELS))})")
        return errs

    def stamp(self, s, volts):
        a, b = self.nodes
        vd = s.limit(self, "f", volts.get(a, 0.0) - volts.get(b, 0.0), self.N * VT, self.IS)
        e = math.exp(min(vd / (self.N * VT), 80)); i = self.IS * (e - 1); g = self.IS * e / (self.N * VT) + 1e-12
        s.conductance(a, b, g); s.inject(a, b, i - g * vd)

    def current(self, va, vb, i):
        return self.IS * (math.exp(min((va - vb) / (self.N * VT), 80)) - 1)

    def gsmall(self, vd):
        """Small-signal conductance at the operating point vd (what the AC analysis uses)."""
        return self.IS * math.exp(min(vd / (self.N * VT), 80)) / (self.N * VT) + 1e-12

    def _mname(self):
        m = str(self.extra.get("model", "")).strip().upper(); return "D" + m if m in DIODE_MODELS else "DMOD"

    def spice(self, a, b): return f"{self.spice_name()} {a} {b} {self._mname()}"
    def model(self): return f".model {self._mname()} D(IS={self.IS:g} N={self.N:g})" if self._mname() != "DMOD" else ".model DMOD D"
    def model_name(self): return self._mname()

    def draw(self, r, cx, cy, tags):
        wire(r, cx, cy, -12, 12, tags)
        r.polygon([(cx - 12, cy - 14), (cx - 12, cy + 14), (cx + 12, cy)], FILL, OUTLINE, 2, tags)
        r.line([(cx + 12, cy - 14), (cx + 12, cy + 14)], 3, OUTLINE, tags)


class LED(Diode):
    idp = "LED"
    type_name, aliases, letter = "LED", (), "D"
    summary = "Light-emitting diode: forward voltage about 1.7 V at 10 mA. nodes = [anode, cathode]. Put a resistor in series."
    IS, N, vmax = 1e-18, 1.8, 3.5
    extras = {}

    def spice(self, a, b): return f"{self.spice_name()} {a} {b} DLED"
    def model(self): return ".model DLED D(IS=1e-18 N=1.8)"
    def model_name(self): return "DLED"

    def draw(self, r, cx, cy, tags):
        Diode.draw(self, r, cx, cy, tags)
        for k in (0, 1):
            x = cx - 2 + 10 * k
            r.line([(x, cy - 20), (x + 9, cy - 31)], 2, ACCENT, tags); r.polygon([(x + 9, cy - 31), (x + 3, cy - 29), (x + 7, cy - 25)], ACCENT, ACCENT, 1, tags)


class Zener(Diode):
    idp = "Z"
    type_name, aliases, letter = "Zener", ("ZenerDiode",), "D"
    extras = {"vz": "5.1"}
    summary = "Zener diode: conducts forward like a diode and in reverse above its breakdown voltage 'vz' (default 5.1). nodes = [anode, cathode]."

    def vz(self): return parse_value(self.extra["vz"])
    def knee(self): return self.N * VT * math.log(1e-3 / self.IS)

    def check(self):
        errs = Diode.check(self)
        try:
            if self.vz() <= 0: errs.append(f"{self.id}: vz must be greater than 0")
        except ValueError as e: errs.append(f"{self.id}: {e}")
        return errs

    def stamp(self, s, volts):
        Diode.stamp(self, s, volts)
        a, b = self.nodes; vz = self.vz(); vk = self.knee()
        vr = s.limit(self, "r", -(volts.get(a, 0.0) - volts.get(b, 0.0)) - vz + vk, self.N * VT, self.IS)     # reverse diode: 1 mA flows at exactly -vz (like SPICE's BV / IBV)
        e = math.exp(min(vr / (self.N * VT), 80)); i = self.IS * (e - 1); g = self.IS * e / (self.N * VT)
        vd0 = -vr - vz + vk                                           # the operating point this step is linearised at
        s.conductance(a, b, g); s.inject(a, b, -i - g * vd0)

    def gsmall(self, vd):
        g = Diode.gsmall(self, vd)
        return g + self.IS * math.exp(min((-vd - self.vz() + self.knee()) / (self.N * VT), 80)) / (self.N * VT)

    def current(self, va, vb, i):
        vd = va - vb
        return Diode.current(self, va, vb, i) - self.IS * (math.exp(min((-vd - self.vz() + self.knee()) / (self.N * VT), 80)) - 1)

    def spice(self, a, b): return f"{self.spice_name()} {a} {b} DZ_{self.id}"
    def model(self): return f".model DZ_{self.id} D(BV={self.vz():g} IBV=1m)"

    def draw(self, r, cx, cy, tags):
        Diode.draw(self, r, cx, cy, tags)
        r.line([(cx + 12, cy - 14), (cx + 7, cy - 19)], 3, OUTLINE, tags); r.line([(cx + 12, cy + 14), (cx + 17, cy + 19)], 3, OUTLINE, tags)


class Switch(AnalogPart):
    type_name, aliases, letter, unit, default = "Switch", ("SPST",), "S", "", None
    extras = {"state": "closed"}
    summary = "Switch: 'state' is \"closed\" or \"open\". Click it in the schematic to toggle."
    RON, ROFF = 1e-6, 1e12

    def is_closed(self): return str(self.extra["state"]).lower() == "closed"
    def conducts(self): return self.is_closed()
    def caption(self, digits=4): return "closed" if self.is_closed() else "open"

    def check(self):
        errs = AnalogPart.check(self)
        if str(self.extra["state"]).lower() not in ("open", "closed"): errs.append(f'{self.id}: "state" must be "open" or "closed"')
        return errs

    def stamp(self, s, volts): s.conductance(self.nodes[0], self.nodes[1], 1.0 / (self.RON if self.is_closed() else self.ROFF))
    def current(self, va, vb, i): return (va - vb) / (self.RON if self.is_closed() else self.ROFF)
    def spice(self, a, b): return f"R{self.id} {a} {b} {self.RON if self.is_closed() else self.ROFF:g}   * switch, {self.caption()}"

    def draw(self, r, cx, cy, tags):
        wire(r, cx, cy, -22, 22, tags)
        r.circle(cx - 22, cy, 3, FILL, OUTLINE, 2, tags); r.circle(cx + 22, cy, 3, FILL, OUTLINE, 2, tags)
        r.line([(cx - 22, cy), (cx + 22, cy) if self.is_closed() else (cx + 18, cy - 20)], 3, OUTLINE, tags)


class Ammeter(AnalogPart):
    idp = "A"
    type_name, aliases, letter, unit, default = "Ammeter", (), "V", "A", None
    summary = "Ammeter: zero resistance, shows the current from its first node to its second."
    branch, positive = True, False

    def stamp(self, s, volts): s.branch_voltage(self, 0.0)
    def current(self, va, vb, i): return i
    def caption(self, digits=4): return ""
    def spice(self, a, b): return f"V{self.id} {a} {b} DC 0   * ammeter"

    def draw(self, r, cx, cy, tags):
        wire(r, cx, cy, -20, 20, tags)
        r.circle(cx, cy, 20, FILL, OUTLINE, 2, tags); r.text(cx, cy, "A", 14, LABEL, True, "c", tags)


class Voltmeter(AnalogPart):
    idp = "VM"
    type_name, aliases, letter, unit, default = "Voltmeter", (), "R", "V", None
    summary = "Voltmeter: infinite resistance, shows the voltage from its first node to its second."
    dc_path = False

    def stamp(self, s, volts): s.conductance(self.nodes[0], self.nodes[1], 1e-12)
    def current(self, va, vb, i): return 0.0
    def caption(self, digits=4): return ""
    def spice(self, a, b): return f"R{self.id} {a} {b} 1e12   * voltmeter"

    def draw(self, r, cx, cy, tags):
        wire(r, cx, cy, -20, 20, tags)
        r.circle(cx, cy, 20, FILL, OUTLINE, 2, tags); r.text(cx, cy, "V", 14, LABEL, True, "c", tags)


class Dependent(AnalogPart):
    """Controlled source. 'value' is the gain; 'control' is two nodes (voltage controlled) or a part id (current controlled)."""
    extras = {"control": None}
    positive = False
    current_controlled = False

    def number(self):
        return parse_value(self.value)

    def ctrl_nodes(self):
        c = self.extra["control"]
        return [str(x).strip() for x in c] if isinstance(c, (list, tuple)) and len(c) == 2 else []

    def control_nodes(self): return self.ctrl_nodes()

    def check(self):
        errs = AnalogPart.check(self)
        c = self.extra["control"]
        if self.current_controlled:
            if not isinstance(c, str) or not c.strip(): errs.append(f'{self.id}: "control" must be the id of the voltage source or ammeter whose current controls it, e.g. "V1"')
        elif len(self.ctrl_nodes()) != 2: errs.append(f'{self.id}: "control" must be two node names, e.g. ["n1", "n2"] (the voltage between them controls this source)')
        return errs

    def ctrl_part(self, s_or_parts):
        return next((p for p in s_or_parts if p.id == str(self.extra["control"]).strip()), None)

    def caption(self, digits=4):
        c = self.ctrl_nodes(); ref = "I(" + str(self.extra["control"]) + ")" if self.current_controlled else ("?" if len(c) != 2 else (f"V({c[0]})" if c[1] in ("0", "gnd", "GND") else f"V({c[0]},{c[1]})"))
        return f"{fmt_si(self.number(), '' if self.unit in ('V/V', 'A/A') else self.unit, digits)}×{ref}"

    def diamond(self, r, cx, cy, tags):
        wire(r, cx, cy, -22, 22, tags)
        r.polygon([(cx, cy - 22), (cx + 22, cy), (cx, cy + 22), (cx - 22, cy)], FILL, OUTLINE, 2, tags)


class VCVS(Dependent):
    type_name, aliases, letter, unit, default = "VCVS", ("E",), "E", "V/V", "1"
    summary = "Voltage-controlled voltage source: V(a) - V(b) = gain × V(control[0], control[1])."
    branch = True

    def stamp(self, s, volts):
        c = self.ctrl_nodes(); s.vcvs(self, c[0], c[1], self.number())
    def current(self, va, vb, i): return i
    def spice(self, a, b): c = self.ctrl_nodes(); return f"{self.spice_name()} {a} {b} {c[0]} {c[1]} {self.number():g}"
    def spice_name(self): return self.id if self.id[:1].upper() == "E" else "E" + self.id

    def draw(self, r, cx, cy, tags):
        self.diamond(r, cx, cy, tags); r.text(cx - 9, cy, "+", 12, ACCENT, True, "c", tags); r.text(cx + 9, cy, "−", 12, LABEL, True, "c", tags)


class VCCS(Dependent):
    type_name, aliases, letter, unit, default = "VCCS", ("G",), "G", "S", "1m"
    summary = "Voltage-controlled current source: the current from a through the source to b = gain × V(control[0], control[1])."

    def stamp(self, s, volts):
        c = self.ctrl_nodes(); s.vccs(self.nodes[0], self.nodes[1], c[0], c[1], self.number())
    def res_current(self, volts, bcur):
        c = self.ctrl_nodes(); return self.number() * (volts[c[0]] - volts[c[1]])
    def spice(self, a, b): c = self.ctrl_nodes(); return f"{self.spice_name()} {a} {b} {c[0]} {c[1]} {self.number():g}"
    def spice_name(self): return self.id if self.id[:1].upper() == "G" else "G" + self.id
    dc_path = False

    def draw(self, r, cx, cy, tags):
        self.diamond(r, cx, cy, tags)
        r.line([(cx - 10, cy), (cx + 8, cy)], 2, LABEL, tags); r.polygon([(cx + 11, cy), (cx + 4, cy - 5), (cx + 4, cy + 5)], LABEL, LABEL, 1, tags)


class CCVS(Dependent):
    type_name, aliases, letter, unit, default = "CCVS", ("H",), "H", "Ω", "1k"
    summary = "Current-controlled voltage source: V(a) - V(b) = gain × (current through the part named in 'control')."
    branch, current_controlled = True, True

    def stamp(self, s, volts): s.ccvs(self, self.ctrl, self.number())
    def current(self, va, vb, i): return i
    def spice(self, a, b): return f"{self.spice_name()} {a} {b} {self.ctrl_spice} {self.number():g}"
    def spice_name(self): return self.id if self.id[:1].upper() == "H" else "H" + self.id

    def draw(self, r, cx, cy, tags):
        self.diamond(r, cx, cy, tags); r.text(cx - 9, cy, "+", 12, ACCENT, True, "c", tags); r.text(cx + 9, cy, "−", 12, LABEL, True, "c", tags)


class CCCS(Dependent):
    type_name, aliases, letter, unit, default = "CCCS", ("F",), "F", "A/A", "1"
    summary = "Current-controlled current source: the current from a through the source to b = gain × (current through the part named in 'control')."
    current_controlled, dc_path = True, False

    def stamp(self, s, volts): s.cccs(self.nodes[0], self.nodes[1], self.ctrl, self.number())
    def res_current(self, volts, bcur): return self.number() * bcur.get(str(self.extra["control"]).strip(), 0.0)
    def spice(self, a, b): return f"{self.spice_name()} {a} {b} {self.ctrl_spice} {self.number():g}"
    def spice_name(self): return self.id if self.id[:1].upper() == "F" else "F" + self.id

    def draw(self, r, cx, cy, tags):
        self.diamond(r, cx, cy, tags)
        r.line([(cx - 10, cy), (cx + 8, cy)], 2, LABEL, tags); r.polygon([(cx + 11, cy), (cx + 4, cy - 5), (cx + 4, cy + 5)], LABEL, LABEL, 1, tags)


PARTS = {}
ALL = [Resistor, VoltageSource, CurrentSource, Capacitor, Inductor, Diode, Zener, LED, Switch, Ammeter, Voltmeter, VCVS, VCCS, CCVS, CCCS]
from .active import ACTIVE, NPN, PNP, NMOS, PMOS, NJFET, PJFET, IGBT, OpAmp, Transformer, Potentiometer, Multi
ALL = tuple(ALL) + ACTIVE
for cls in ALL:
    for k in (cls.type_name,) + cls.aliases: PARTS[k.lower()] = cls


def lookup(name): return PARTS.get(str(name).strip().lower())
def part_types(): return list(ALL)
