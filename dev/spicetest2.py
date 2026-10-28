import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from vibesimulation.imports.spice_in import parse_spice
from vibesimulation.analog.netlist import parse, to_spice
bad = 0
def chk(n, c, x=""):
    global bad; print("ok  " if c else "FAIL", n, "" if c else x); bad += (not c)
T = """transistor amp
VCC vcc 0 DC 12
RB vcc b 470k
RC vcc c 2.2k
Q1 c b 0 QMOD
.model QMOD NPN(IS=2e-14 BF=150 VAF=80 CJE=10p)
VG g 0 DC 4
RD vcc d 500
M1 d g 0 0 MN W=10u L=1u
.model MN NMOS(LEVEL=1 VTO=2 KP=5e-4 LAMBDA=0.02)
J1 vcc 0 j0 JN
RJ j0 0 1k
.model JN NJF(VTO=-2 BETA=1m)
.end
"""
nl, notes = parse_spice(T); print(notes)
q = nl.part("Q1"); m = nl.part("M1"); j = nl.part("J1")
chk("BJT imported", type(q).__name__ == "NPN" and q.extra["bf"] == "150" and q.extra["is"] == "2e-14" and q.extra["vaf"] == "80" and q.extra["cbe"] == "10p")
chk("MOSFET imported with W/L", type(m).__name__ == "NMOS" and abs(m.pv("kp") - 5e-3) < 1e-12 and m.pv("vto") == 2.0)
chk("JFET imported", type(j).__name__ == "NJFET" and j.pv("beta") == 1e-3)
# round trip through our own export
txt = to_spice(nl); nl2, n2 = parse_spice(txt); print(n2)
for pid in ("Q1", "M1", "J1"):
    a, b = nl.part(pid), nl2.part(pid); chk(f"round trip {pid}", type(a) is type(b) and all(abs(a.pv(k) - b.pv(k)) <= 1e-9 * max(1, abs(a.pv(k))) for k in a.extras) and a.nodes == b.nodes, (a.extra, b.extra))
# PNP / PMOS / PJF
T2 = "t\nV1 a 0 DC -9\nR1 a b 1k\nQ1 c b 0 QP\n.model QP PNP(BF=80)\nR2 c 0 1k\nM1 d g 0 0 MP\n.model MP PMOS(VTO=-1.5 KP=1m)\nR3 d 0 1k\nR4 g 0 1k\nJ1 e 0 0 JP\n.model JP PJF(VTO=2 BETA=2m)\nR5 e a 1k\n.end\n"
nl, notes = parse_spice(T2); print(notes)
chk("PNP/PMOS/PJFET types", [type(nl.part(i)).__name__ for i in ("Q1", "M1", "J1")] == ["PNP", "PMOS", "PJFET"])
# transformer from K
T3 = "tr\nV1 p 0 DC 0 AC 1\nL1 p 0 100m\nL2 s 0 400m\nK1 L1 L2 0.95\nRL s 0 1k\n.ac dec 10 10 100k\n.end\n"
nl, notes = parse_spice(T3); print(notes, [type(p).__name__ for p in nl.parts])
t = nl.part("L1_L2"); chk("K -> Transformer", t is not None and abs(t.pv("ratio") - 2) < 1e-9 and t.pv("k") == 0.95 and t.number() == 0.1 and t.nodes == ["p", "0", "s", "0"])
chk("no inductor left", not any(type(p).__name__ == "Inductor" for p in nl.parts))
print("FAILURES:", bad); sys.exit(1 if bad else 0)
