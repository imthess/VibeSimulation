"""Big designs stay usable: load within a time limit, rough layout flagged, export refused cleanly, results correct."""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import perf
from vibesimulation.components import load_all; load_all()
from vibesimulation.core.document import Document
bad = 0
def ok(c, m):
    global bad
    if not c: bad += 1
    print("ok  " if c else "FAIL", m)
for nm, n, lim in (("chain", 1200, 10), ("tree", 1200, 10), ("tree", 100, 20)):
    d = Document(); t = time.time(); d.load_text(getattr(perf, nm)(n)); dt = time.time() - t
    ok(d.valid and dt < lim, f"{nm} {n}: valid, {dt:.1f}s < {lim}s")
    ref = d.circuit.simulate({"A": 1, "B": 1} if nm == "chain" else {f"I{i}": 1 for i in range(16)})
    d.set_inputs({"A": 1, "B": 1} if nm == "chain" else {f"I{i}": 1 for i in range(16)})
    ok(d.vals.get("Y") == ref["Y"], f"{nm} {n}: results match a direct simulation")
    if d.layout.rough:
        try: d.circ_text(); ok(False, "rough layout cannot be exported")
        except ValueError as e: ok("too large" in str(e), "export of a rough layout is refused with a message")
sys.exit(1 if bad else 0)
