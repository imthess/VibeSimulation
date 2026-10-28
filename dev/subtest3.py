"""Subcircuits: our simulation vs real Logisim (-tty table,halt), including a counter inside a subcircuit and nesting."""
import json, subprocess, sys
sys.path.insert(0, "src")
import vibesimulation.components
from vibesimulation.core.document import Document
from vibesimulation.core import sim

HALT = {"id": "hc", "type": "Counter", "width": 6, "max": 0, "in": {"Clk": "clk"}, "out": {"Carry": "halt"}}
CK = {"id": "ck", "type": "Clock", "out": "clk"}
def fmt(v, w): return str(v) if w == 1 else format(v, f"0{w}b")
HALF = {"inputs": ["a", "b"], "outputs": ["s", "c"], "gates": [{"id": "x", "type": "XOR", "in": ["a", "b"], "out": "s"}, {"id": "n", "type": "AND", "in": ["a", "b"], "out": "c"}]}
FA = {"inputs": ["A", "B", "Cin"], "outputs": ["S", "Cout"], "gates": [
 {"id": "h1", "type": "Circuit", "circuit": "half", "in": {"a": "A", "b": "B"}, "out": {"s": "s1", "c": "c1"}},
 {"id": "h2", "type": "Circuit", "circuit": "half", "in": {"a": "s1", "b": "Cin"}, "out": {"s": "S", "c": "c2"}},
 {"id": "o", "type": "OR", "in": ["c1", "c2"], "out": "Cout"}]}
CNT = {"inputs": ["Clk"], "outputs": [{"name": "Q"}], "gates": [{"id": "c", "type": "Counter", "width": 3, "in": {"Clk": "Clk"}, "out": {"Q": "Q"}}]}
WRAP = {"inputs": ["Clk"], "outputs": ["Q"], "gates": [{"id": "k", "type": "Circuit", "circuit": "cnt", "in": {"Clk": "Clk"}, "out": {"Q": "Q"}}]}
CASES = {
 "full adder": ({"half": HALF, "fa": FA}, {"inputs": [], "outputs": ["S", "Cout", "halt"], "gates": [CK, HALT,
   {"id": "c", "type": "Counter", "width": 3, "in": {"Clk": "clk"}, "out": {"Q": "q"}},
   {"id": "sp", "type": "Splitter", "widths": [1, 1, 1], "in": {"In": "q"}, "out": {"Out0": "q0", "Out1": "q1", "Out2": "q2"}},
   {"id": "u", "type": "Circuit", "circuit": "fa", "in": {"A": "q0", "B": "q1", "Cin": "q2"}, "out": {"S": "S", "Cout": "Cout"}}]}, ["S", "Cout"]),
 "counter inside": ({"cnt": CNT}, {"inputs": [], "outputs": ["q", "halt"], "gates": [CK, HALT, {"id": "u", "type": "Circuit", "circuit": "cnt", "in": {"Clk": "clk"}, "out": {"Q": "q"}}]}, ["q"]),
 "nested + two copies": ({"cnt": CNT, "wrap": WRAP}, {"inputs": [], "outputs": ["q1", "q2", "halt"], "gates": [CK, HALT,
   {"id": "u", "type": "Circuit", "circuit": "wrap", "in": {"Clk": "clk"}, "out": {"Q": "q1"}},
   {"id": "v", "type": "Circuit", "circuit": "cnt", "in": {"Clk": "clk"}, "out": {"Q": "q2"}}]}, ["q1", "q2"]),
}

def make(subs, main):
    d = Document()
    first = True
    for n, j in subs.items():
        if first: d.load_text(json.dumps(j)); d.rename_circuit("main", n); first = False
        else: d.add_circuit(n, json.dumps(j))
    d.add_circuit("main", json.dumps(main))
    assert d.valid, (d.errors, d.layout_error)
    return d

def ours(d, outs):
    c = d.circuit; st = sim.fresh(c); tick = 0; rows = []; prev = None; w = {o: c.signals()[o] for o in outs}
    while True:
        v, osc = sim.settle(c, {}, st, tick)
        row = [fmt(v[o], w[o]) for o in outs]
        if row != prev: rows.append(row); prev = row
        if v["halt"] == 1 or osc or tick > 400: return rows
        tick += 1

def theirs(d, outs):
    open("/tmp/subcase.circ", "w").write(d.circ_text())
    r = subprocess.run(["java", "-Djava.awt.headless=true", "-jar", "dev/logisim.jar", "-tty", "table,halt", "/tmp/subcase.circ"], capture_output=True, text=True, timeout=120)
    rows = [l.split("\t") for l in r.stdout.splitlines() if l.strip() and not l.startswith(("INFO", "Picked"))]
    order = [p.name for p, x, y in sorted(d.layout.outputs, key=lambda t: (t[2], t[1])) if p.name != "halt"]
    return [[x[order.index(o)] for o in outs] for x in rows if len(x) == len(order)], r.stderr[-300:] if not rows else ""

bad = 0
for name, (subs, main, outs) in CASES.items():
    d = make(subs, main); a = ours(d, outs); b, err = theirs(d, outs)
    ok = a == b; print(("ok   " if ok else "FAIL ") + name, len(a), "rows")
    if not ok: bad += 1; print("  ours  ", a[:12]); print("  logisim", b[:12], err)
print("failures", bad)
