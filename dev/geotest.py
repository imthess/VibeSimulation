"""Compare each component's pins/bounds with real Logisim."""
import sys, subprocess, itertools
sys.path.insert(0, "src"); sys.path.insert(0, "dev")
from geo import HEADER, FOOT
from vibesimulation.components import ComponentRegistry as R
LIB = {"Wiring": 0, "Gates": 1, "Plexers": 2, "Arithmetic": 3, "Input/Output": 5}
def mk(t, attrs, connect=True):
    c = R.lookup(t)(f"{t}1", attrs)
    if connect:
        for p in c.all_ports():
            (c.ins if p.direction == "in" else c.outs)[p.name] = "s_" + p.name
    return c
def run(cases):
    body = ""
    for i, (t, attrs) in enumerate(cases):
        c = mk(t, attrs)
        a = "".join(f'      <a name="{k}" val="{v}"/>\n' for k, v in c.logisim_attrs().items())
        body += f'    <comp lib="{LIB[c.library]}" loc="({300 + 400 * (i % 6)},{300 + 400 * (i // 6)})" name="{c.logisim_name}">\n{a}    </comp>\n'
    open("dev/gt.circ", "w").write(HEADER + body + FOOT)
    out = subprocess.run(["java", "-Djava.awt.headless=true", "-cp", "dev/logisim.jar:dev", "Dump", "dev/gt.circ"], capture_output=True, text=True)
    return out.stdout, out.stderr
def parse(out):
    comps = []
    for l in out.splitlines():
        if l.startswith("COMP"):
            loc = l.split("loc=")[1].split()[0]; bd = l.split("bounds=")[1].split()[0]
            comps.append({"loc": tuple(map(int, loc.split(","))), "bounds": tuple(map(int, bd.split(","))), "ends": []})
        elif l.startswith("  END"):
            p = l.split(); xy = tuple(map(int, p[2].split(","))); d = p[3]; w = int(p[4][2:])
            comps[-1]["ends"].append((xy, d, w))
    return comps
CASES = [("AND", {"inputs": 2}), ("AND", {"inputs": 5}), ("AND", {"inputs": 6}), ("AND", {"inputs": 3, "width": 4}), ("NOT", {}), ("BUFFER", {}), ("NAND", {"inputs": 3}), ("NOR", {}), ("XOR", {"inputs": 4}), ("XNOR", {"inputs": 3}),
 ("ODDPARITY", {"inputs": 3}), ("EVENPARITY", {"inputs": 4}), ("Constant", {"width": 4, "value": 5}), ("Power", {}), ("Ground", {}), 
 ("Splitter", {"widths": [1, 1, 1, 1]}), ("Splitter", {"widths": [2, 2]}), ("Splitter", {"widths": [1, 2, 1]}), ("Combiner", {"widths": [1, 1, 1, 1]}), ("Combiner", {"widths": [3, 1]}), ("BitExtender", {}),
 ] + [("MUX", {"select": s, "width": 4}) for s in (1, 2, 3, 4)] + [("DEMUX", {"select": s, "width": 4}) for s in (1, 2, 3, 4)] + [("DECODER", {"select": s}) for s in (1, 2, 3, 4)] \
  + [("ENCODER", {"select": s}) for s in (1, 2, 3, 4)] + [("BITSELECTOR", {"width": 8, "group": 2}), ("BITSELECTOR", {"width": 8, "group": 1})] \
  + [(t, {"width": 4}) for t in ("Adder", "Subtractor", "Multiplier", "Divider", "Negator", "Comparator", "Shifter", "BitFinder")] + [("Adder", {"width": 1})] \
  + [("BitAdder", {"width": 4, "inputs": n}) for n in (1, 2, 3, 4, 5, 6, 7, 8)] + [("LED", {}), ("SEVENSEG", {}), ("HEXDISPLAY", {})]
if __name__ == "__main__":
    out, err = run(CASES)
    comps = parse(out)
    if len(comps) != len(CASES): print("COUNT", len(comps), len(CASES)); print(err[-800:])
    bad = 0
    for (t, attrs), lc in zip(CASES, comps):
        c = mk(t, attrs); lx, ly = lc["loc"]
        mine = sorted((p.dx, p.dy, p.direction, p.width) for p in c.active_ports())
        real = sorted(((x, y, "in" if d == "in" else "out" if d == "out" else "io", w) for (x, y), d, w in lc["ends"]))
        norm = lambda l: sorted((x, y, "io" if d == "io" else d, w) for x, y, d, w in l)
        m2 = [(x, y, d, w) for x, y, d, w in mine]
        ok = len(m2) == len(real) and all(a[:2] == b[:2] and a[3] == b[3] and (b[2] == "io" or a[2] == b[2]) for a, b in zip(sorted(m2, key=lambda q: q[:2]), sorted(real, key=lambda q: q[:2])))
        bx, by, bw, bh = lc["bounds"]; x0, y0, x1, y1 = c.bounds()
        if (x0, y0, x1 - x0, y1 - y0) != (bx - lx, by - ly, bw, bh) and "-v" in sys.argv:
            print("BOUNDS", t, attrs, "mine", (x0, y0, x1, y1), "real", (bx - lx, by - ly, bx - lx + bw, by - ly + bh))
        if not ok:
            bad += 1; print("PIN MISMATCH", t, attrs); print("  mine", sorted(m2, key=lambda q: q[:2])); print("  real", sorted(real, key=lambda q: q[:2]))
    print("checked", len(CASES), "bad", bad)
