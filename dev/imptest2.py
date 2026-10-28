"""Hand-made Logisim circuits (rotated gates, sizes, defaults, tunnels): real Logisim vs our import."""
import sys, subprocess, itertools
sys.path.insert(0, "src"); sys.path.insert(0, "dev")
from vibesimulation.components import load_all
load_all()
from vibesimulation.core.serializer import parse
from vibesimulation.export.logisim import HEADER, FOOTER
from vibesimulation.imports.logisim_in import circ_to_json
from semtest import val

def pin(x, y, label, out=False, width=1):
    f = ' <a name="facing" val="west"/>' if out else ""
    return f'<comp lib="0" loc="({x},{y})" name="Pin">{f}<a name="label" val="{label}"/>' + ('<a name="output" val="true"/>' if out else '<a name="tristate" val="false"/>') + (f'<a name="width" val="{width}"/>' if width != 1 else "") + '</comp>\n'
def comp(lib, x, y, name, **a):
    return f'<comp lib="{lib}" loc="({x},{y})" name="{name}">' + "".join(f'<a name="{k}" val="{v}"/>' for k, v in a.items()) + '</comp>\n'
def wire(a, b): return f'<wire from="({a[0]},{a[1]})" to="({b[0]},{b[1]})"/>\n'
def run(name, body, ins, outs):
    open("dev/h.circ", "w").write(HEADER + body + FOOTER)
    out = subprocess.run(["java", "-Djava.awt.headless=true", "-jar", "dev/logisim.jar", "-tty", "table", "dev/h.circ"], capture_output=True, text=True, timeout=120).stdout
    lines = [l.rstrip() for l in out.splitlines() if l.strip() and not l.startswith(("INFO", "Oct", "Picked"))]
    head = lines[0].split(); rows = [dict(zip(head, l.split())) for l in lines[1:]]
    js, notes = circ_to_json(open("dev/h.circ").read())
    c, errs = parse(js); errs = errs or c.validate()
    if errs: print("FAIL", name, errs, js); return 1
    t = c.table(12); names = t[0] + t[1] + t[2]; bad = 0
    mine = {tuple(r[names.index(n)] for n in t[0]): {o: r[names.index(o)] for o in t[2]} for r in t[3]}
    for r in rows:
        key = tuple(val(r[n]) for n in ins)
        if None in key: continue
        for o in outs:
            if val(r[o]) != mine[key][o]: bad += 1
    print("ok  " if not bad else "FAIL", name, f"({len(rows)} rows, notes {notes})"); return bad

fails = 0
# 1) gates in all four directions, sizes, input counts, a negated input
for name, kind in (("AND Gate", "AND"), ("NOR Gate", "NOR"), ("XOR Gate", "XOR"), ("NAND Gate", "NAND")):
    for facing in ("east", "west", "north", "south"):
        for size in (30, 50, 70):
            n = 3
            from vibesimulation.imports.logisim_in import gate_inputs
            ps = gate_inputs(name, {"facing": facing, "size": size, "inputs": n})
            gx, gy = 600, 600
            body = comp(1, gx, gy, name, facing=facing, size=size, inputs=n, **({"xor": "odd"} if "XOR" in name else {}))
            # pins placed 100 units away from each input, wired straight
            for k, (dx, dy) in enumerate(ps):
                ux = 0 if dx == 0 else (1 if dx > 0 else -1); uy = 0 if dy == 0 else (1 if dy > 0 else -1)
                if abs(dx) >= abs(dy): far = (gx + dx + ux * 100, gy + dy)
                else: far = (gx + dx, gy + dy + uy * 100)
                body += pin(*far, f"I{k}") + wire(far, (gx + dx, gy + dy))
            ox, oy = {"east": (1, 0), "west": (-1, 0), "north": (0, -1), "south": (0, 1)}[facing]
            far = (gx + ox * 100, gy + oy * 100); body += pin(*far, "Y", out=True) + wire((gx, gy), far)
            fails += run(f"{name} {facing} size {size}", body, ["I0", "I1", "I2"], ["Y"])
# 2) a default-size NOT, Buffer, tunnel and constants
body = pin(100, 100, "A") + comp(1, 200, 100, "NOT Gate") + wire((100, 100), (170, 100)) + comp(0, 260, 100, "Tunnel", label="t", facing="west") + wire((200, 100), (260, 100))
body += comp(0, 300, 200, "Tunnel", label="t") + comp(1, 400, 200, "Buffer") + wire((300, 200), (380, 200)) + pin(500, 200, "Y", out=True) + wire((400, 200), (500, 200))
fails += run("NOT + tunnel + buffer", body, ["A"], ["Y"])
print("total failures", fails)
