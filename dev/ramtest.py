"""RAM pin positions (both looks) against real Logisim, and RAM surviving export -> import."""
import sys, json, re, subprocess, itertools
sys.path.insert(0, "src")
import vibesimulation.components
from vibesimulation.components.registry import ComponentRegistry as R
from vibesimulation.export.logisim import HEAD, _open
from vibesimulation.imports.logisim_in import parse_circ
from vibesimulation.core.serializer import parse
head = HEAD.replace("@MAIN@", "main")
bad = 0
for w, extra, look in itertools.product((1, 8), ({}, {"clearpin": "true"}, {"trigger": "high"}, {"trigger": "falling", "asyncread": "true"}), ("classic", "evo")):
    attrs = {"dataWidth": w, **extra}
    if look == "classic": attrs["appearance"] = "classic"
    a = "".join(f'      <a name="{k}" val="{v}"/>\n' for k, v in attrs.items())
    open("/tmp/r.circ", "w").write(head + _open("main") + f'    <comp lib="4" loc="(500,300)" name="RAM">\n{a}    </comp>\n  </circuit>\n</project>\n')
    out = subprocess.run(["java", "-Djava.awt.headless=true", "-cp", "dev/logisim.jar:dev", "Dump", "/tmp/r.circ"], capture_output=True, text=True).stdout
    ends = sorted((int(x), int(y), k) for x, y, k in re.findall(r"END \d+ (-?\d+),(-?\d+) (in|out)", out))
    c = R.create("RAM", "m", {"width": w, "trigger": extra.get("trigger", "rising"), "clearpin": extra.get("clearpin") == "true", "asyncread": extra.get("asyncread") == "true"})
    ports = c.evolution_ports() if look == "evo" else {p.name: (p.dx, p.dy) for p in c.all_ports()}
    mine = sorted((dx, dy, "out" if n == "Dout" else "in") for n, (dx, dy) in ports.items())
    ok = ends == mine; bad += not ok
    print(("ok  " if ok else "FAIL"), w, extra, look, "" if ok else (ends, mine))
# export -> import
d = {"inputs": [{"name": "a", "width": 4}, {"name": "d", "width": 8}, "we", "clk", "oe"], "outputs": [{"name": "q", "width": 8}], "gates": [
    {"id": "m", "type": "RAM", "addr": 4, "asyncread": True, "readbehav": "beforewrite", "in": {"A": "a", "Din": "d", "WE": "we", "Clk": "clk", "OE": "oe"}, "out": {"Dout": "q"}}]}
from vibesimulation.export.logisim import to_circ
c, e = parse(json.dumps(d)); back, notes = parse_circ(to_circ(c)); m = next(x for x in back.components if x.type_name == "RAM")
ok = m.attrs["addr"] == 4 and m.attrs["asyncread"] and m.attrs["readbehav"] == "beforewrite" and len(m.ins) == 5 and len(m.outs) == 1
print(("ok  " if ok else "FAIL"), "export/import", m.attrs, m.ins, notes); bad += not ok
print("failures", bad)
