"""Import a file whose subcircuit uses Logisim's newer box (width taken from the wires)."""
import sys, subprocess, re
sys.path.insert(0, "src")
import vibesimulation.components
from vibesimulation.export.logisim import HEADER
from vibesimulation.imports.logisim_in import parse_project
head = HEADER.replace("@MAIN@", "main").split('  <circuit name="main">')[0] if '<circuit name="main">' in HEADER else HEADER.replace("@MAIN@", "main")
def pin(x, y, label, out): return f'    <comp lib="0" loc="({x},{y})" name="Pin">\n' + ('      <a name="facing" val="west"/>\n      <a name="output" val="true"/>\n' if out else '') + f'      <a name="label" val="{label}"/>\n    </comp>\n'
bad = 0
for L in (1, 8, 12):
    lab = lambda c: c * L
    sub = '  <circuit name="sub">\n    <a name="circuit" val="sub"/>\n    <a name="appearance" val="evolution"/>\n' + pin(100, 100, lab("a"), 0) + pin(100, 140, lab("b"), 0) + pin(300, 100, lab("x"), 1) + '  </circuit>\n'
    probe = '  <circuit name="main">\n    <a name="circuit" val="main"/>\n    <comp loc="(500,300)" name="sub"/>\n  </circuit>\n'
    open("/tmp/ev.circ", "w").write(head + sub + probe + "</project>\n")
    out = subprocess.run(["java", "-Djava.awt.headless=true", "-cp", "dev/logisim.jar:dev", "Dump", "/tmp/ev.circ"], capture_output=True, text=True).stdout
    ends = [(int(a), int(b), k) for a, b, k in re.findall(r"END \d+ (-?\d+),(-?\d+) (in|out)", out)][-3:]
    main = '  <circuit name="main">\n    <a name="circuit" val="main"/>\n    <comp loc="(500,300)" name="sub"/>\n'
    for dx, dy, k in ends:
        px, py = 500 + dx, 300 + dy
        if k == "in": main += pin(px - 100, py, "i%d" % dy, 0) + f'    <wire from="({px-100},{py})" to="({px},{py})"/>\n'
        else: main += pin(px + 100, py, "o", 1) + f'    <wire from="({px},{py})" to="({px+100},{py})"/>\n'
    main += "  </circuit>\n"
    open("/tmp/ev2.circ", "w").write(head + sub + main + "</project>\n")
    circs, m, notes = parse_project(open("/tmp/ev2.circ").read())
    u = next(c for c in circs["main"].components if c.type_name == "Circuit")
    ok = len(u.ins) == 2 and len(u.outs) == 1
    print(("ok  " if ok else "FAIL"), L, ends, u.ins, u.outs, notes)
    bad += not ok
print("failures", bad)
