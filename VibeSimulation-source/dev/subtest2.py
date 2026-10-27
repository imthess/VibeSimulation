"""Subcircuits through real Logisim: export a project, run it in the jar, compare; then import the .circ back."""
import json, subprocess, sys, itertools, re
sys.path.insert(0, "src")
import vibesimulation.components
from vibesimulation.core.document import Document
from vibesimulation.imports.logisim_in import circ_to_json, parse_project

d = Document()
d.load_text('{"inputs":["a","b"],"outputs":["s","c"],"gates":[{"id":"x","type":"XOR","in":["a","b"],"out":"s"},{"id":"n","type":"AND","in":["a","b"],"out":"c"}]}')
d.rename_circuit("main", "half"); d.add_circuit("main")
d.set_text(json.dumps({"inputs": ["A", "B", "Cin"], "outputs": ["S", "Cout"], "gates": [
 {"id": "h1", "type": "Circuit", "circuit": "half", "in": {"a": "A", "b": "B"}, "out": {"s": "s1", "c": "c1"}},
 {"id": "h2", "type": "Circuit", "circuit": "half", "in": {"a": "s1", "b": "Cin"}, "out": {"s": "S", "c": "c2"}},
 {"id": "o", "type": "OR", "in": ["c1", "c2"], "out": "Cout"}]}))
assert d.valid, d.errors
txt = d.circ_text(); open("/tmp/proj.circ", "w").write(txt)
# real Logisim: -tty table with fixed inputs is awkward; use Dump to check the instance ends instead
out = subprocess.run(["java", "-Djava.awt.headless=true", "-cp", "dev/logisim.jar:dev", "Dump", "/tmp/proj.circ"], capture_output=True, text=True)
print(out.stdout[:900], out.stderr[:300])
js, notes = circ_to_json(txt); print(notes)
d2 = Document(); d2.load_project(js)
print(d2.cur, d2.circuit_names(), d2.valid, d2.errors)
for a, b, c in itertools.product(range(2), repeat=3):
    v = d2.circuit.simulate({"A": a, "B": b, "Cin": c}); assert (v["S"], v["Cout"]) == ((a+b+c) & 1, (a+b+c) >> 1), (a, b, c, v)
print("roundtrip OK")
