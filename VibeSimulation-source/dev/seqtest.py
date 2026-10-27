"""Run sequential circuits in real Logisim (-tty table,halt: it ticks the clocks until the 'halt' pin is 1) and in VibeSimulation; compare every row."""
import json, subprocess, sys
sys.path.insert(0, "src")
from vibesimulation.core.serializer import parse
from vibesimulation.core import sim
from vibesimulation.export.logisim import to_circ

HALT = {"id": "hc", "type": "Counter", "width": 6, "max": 0, "in": {"Clk": "clk"}, "out": {"Carry": "halt"}}   # halts after 63 rising edges


def ck(**a): return dict({"id": "ck", "type": "Clock", "out": "clk"}, **a)
def const(i, v, w=1): return {"id": i, "type": "Constant", "value": v, "width": w, "out": i}


def circuits():
    C = {}
    C["D toggle"] = ([ck(), {"id": "f", "type": "D Flip-Flop", "in": {"D": "qn", "Clk": "clk"}, "out": {"Q": "q", "Qn": "qn"}}], ["q"], 12)
    C["D falling"] = ([ck(), {"id": "f", "type": "D Flip-Flop", "trigger": "falling", "in": {"D": "qn", "Clk": "clk"}, "out": {"Q": "q", "Qn": "qn"}}], ["q"], 12)
    C["ripple T"] = ([ck(), const("one", 1)] + [{"id": f"t{i}", "type": "T Flip-Flop", "in": {"T": "one", "Clk": "clk" if i == 0 else f"n{i-1}"}, "out": {"Q": f"q{i}", "Qn": f"n{i}"}} for i in range(3)], ["q2", "q1", "q0"], 20)
    C["counter wrap max9"] = ([ck(), {"id": "c", "type": "Counter", "width": 4, "max": 9, "in": {"Clk": "clk"}, "out": {"Q": "q"}}], ["q"], 26)
    C["counter stay"] = ([ck(), {"id": "c", "type": "Counter", "width": 3, "ongoal": "stay", "in": {"Clk": "clk"}, "out": {"Q": "q"}}], ["q"], 24)
    C["counter continue"] = ([ck(), {"id": "c", "type": "Counter", "width": 3, "max": 5, "ongoal": "continue", "in": {"Clk": "clk"}, "out": {"Q": "q"}}], ["q"], 30)
    C["counter down"] = ([ck(), const("zero", 0), {"id": "c", "type": "Counter", "width": 3, "in": {"Clk": "clk", "UD": "zero"}, "out": {"Q": "q", "Carry": "cy"}}], ["q", "cy"], 24)
    C["counter load"] = ([ck(), {"id": "tg", "type": "T Flip-Flop", "in": {"T": "one", "Clk": "clk"}, "out": {"Q": "ld"}}, const("one", 1), const("five", 5, 4),
                          {"id": "c", "type": "Counter", "width": 4, "in": {"Clk": "clk", "Ld": "ld", "D": "five"}, "out": {"Q": "q"}}], ["q"], 30)
    C["register"] = ([ck(), {"id": "c", "type": "Counter", "width": 4, "in": {"Clk": "clk"}, "out": {"Q": "cq"}},
                      {"id": "r", "type": "Register", "width": 4, "in": {"D": "cq", "Clk": "clk"}, "out": {"Q": "q"}}], ["cq", "q"], 24)
    C["register en"] = ([ck(), {"id": "c", "type": "Counter", "width": 4, "in": {"Clk": "clk"}, "out": {"Q": "cq"}},
                         {"id": "e", "type": "T Flip-Flop", "in": {"T": "one", "Clk": "clk"}, "out": {"Q": "en"}}, const("one", 1),
                         {"id": "r", "type": "Register", "width": 4, "trigger": "falling", "in": {"D": "cq", "Clk": "clk", "En": "en"}, "out": {"Q": "q"}}], ["cq", "q"], 24)
    C["clock 2/3 phase1"] = ([ck(high=2, low=3, phase=1), {"id": "c", "type": "Counter", "width": 3, "in": {"Clk": "clk"}, "out": {"Q": "q"}}], ["clk", "q"], 40)
    C["JK"] = ([ck(), {"id": "c", "type": "Counter", "width": 2, "in": {"Clk": "clk"}, "out": {"Q": "cq"}},
                {"id": "j", "type": "J-K Flip-Flop", "in": {"J": "a", "K": "b", "Clk": "clk"}, "out": {"Q": "q"}},
                {"id": "t0", "type": "T Flip-Flop", "in": {"T": "one", "Clk": "clk"}, "out": {"Q": "a"}}, const("one", 1),
                {"id": "t1", "type": "T Flip-Flop", "in": {"T": "one", "Clk": "a"}, "out": {"Q": "b"}}], ["a", "b", "q"], 30)
    C["SR"] = ([ck(), {"id": "t0", "type": "T Flip-Flop", "in": {"T": "one", "Clk": "clk"}, "out": {"Q": "a"}}, const("one", 1),
                {"id": "t1", "type": "T Flip-Flop", "in": {"T": "one", "Clk": "a"}, "out": {"Q": "b"}},
                {"id": "s", "type": "S-R Flip-Flop", "in": {"S": "a", "R": "b", "Clk": "clk"}, "out": {"Q": "q"}}], ["a", "b", "q"], 30)
    C["clear/preset"] = ([ck(), {"id": "t0", "type": "T Flip-Flop", "in": {"T": "one", "Clk": "clk"}, "out": {"Q": "a"}}, const("one", 1),
                          {"id": "t1", "type": "T Flip-Flop", "in": {"T": "one", "Clk": "a"}, "out": {"Q": "b"}},
                          {"id": "d", "type": "D Flip-Flop", "in": {"D": "one", "Clk": "clk", "Clr": "a", "Pre": "b"}, "out": {"Q": "q"}}], ["a", "b", "q"], 30)
    C["shift"] = ([ck(), {"id": "t0", "type": "T Flip-Flop", "in": {"T": "one", "Clk": "clk"}, "out": {"Q": "a"}}, const("one", 1),
                   {"id": "t1", "type": "T Flip-Flop", "in": {"T": "one", "Clk": "a"}, "out": {"Q": "b"}},
                   {"id": "s", "type": "Shift Register", "length": 4, "parallel": False, "in": {"In": "b", "Clk": "clk"}, "out": {"Out": "q"}}], ["b", "q"], 40)
    C["shift parallel"] = ([ck(), {"id": "t0", "type": "T Flip-Flop", "in": {"T": "one", "Clk": "clk"}, "out": {"Q": "a"}}, const("one", 1), const("one0", 1),
                            {"id": "t1", "type": "T Flip-Flop", "in": {"T": "one", "Clk": "a"}, "out": {"Q": "ld"}},
                            {"id": "s", "type": "Shift Register", "length": 3, "width": 2, "in": {"In": "x", "Clk": "clk", "Ld": "ld", "D0": "d0", "D1": "d1", "D2": "d2"}, "out": {"Out": "q", "Q0": "q0", "Q1": "q1", "Q2": "q2"}},
                            const("d0", 1, 2), const("d1", 2, 2), const("d2", 3, 2), const("x", 0, 2)], ["q", "q0", "q1"], 40)   # q2 (the last parallel output) is left out: Logisim 3.8.0 leaves it floating (a bug fixed in later versions)
    C["D latch (high)"] = ([ck(), {"id": "c", "type": "Counter", "width": 1, "in": {"Clk": "clk"}, "out": {"Q": "cq"}},
                            {"id": "t", "type": "T Flip-Flop", "in": {"T": "one", "Clk": "cq"}, "out": {"Q": "d"}}, const("one", 1),
                            {"id": "l", "type": "D Flip-Flop", "trigger": "high", "in": {"D": "d", "Clk": "clk"}, "out": {"Q": "q"}}], ["d", "q"], 30)
    ramc = lambda **a: {"id": "m", "type": "RAM", "addr": 4, "in": {"A": "cq", "Din": "k", "WE": "en", "Clk": "clk"}, "out": {"Dout": "q"}, **a}
    base = [ck(), const("k", 165, 8), {"id": "c", "type": "Counter", "width": 4, "in": {"Clk": "clk"}, "out": {"Q": "cq"}},
            {"id": "e", "type": "T Flip-Flop", "in": {"T": "one", "Clk": "clk"}, "out": {"Q": "en"}}, const("one", 1)]
    C["RAM write/read"] = (base + [ramc()], ["cq", "en", "q"], 40)
    C["RAM before write"] = (base + [ramc(readbehav="beforewrite")], ["cq", "en", "q"], 40)
    C["RAM async read"] = (base + [ramc(asyncread=True)], ["cq", "en", "q"], 40)
    C["RAM falling"] = (base + [ramc(trigger="falling")], ["cq", "en", "q"], 40)
    C["RAM level high"] = ([g if g["id"] != "e" else dict(g, trigger="falling") for g in base] + [ramc(trigger="high", **{"in": {"A": "cq", "Din": "k", "WE": "en"}})], ["cq", "en", "q"], 40)
    C["RAM OE"] = (base + [{"id": "oe", "type": "T Flip-Flop", "in": {"T": "one", "Clk": "clk"}, "out": {"Q": "oeq"}}, ramc(**{"in": {"A": "cq", "Din": "k", "WE": "en", "Clk": "clk", "OE": "oeq"}})], ["cq", "en", "q"], 40)
    return C


