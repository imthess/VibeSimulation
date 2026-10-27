"""Run each component in real Logisim (-tty table) and compare with our simulation."""
import subprocess, sys, itertools, json
sys.path.insert(0, "src")
from vibesimulation.core.model import Circuit, IOPin
from vibesimulation.components import ComponentRegistry as R
from vibesimulation.export.logisim import to_circ

def build(t, attrs, skip=()):
    c = R.lookup(t)("c1", attrs)
    ins, outs = [], []
    for p in c.all_ports():
        if p.name in skip: continue
        if p.direction == "in":
            c.ins[p.name] = "i_" + p.name; ins.append(IOPin("i_" + p.name, p.width))
        else:
            c.outs[p.name] = "o_" + p.name
    circ = Circuit(ins, [], [c]); circ.sync()
    circ.outputs = [IOPin("o_" + p.name, p.width) for p in c.out_ports() if p.name not in skip]
    circ.sync()
    return circ

def logisim(circ, tag="s"):
    path = f"dev/{tag}.circ"
    open(path, "w").write(to_circ(circ))
    out = subprocess.run(["java", "-Djava.awt.headless=true", "-jar", "dev/logisim.jar", "-tty", "table", path], capture_output=True, text=True, timeout=120).stdout
    lines = [l.rstrip() for l in out.splitlines() if l.strip() and not l.startswith(("INFO", "Oct", "Picked"))]
    head = lines[0].split()
    return head, [l.split() for l in lines[1:]]

def val(tok):
    try: return int(tok, 2)
    except ValueError: return None   # error / floating

def check(t, attrs, skip=()):
    circ = build(t, attrs, skip)
    errs = circ.validate()
    if errs: return f"validate: {errs}"
    head, rows = logisim(circ)
    tab = circ.table(14)
    names = tab[0] + tab[1] + tab[2]
    mine = {}
    for r in tab[3]:
        d = dict(zip(names, r)); mine[tuple(d[n] for n in tab[0])] = d
    bad = []
    for row in rows:
        d = dict(zip(head, row))
        key = tuple(val(d[n]) for n in tab[0])
        if None in key or key not in mine: continue
        for o in tab[2]:
            got, exp = val(d[o]), mine[key][o]
            if got != exp: bad.append((dict(zip(tab[0], key)), o, "logisim", d[o], "mine", exp))
    return bad[:4] if bad else None

CASES = [("Adder", {"width": 3}, ()), ("Adder", {"width": 3}, ("Cin",)), ("Adder", {"width": 1}, ("Cin", "Cout")), ("Adder", {"width": 1}, ("Cin",)),
 ("Subtractor", {"width": 3}, ()), ("Subtractor", {"width": 3}, ("Bin",)), ("Multiplier", {"width": 3}, ()), ("Multiplier", {"width": 3}, ("Cin",)),
 ("Divider", {"width": 3}, ()), ("Divider", {"width": 3}, ("Upper",)), ("Negator", {"width": 4}, ()),
 ("Comparator", {"width": 3, "mode": "unsigned"}, ()), ("Comparator", {"width": 3, "mode": "signed"}, ()),
 ("Shifter", {"width": 4, "shift": "ll"}, ()), ("Shifter", {"width": 4, "shift": "lr"}, ()), ("Shifter", {"width": 4, "shift": "ar"}, ()), ("Shifter", {"width": 4, "shift": "rl"}, ()), ("Shifter", {"width": 4, "shift": "rr"}, ()),
 ("BitAdder", {"width": 3, "inputs": 3}, ()), ("BitFinder", {"width": 4, "find": "low1"}, ()), ("BitFinder", {"width": 4, "find": "high1"}, ()), ("BitFinder", {"width": 4, "find": "low0"}, ()), ("BitFinder", {"width": 4, "find": "high0"}, ()),
 ("MUX", {"select": 1, "width": 2}, ()), ("MUX", {"select": 2, "width": 1}, ()), ("MUX", {"select": 2, "width": 1}, ("En",)), ("MUX", {"select": 3, "width": 1}, ("En",)),
 ("DEMUX", {"select": 1, "width": 2}, ()), ("DEMUX", {"select": 2, "width": 1}, ("En",)), ("DEMUX", {"select": 3, "width": 1}, ("En",)),
 ("DECODER", {"select": 2}, ()), ("DECODER", {"select": 2}, ("En",)), ("DECODER", {"select": 3}, ("En",)), ("DECODER", {"select": 1}, ("En",)),
 ("ENCODER", {"select": 2}, ("EI", "GS", "EO")), ("ENCODER", {"select": 2}, ()), ("ENCODER", {"select": 3}, ("EI", "EO")), ("ENCODER", {"select": 1}, ("EI", "GS", "EO")),
 ("BITSELECTOR", {"width": 8, "group": 2}, ()), ("BITSELECTOR", {"width": 6, "group": 2}, ()), ("BITEXTENDER", {"in_width": 3, "out_width": 6, "fill": "sign"}, ()),
 ("Splitter", {"widths": [1, 2, 1]}, ()), ("Combiner", {"widths": [2, 1, 1]}, ()), ("BitExtender", {"in_width": 3, "out_width": 6, "fill": "one"}, ()), ("BitExtender", {"in_width": 3, "out_width": 6, "fill": "zero"}, ()), ("BitExtender", {"in_width": 4, "out_width": 2, "fill": "zero"}, ()),
 ("ODDPARITY", {"inputs": 3}, ()), ("EVENPARITY", {"inputs": 3}, ()), ("XOR", {"inputs": 3}, ()), ("XNOR", {"inputs": 3}, ()), ("NAND", {"inputs": 3, "width": 2}, ()), ("NOT", {"width": 3}, ()), ("BUFFER", {}, ()),]
if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for t, a, s in CASES:
        if only and only != t: continue
        try: r = check(t, a, s)
        except Exception as e: r = f"EXC {type(e).__name__}: {e}"
        print("OK  " if r is None else "FAIL", t, a, s, "" if r is None else r, flush=True)
