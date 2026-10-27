"""Circuits made from the newer Verilog features: circuit -> Verilog -> circuit keeps the behaviour."""
import sys
sys.path.insert(0, "src")
import vibesimulation.components
from vibesimulation.verilog.elab import elaborate
from vibesimulation.verilog.emit import circuit_to_verilog, equivalent
from vibesimulation.verilog.lexer import VError
ns = {}
code = open("dev/vtest_adv.py").read().split("bad_total = 0")[0].replace("from vcheck import compare", "")
exec(code, ns)
bad = 0
for name, (src, top, rs) in ns["T"].items():
    if src.count("endmodule") > 1: continue
    circs, t, _ = elaborate(src, top); circ = dict(circs)[t]
    try:
        text = circuit_to_verilog(t, circ)
        circs2, _, _ = elaborate(text, t); new = dict(circs2)[t]
        ok = equivalent(circ, new, n=200)
    except VError as e: ok = False; text = f"{e.msg} line {e.line}"
    if not ok: bad += 1; print("BAD", name); print(text[:600])
    else: print("ok ", name)
print("failures:", bad)
