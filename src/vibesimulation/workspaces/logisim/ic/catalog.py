"""The 74xx chips of Logisim-evolution 5.0.0 (``std/ttl``): title, DIP pinout and the functional units inside each package.

Titles and the order of the signal pins are the ones Logisim uses; power pins follow the datasheets
(GND = pin N/2 and VCC = pin N, except the 7476 and 7493).  ``dev/ic_catalog_check.py`` compares this table with the
Java sources of Logisim, so the numbers here stay honest.

A *unit* is one repeated block of a package (one NAND gate of a 7400, one flip-flop of a 7474).  Each unit
lists ``role -> pin`` for its own pins; ``common`` lists pins shared by all units (clock, clear, select ...).
Roles ending in ``_n`` are active-low controls (an unused one is tied to VCC, any other unused input to GND).
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Pin:
    name: str
    kind: str          # "in", "out", "io" (bidirectional / tri-state), "vcc", "gnd", "nc"


@dataclass(frozen=True)
class Unit:
    func: str                         # what the unit does: NAND2, NOT, DFF, MUX2 ...
    pins: tuple                       # ((role, pin number or tuple of pin numbers), ...)

    def get(self, role):
        return dict(self.pins)[role]

    def roles(self):
        return [r for r, _ in self.pins]


@dataclass(frozen=True)
class Chip:
    part: str                         # "7400" (the name Logisim uses)
    title: str                        # Logisim's own description
    family: str                       # Gates, Decoders ... (library grouping)
    pinout: tuple                     # Pin objects, pin 1 first
    units: tuple = ()                 # Unit objects ("units" the mapper can use); empty = catalogue only
    common: tuple = ()                # ((role, pin), ...) shared by every unit
    wide: bool = False                # 0.6 inch package: does not straddle a breadboard gap
    notes: str = ""
    logisim: bool = True              # False: not in Logisim's TTL library (added from a lab sheet)

    @property
    def pins(self): return len(self.pinout)

    @property
    def vcc(self): return next(i + 1 for i, p in enumerate(self.pinout) if p.kind == "vcc")

    @property
    def gnd(self): return next(i + 1 for i, p in enumerate(self.pinout) if p.kind == "gnd")

    @property
    def mapped(self): return bool(self.units)

    def pin_name(self, n): return self.pinout[n - 1].name

    def pin_kind(self, n): return self.pinout[n - 1].kind

    def common_map(self): return dict(self.common)

    def signal_pins(self):
        return [i + 1 for i, p in enumerate(self.pinout) if p.kind in ("in", "out", "io")]


def _pinout(text):
    out = []
    for tok in text.split():
        if tok == "VCC": out.append(Pin("VCC", "vcc"))
        elif tok == "GND": out.append(Pin("GND", "gnd"))
        elif tok == "NC": out.append(Pin("NC", "nc"))
        elif tok.endswith("<>"): out.append(Pin(tok[:-2], "io"))
        elif tok.endswith(">"): out.append(Pin(tok[:-1], "out"))
        else: out.append(Pin(tok, "in"))
    return tuple(out)


def _gates(func, groups):
    return tuple(Unit(func, (("in", tuple(i)), ("out", o))) for i, o in groups)


# ---- pin layouts shared by many gate chips
_L2 = "1A 1B 1Y> 2A 2B 2Y> GND 3Y> 3A 3B 4Y> 4A 4B VCC"                  # 7400 layout (quad 2-input)
_L2_UNITS = [((1, 2), 3), ((4, 5), 6), ((9, 10), 8), ((12, 13), 11)]
_LNOR = "1Y> 1A 1B 2Y> 2A 2B GND 3A 3B 3Y> 4A 4B 4Y> VCC"                  # 7402 layout (output first)
_LNOR_UNITS = [((2, 3), 1), ((5, 6), 4), ((8, 9), 10), ((11, 12), 13)]
_LHEX = "1A 1Y> 2A 2Y> 3A 3Y> GND 4Y> 4A 5Y> 5A 6Y> 6A VCC"                # 7404 layout (hex)
_LHEX_UNITS = [((1,), 2), ((3,), 4), ((5,), 6), ((9,), 8), ((11,), 10), ((13,), 12)]
_L3 = "1A 1B 2A 2B 2C 2Y> GND 3Y> 3A 3B 3C 1Y> 1C VCC"                      # 7410 layout (triple 3-input)
_L3_UNITS = [((1, 2, 13), 12), ((3, 4, 5), 6), ((9, 10, 11), 8)]
_L4 = "1A 1B NC 1C 1D 1Y> GND 2Y> 2A 2B NC 2C 2D VCC"                       # 7420 layout (dual 4-input)
_L4_UNITS = [((1, 2, 4, 5), 6), ((9, 10, 12, 13), 8)]
_D8 = tuple((("D", d), ("Q", q)) for d, q in ((3, 2), (4, 5), (7, 6), (8, 9), (13, 12), (14, 15), (17, 16), (18, 19)))   # 74273 / 74377 flip-flops

CHIPS = {}


def _add(part, title, family, layout, units=(), common=(), wide=False, notes="", logisim=True):
    CHIPS[part] = Chip(part, title, family, _pinout(layout), tuple(units), tuple(common), wide, notes, logisim)


# ============================================================ gates
_add("7400", "quad 2-input NAND gate", "Gates", _L2, _gates("NAND2", _L2_UNITS))
_add("7402", "quad 2-input NOR gate (right-to-left)", "Gates", _LNOR, _gates("NOR2", _LNOR_UNITS))
_add("7404", "hex inverter", "Gates", _LHEX, _gates("NOT", _LHEX_UNITS))
_add("7408", "quad 2-input AND gate", "Gates", _L2, _gates("AND2", _L2_UNITS))
_add("7410", "triple 3-input NAND gate", "Gates", _L3, _gates("NAND3", _L3_UNITS))
_add("7411", "triple 3-input AND gate", "Gates", _L3, _gates("AND3", _L3_UNITS))
_add("7413", "dual 4-input NAND gate (Schmitt trigger)", "Gates", _L4)
_add("7414", "hex inverter (Schmitt trigger)", "Gates", _LHEX)
_add("7418", "dual 4-input NAND gate (Schmitt trigger)", "Gates", _L4)
_add("7419", "hex inverter (Schmitt trigger)", "Gates", _LHEX)
_add("7420", "dual 4-input NAND gate", "Gates", _L4, _gates("NAND4", _L4_UNITS))
_add("7421", "dual 4-input AND gate", "Gates", _L4, _gates("AND4", _L4_UNITS))
_add("7424", "quad 2-input NAND gate (Schmitt trigger)", "Gates", _L2)
_add("7427", "triple 3-input NOR gate", "Gates", _L3, _gates("NOR3", _L3_UNITS))
_add("7430", "single 8-input NAND gate", "Gates", "A B C D E F GND Y> NC NC G H NC VCC", _gates("NAND8", [((1, 2, 3, 4, 5, 6, 11, 12), 8)]))
_add("7432", "quad 2-input OR gate", "Gates", _L2, _gates("OR2", _L2_UNITS))
_add("7434", "hex buffer gate", "Gates", _LHEX, _gates("BUF", _LHEX_UNITS))
_add("7436", "quad 2-input NOR gate", "Gates", _L2)
_add("7438", "quad 2-input NAND gate (open-collector)", "Gates", _L2, notes="Open-collector outputs: each output needs a pull-up resistor to VCC.")
_add("7486", "quad 2-input XOR gate", "Gates", _L2, _gates("XOR2", _L2_UNITS))
_add("74266", "quad 2-input XNOR gate (open-collector)", "Gates", _L2, _gates("XNOR2", _L2_UNITS),
     notes="Open-collector outputs: each output needs a 1 k pull-up resistor to VCC.")
_add("747266", "quad 2-input XNOR gate", "Gates", _L2)
_add("7451", "dual AND-OR-INVERT gate", "Gates", "1A 2A 2B 2C 2D 2Y> GND 1Y> 1C 1D NC NC 1B VCC")
_add("7454", "Four wide AND-OR-INVERT gate", "Gates", "A C D E F NC GND Y> G H NC NC B VCC")
_add("7458", "dual AND-OR gate", "Gates", "A0 A1 B1 C1 D1 Y1> GND Y0> D0 E0 F0 B0 C0 VCC")
_add("7464", "4-2-3-2 AND-OR-INVERT gate", "Gates", "A E F G H I GND Y> J K B C D VCC")
_add("7487", "4-bit True/complement, zero/one elements", "Gates", "C A1 Y1> NC A2 Y2> GND B Y3> A3 NC Y4> A4 VCC")

# ============================================================ buffers
_add("74125", "quad bus buffer, three-state outputs, negative enable", "Buffers", "1G 1A 1Y> 2G 2A 2Y> GND 3Y> 3A 3G 4Y> 4A 4G VCC")
_LOCT = "{g1} 1A1 2Y4> 1A2 2Y3> 1A3 2Y2> 1A4 2Y1> GND 2A1 1Y4> 2A2 1Y3> 2A3 1Y2> 2A4 1Y1> {g2} VCC"
_add("74240", "octal buffers with three-state inverted outputs", "Buffers", _LOCT.format(g1="1G", g2="2G"))
_add("74241", "octal buffers with three-state outputs and complementary enables", "Buffers", _LOCT.format(g1="1G", g2="2G"))
_add("74244", "octal buffers with three-state outputs", "Buffers", _LOCT.format(g1="1G", g2="2G"))
_add("74245", "octal bus transceivers with three-state outputs", "Buffers",
     "DIR A1<> A2<> A3<> A4<> A5<> A6<> A7<> A8<> GND B8<> B7<> B6<> B5<> B4<> B3<> B2<> B1<> OE VCC")
_add("74541", "Octal buffers with three-state outputs", "Buffers", "OE1 A1 A2 A3 A4 A5 A6 A7 A8 GND Y8> Y7> Y6> Y5> Y4> Y3> Y2> Y1> OE2 VCC")

# ============================================================ decoders / data selectors
_add("7442", "BCD to decimal decoder", "Decoders", "Y0> Y1> Y2> Y3> Y4> Y5> Y6> GND Y7> Y8> Y9> D C B A VCC")
_add("7443", "Excess-3 to decimal decoder", "Decoders", "Y0> Y1> Y2> Y3> Y4> Y5> Y6> GND Y7> Y8> Y9> D C B A VCC")
_add("7444", "Gray to decimal decoder", "Decoders", "Y0> Y1> Y2> Y3> Y4> Y5> Y6> GND Y7> Y8> Y9> D C B A VCC")
_add("7447", "BCD to 7-segment decoder", "Decoders", "B C LT BI RBI D A GND e> d> c> b> a> g> f> VCC",
     (Unit("BCD7", (("A", 7), ("B", 1), ("C", 2), ("D", 6), ("LT_n", 3), ("BI_n", 4), ("RBI_n", 5), ("a_n", 13), ("b_n", 12), ("c_n", 11), ("d_n", 10), ("e_n", 9), ("f_n", 15), ("g_n", 14))),),
     notes="Active-low outputs for a common-anode display; only 0-9 are real digits (10-15 show odd shapes).")
_add("74138", "3-line to 8-line decoder", "Decoders", "A B C G2A G2B G1 Y7> GND Y6> Y5> Y4> Y3> Y2> Y1> Y0> VCC",
     (Unit("DEC3", (("A", 1), ("B", 2), ("C", 3), ("G2A_n", 4), ("G2B_n", 5), ("G1", 6), ("Y0_n", 15), ("Y1_n", 14), ("Y2_n", 13), ("Y3_n", 12), ("Y4_n", 11), ("Y5_n", 10), ("Y6_n", 9), ("Y7_n", 7))),),
     notes="Outputs are active-LOW.")
_add("74139", "Dual 2-line to 4-line decoder", "Decoders", "1G 1A 1B 1Y0> 1Y1> 1Y2> 1Y3> GND 2Y3> 2Y2> 2Y1> 2Y0> 2B 2A 2G VCC",
     (Unit("DEC2", (("G_n", 1), ("A", 2), ("B", 3), ("Y0_n", 4), ("Y1_n", 5), ("Y2_n", 6), ("Y3_n", 7))),
      Unit("DEC2", (("G_n", 15), ("A", 14), ("B", 13), ("Y0_n", 12), ("Y1_n", 11), ("Y2_n", 10), ("Y3_n", 9)))),
     notes="Outputs are active-LOW.")
_add("74151", "8-line to 1 line data selector", "Selectors", "D3 D2 D1 D0 Y> W> G GND C B A D7 D6 D5 D4 VCC",
     (Unit("MUX8", (("D0", 4), ("D1", 3), ("D2", 2), ("D3", 1), ("D4", 15), ("D5", 14), ("D6", 13), ("D7", 12), ("A", 11), ("B", 10), ("C", 9), ("G_n", 7), ("Y", 5))),))
_add("74153", "dual 4-line to 1 line data selector", "Selectors", "1G S1 1C3 1C2 1C1 1C0 1Y> GND 2Y> 2C0 2C1 2C2 2C3 S0 2G VCC",
     (Unit("MUX4", (("G_n", 1), ("D3", 3), ("D2", 4), ("D1", 5), ("D0", 6), ("Y", 7))),
      Unit("MUX4", (("G_n", 15), ("D3", 13), ("D2", 12), ("D1", 11), ("D0", 10), ("Y", 9)))),
     (("A", 14), ("B", 2)))
_L157 = "S 1A 1B 1Y> 2A 2B 2Y> GND 3Y> 3B 3A 4Y> 4B 4A G VCC"
_add("74157", "quad 2-line to 1 line data selector", "Selectors", _L157,
     tuple(Unit("MUX2", (("D0", a), ("D1", b), ("Y", y))) for a, b, y in ((2, 3, 4), (5, 6, 7), (11, 10, 9), (14, 13, 12))),
     (("S", 1), ("G_n", 15)))
_add("74158", "quad 2-line to 1 line data selector, inverted output", "Selectors", _L157)

# ============================================================ flip-flops, registers
_add("7474", "dual D-Flipflops with preset and clear", "Flip-flops", "CLR1 D1 CLK1 PRE1 Q1> QN1> GND QN2> Q2> PRE2 CLK2 D2 CLR2 VCC",
     (Unit("DFF", (("D", 2), ("CLK", 3), ("PRE_n", 4), ("CLR_n", 1), ("Q", 5), ("QN", 6))),
      Unit("DFF", (("D", 12), ("CLK", 11), ("PRE_n", 10), ("CLR_n", 13), ("Q", 9), ("QN", 8)))),
     notes="Triggers on the rising clock edge; preset and clear are active-low.")
_add("7476", "dual J-K Flipflops with preset and clear", "Flip-flops", "CLK1 PRE1 CLR1 J1 VCC CLK2 PRE2 CLR2 J2 QN2> Q2> K2 GND QN1> Q1> K1",
     (Unit("JKFF", (("J", 4), ("K", 16), ("CLK", 1), ("PRE_n", 2), ("CLR_n", 3), ("Q", 15), ("QN", 14))),
      Unit("JKFF", (("J", 9), ("K", 12), ("CLK", 6), ("PRE_n", 7), ("CLR_n", 8), ("Q", 11), ("QN", 10)))),
     notes="Triggers on the falling clock edge; power is on pins 5 (VCC) and 13 (GND).")
_add("74175", "quad D-flipflop, asynchronous reset", "Registers", "CLR 1Q> 1QN> 1D 2D 2QN> 2Q> GND CLK 3Q> 3QN> 3D 4D 4QN> 4Q> VCC",
     tuple(Unit("DREG", (("D", d), ("Q", q), ("QN", qn))) for d, q, qn in ((4, 2, 3), (5, 7, 6), (12, 10, 11), (13, 15, 14))),
     (("CLK", 9), ("CLR_n", 1)))
_add("74273", "octal D-Flipflop with clear", "Registers", "CLR 1Q> 1D 2D 2Q> 3Q> 3D 4D 4Q> GND CLK 5Q> 5D 6D 6Q> 7Q> 7D 8D 8Q> VCC",
     tuple(Unit("DREG", u) for u in _D8), (("CLK", 11), ("CLR_n", 1)))
_add("74377", "octal D-Flipflop with enable", "Registers", "E 1Q> 1D 2D 2Q> 3Q> 3D 4D 4Q> GND CLK 5Q> 5D 6D 6Q> 7Q> 7D 8D 8Q> VCC",
     tuple(Unit("DREG", u) for u in _D8), (("CLK", 11), ("E_n", 1)))
_add("74173", "4-bit D-type registers with 3-state outputs", "Registers", "M N 1Q> 2Q> 3Q> 4Q> CLK GND G1 G2 4D 3D 2D 1D CLR VCC",
     tuple(Unit("DREG", (("D", d), ("Q", q))) for d, q in ((14, 3), (13, 4), (12, 5), (11, 6))),
     (("CLK", 7), ("CLR", 15), ("G1_n", 9), ("G2_n", 10), ("M_n", 1), ("N_n", 2)),
     notes="Clear is active-HIGH here. Pins M and N must be low for the outputs to be on.")
_add("74670", "4-by-4 register file with three-state outputs", "Registers", "D2 D3 D4 RA1 RA0 Q4> Q3> GND Q2> Q1> OE WE WA1 WA0 D1 VCC")

# ============================================================ counters, shift registers
_L161 = "CLR CLK A B C D ENP GND LOAD ENT QD> QC> QB> QA> RCO> VCC"
_U161 = (Unit("CNT4", (("CLR_n", 1), ("CLK", 2), ("A", 3), ("B", 4), ("C", 5), ("D", 6), ("ENP", 7), ("LOAD_n", 9), ("ENT", 10), ("QD", 11), ("QC", 12), ("QB", 13), ("QA", 14), ("RCO", 15))),)
_add("74161", "4-bit sync counter with async clear", "Counters", _L161, _U161)
_add("74163", "4-bit sync counter with sync clear", "Counters", _L161)
_add("74164", "8-bit serial-to-parallel shift register", "Shift registers", "A B QA> QB> QC> QD> GND CLK CLR QE> QF> QG> QH> VCC",
     (Unit("SIPO8", (("A", 1), ("B", 2), ("QA", 3), ("QB", 4), ("QC", 5), ("QD", 6), ("CLK", 8), ("CLR_n", 9), ("QE", 10), ("QF", 11), ("QG", 12), ("QH", 13))),))
_add("74165", "8-bit parallel-to-serial shift register", "Shift registers", "SHLD CLK E F G H QHN> GND QH> SER A B C D CLKINH VCC")
_add("74166", "8-bit parallel-to-serial shift register with asynchronous clear", "Shift registers", "SER A B C D CLKINH CLK GND CLR E F G QH> H SHLD VCC")
_add("74192", "4-bit up/down decade counter", "Counters", "B QB> QA> DOWN UP QC> QD> GND D C LOAD CO> BO> CLR A VCC")
_add("74193", "4-bit up/down binary counter", "Counters", "B QB> QA> DOWN UP QC> QD> GND D C LOAD CO> BO> CLR A VCC")
_add("74194", "4-bit bidirectional universal shift register", "Shift registers", "CLR SR A B C D SL GND S0 S1 CLK QD> QC> QB> QA> VCC")
_add("74299", "8-bit universal shift register with three-state outputs", "Shift registers",
     "S0 OE1 OE2 IOG<> IOE<> IOC<> IOA<> QA> CLR GND SR CLK IOB<> IOD<> IOF<> IOH<> QH> SL S1 VCC")
_add("7493", "4-bit binary ripple counter", "Counters", "CKB R01 R02 NC VCC NC NC QC> QB> GND QD> QA> NC CKA",
     notes="Power is on pins 5 (VCC) and 10 (GND).")

# ============================================================ arithmetic
_add("74283", "4-bit binary full adder", "Arithmetic", "S2> B2 A2 S1> A1 B1 CIN GND COUT> S4> B4 A4 S3> A3 B3 VCC",
     (Unit("ADD4", (("A1", 5), ("A2", 3), ("A3", 14), ("A4", 12), ("B1", 6), ("B2", 2), ("B3", 15), ("B4", 11), ("CIN", 7),
                    ("S1", 4), ("S2", 1), ("S3", 13), ("S4", 10), ("COUT", 9))),))
_add("7483", "4-bit binary full adder (lab-sheet pinout)", "Arithmetic", "A4 S3> A3 B3 VCC S2> B2 A2 S1> A1 B1 GND CIN COUT> S4> B4",
     (Unit("ADD4", (("A1", 10), ("A2", 8), ("A3", 3), ("A4", 1), ("B1", 11), ("B2", 7), ("B3", 4), ("B4", 16), ("CIN", 13),
                    ("S1", 9), ("S2", 6), ("S3", 2), ("S4", 15), ("COUT", 14))),),
     notes="Same function as the 74283 with a different pinout: VCC is pin 5 and GND pin 12. Not in Logisim's library (it only has the 74283).",
     logisim=False)
_add("7485", "4-bit magnitude comparator", "Arithmetic", "B3 LTI EQI GTI GTO> EQO> LTO> GND B0 A0 B1 A1 A2 B2 A3 VCC",
     (Unit("CMP4", (("A0", 10), ("A1", 12), ("A2", 13), ("A3", 15), ("B0", 9), ("B1", 11), ("B2", 14), ("B3", 1),
                    ("LTI", 2), ("EQI", 3), ("GTI", 4), ("GTO", 5), ("EQO", 6), ("LTO", 7))),))
_add("74181", "arithmetic logic unit", "Arithmetic",
     "B0 A0 S3 S2 S1 S0 CN M F0> F1> F2> GND F3> AEQB> P> CN4> G> B3 A3 B2 A2 B1 A1 VCC", wide=True,
     notes="24-pin 0.6 inch package: it does not fit across the gap of a normal breadboard.")
_add("74182", "look-ahead carry generator", "Arithmetic", "G1 P1 G0 P0 G3 P3 P> GND CNZ> G> CNY> CNX> CN G2 P2 VCC")
_add("74381", "arithmetic logic unit (ALU)", "Arithmetic", "A1 B1 A0 B0 S0 S1 S2 F0> F1> GND F2> F3> G> P> CN B3 A3 B2 A2 VCC")


def chip(part):
    return CHIPS[str(part)]


def by_family():
    out = {}
    for c in CHIPS.values():
        out.setdefault(c.family, []).append(c)
    for v in out.values(): v.sort(key=lambda c: (len(c.part), c.part))
    return out


def all_chips():
    return sorted(CHIPS.values(), key=lambda c: (len(c.part), c.part))