def build(gates, outs):
    pins = {}
    d = {"inputs": [], "outputs": outs + ["halt"], "gates": gates + [HALT]}
    c, e = parse(json.dumps(d)); assert not e, e
    err = c.validate(loose=True); assert not err, err
    return c


def fmt(v, w): return "E" * w if v is None else (str(v) if w == 1 else format(v, f"0{w}b"))


def ours(c, outs, maxticks=400):
    st = sim.fresh(c); tick = 0; rows = []; prev = None; w = {o: c.signals()[o] for o in outs}
    while True:
        v, osc = sim.settle(c, {}, st, tick)
        row = [fmt(v[o], w[o]) for o in outs]
        if row != prev: rows.append(row); prev = row
        if v["halt"] == 1 or osc or tick > maxticks: return rows
        tick += 1


def theirs(c, outs):
    open("/tmp/seqcase.circ", "w").write(to_circ(c))
    r = subprocess.run(["java", "-Djava.awt.headless=true", "-jar", "dev/logisim.jar", "-tty", "table,halt", "/tmp/seqcase.circ"], capture_output=True, text=True, timeout=120)
    rows = [l.split("\t") for l in r.stdout.splitlines() if l.strip() and not l.startswith(("INFO", "Picked"))]
    from vibesimulation.layout.engine import LayoutEngine
    lay = LayoutEngine().build(c)
    order = [p.name for p, x, y in sorted(lay.outputs, key=lambda t: (t[2], t[1])) if p.name != "halt"]     # Logisim lists the pins top to bottom
    return [[x[order.index(o)].replace(" ", "") for o in outs] for x in rows if len(x) == len(outs)]


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    bad = 0
    for name, (gates, outs, _) in circuits().items():
        if only and only not in name: continue
        c = build(gates, outs); a = ours(c, outs); b = theirs(c, outs)
        if any("x" in cell.lower() for r in b for cell in r):
            i = next((k for k, r in enumerate(b) if not any("x" in cell.lower() for cell in r)), 0); b = b[i:]
            j = next((k for k, r in enumerate(a) if r == b[0]), 0); a = a[j:]
        ok = a == b
        print(("ok   " if ok else "FAIL ") + name, len(a), "rows")
        if not ok:
            bad += 1; print("  ours  ", a[:14]); print("  logisim", b[:14])
    print("failures", bad)
