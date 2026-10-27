"""Import sequential circuits drawn in Logisim's newer look (the default) and check them against the real Logisim."""
import subprocess, sys
sys.path.insert(0, "src"); sys.path.insert(0, "dev")
from vibesimulation.components.registry import ComponentRegistry as R
from vibesimulation.export.logisim import HEADER, FOOTER
from vibesimulation.imports.logisim_in import parse_circ
from vibesimulation.core import sim
import seqtest as T


def comp(lib, x, y, name, **a):
    s = "".join(f'      <a name="{k}" val="{v}"/>\n' for k, v in a.items())
    return f'    <comp lib="{lib}" loc="({x},{y})" name="{name}">\n{s}    </comp>\n'


def wire(*pts):
    return "".join(f'    <wire from="({a[0]},{a[1]})" to="({b[0]},{b[1]})"/>\n' for a, b in zip(pts, pts[1:]))


def pin(x, y, label, out=True, **a):
    d = {"facing": "west", "label": label, "output": "true"} if out else {"label": label}
    d.update(a)
    return comp(0, x, y, "Pin", **d)


def circuit_b():
    b = comp(0, 100, 100, "Clock") + comp(4, 300, 100, "Counter", width=1) + comp(4, 300, 350, "Register", width=1)
    b += comp(4, 700, 100, "Counter", width=6, max="0x3f", ongoal="wrap")
    b += wire((100, 100), (200, 100)) + wire((200, 100), (200, 420)) + wire((200, 180), (300, 180)) + wire((200, 420), (300, 420))
    b += wire((150, 100), (150, 40), (640, 40), (640, 180), (700, 180))
    b += wire((480, 220), (560, 220)) + wire((520, 220), (520, 300), (260, 300), (260, 380), (300, 380))
    b += wire((360, 380), (440, 380)) + wire((890, 210), (960, 210)) + wire((890, 150), (960, 150))
    b += pin(560, 220, "cq") + pin(440, 380, "rq") + pin(960, 150, "halt")
    return HEADER + b + FOOTER


def run_logisim(circ):
    open("/tmp/impseq.circ", "w").write(circ)
    r = subprocess.run(["java", "-Djava.awt.headless=true", "-jar", "dev/logisim.jar", "-tty", "table,halt", "/tmp/impseq.circ"], capture_output=True, text=True, timeout=120)
    return [l.split("\t") for l in r.stdout.splitlines() if l.strip() and not l.startswith(("INFO", "Picked"))]


if __name__ == "__main__":
    circ = circuit_b(); theirs = run_logisim(circ)
    c, notes = parse_circ(circ); print("notes", notes); print("errors", c.validate(loose=True))
    outs = [p.name for p in c.outputs if p.name != "halt"]
    ours = T.ours(c, outs); print(outs, len(ours), len(theirs))
    # Logisim lists pins top to bottom; ours in our list order -> reorder by y: cq (y220) is below halt; rq (380) below cq
    theirs = [[x[0], x[1]] for x in theirs]
    print("ours  ", ours[:6]); print("theirs", theirs[:6])
    print("MATCH" if ours == theirs else "DIFFERENT")


def geometry_check():
    """Our evolution pin positions against what the real Logisim reports (Dump)."""
    import re
    cases = [("D Flip-Flop", {}), ("T Flip-Flop", {}), ("J-K Flip-Flop", {}), ("S-R Flip-Flop", {}), ("Register", {"width": 8}),
             ("Counter", {"width": 1}), ("Counter", {"width": 4}), ("Counter", {"width": 16}), ("Counter", {"width": 32}),
             ("Shift Register", {"width": 2, "length": 4, "parallel": "true"}), ("Shift Register", {"width": 1, "length": 1, "parallel": "true"})]
    body = "".join(comp(4, 200, 100 + 400 * i, n, **a) for i, (n, a) in enumerate(cases))
    open("/tmp/geo.circ", "w").write(HEADER + body + FOOTER)
    out = subprocess.run(["java", "-Djava.awt.headless=true", "-cp", "dev/logisim.jar:dev", "Dump", "/tmp/geo.circ"], capture_output=True, text=True).stdout
    blocks = out.split("COMP ")[1:]; bad = 0
    for (n, a), blk in zip(cases, blocks):
        theirs = sorted((tuple(map(int, m.group(1).split(","))), m.group(2)) for m in re.finditer(r"END \d+ (-?\d+,-?\d+) (in|out)", blk))
        c = R.lookup(n)("x", {k: (v if v != "true" else True) for k, v in a.items()})
        ev = c.evolution_ports(); mine = sorted((ev[p.name], p.direction) for p in c.all_ports() if p.name in ev)
        ok = [(p, d) for p, d in theirs] == [(p, "in" if d == "in" else "out") for p, d in mine]
        print(("ok   " if ok else "FAIL ") + n, a); bad += not ok
        if not ok: print("  theirs", theirs); print("  mine  ", mine)
    return bad


def rom_roundtrip():
    """ROM contents: our export -> Logisim runs it; our .circ import brings the contents back."""
    import json
    from vibesimulation.core.serializer import parse
    from vibesimulation.export.logisim import to_circ
    rom = {str(i): (i * 7 + 3) % 16 for i in range(8)}; rom["5"] = 0
    g = [T.ck(), {"id": "c", "type": "Counter", "width": 3, "in": {"Clk": "clk"}, "out": {"Q": "a"}},
         {"id": "r", "type": "ROM", "addr": 3, "width": 4, "contents": rom, "in": {"A": "a"}, "out": {"D": "d"}}]
    c = T.build(g, ["a", "d"]); circ = to_circ(c)
    back, notes = parse_circ(circ); r = next(x for x in back.components if x.type_name == "ROM")
    ok = {str(k): v for k, v in r.attrs["contents"].items()} == {k: v for k, v in rom.items() if v}
    print(("ok   " if ok else "FAIL ") + "ROM contents survive export + import", notes); return not ok
