"""Compare our solver with ngspice on exported SPICE netlists (operating point)."""
import sys, os, json, subprocess, tempfile, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from vibesimulation.analog.netlist import parse, to_spice
def mk(c):
    nl, e = parse(json.dumps({"components": c})); assert not e, e; return nl
def ng_op(nl):
    txt = to_spice(nl); lines = [l for l in txt.splitlines() if not l.strip().lower().startswith((".end", ".op", ".dc", ".ac", ".tran"))]
    nets = sorted({n for p in nl.parts for n in p.nodes if str(n) not in ("0",)})
    deck = "\n".join(lines) + "\n.control\nop\nprint " + " ".join(f"v({n})" for n in nets) + "\n.endc\n.end\n"
    f = tempfile.NamedTemporaryFile("w", suffix=".cir", delete=False); f.write(deck); f.close()
    out = subprocess.run(["ngspice", "-b", f.name], capture_output=True, text=True).stdout
    vals = {}
    for m in re.finditer(r"v\(([^)]+)\)\s*=\s*([-+0-9.eE]+)", out): vals[m.group(1).lower()] = float(m.group(2))
    return vals, deck, out
CASES = {
 "BJT CE bias": [{"id":"V1","type":"VoltageSource","value":"12","nodes":["vcc","0"]},{"id":"R1","type":"Resistor","value":"47k","nodes":["vcc","b"]},{"id":"R2","type":"Resistor","value":"10k","nodes":["b","0"]},{"id":"Rc","type":"Resistor","value":"2.2k","nodes":["vcc","c"]},{"id":"Re","type":"Resistor","value":"1k","nodes":["e","0"]},{"id":"Q1","type":"NPN","nodes":["c","b","e"]}],
 "BJT with Early": [{"id":"V1","type":"VoltageSource","value":"10","nodes":["vcc","0"]},{"id":"Rb","type":"Resistor","value":"100k","nodes":["vcc","b"]},{"id":"Rc","type":"Resistor","value":"1k","nodes":["vcc","c"]},{"id":"Q1","type":"NPN","vaf":"50","bf":"150","nodes":["c","b","0"]}],
 "PNP": [{"id":"V1","type":"VoltageSource","value":"10","nodes":["vcc","0"]},{"id":"Rb","type":"Resistor","value":"100k","nodes":["b","0"]},{"id":"Rc","type":"Resistor","value":"1k","nodes":["c","0"]},{"id":"Q1","type":"PNP","nodes":["c","b","vcc"]}],
 "NMOS sat": [{"id":"V1","type":"VoltageSource","value":"10","nodes":["vdd","0"]},{"id":"Vg","type":"VoltageSource","value":"3","nodes":["g","0"]},{"id":"Rd","type":"Resistor","value":"1k","nodes":["vdd","d"]},{"id":"M1","type":"NMOS","vto":"1","kp":"1m","lambda":"0.02","nodes":["d","g","0"]}],
 "NMOS triode": [{"id":"V1","type":"VoltageSource","value":"10","nodes":["vdd","0"]},{"id":"Vg","type":"VoltageSource","value":"8","nodes":["g","0"]},{"id":"Rd","type":"Resistor","value":"2k","nodes":["vdd","d"]},{"id":"M1","type":"NMOS","vto":"1","kp":"2m","nodes":["d","g","0"]}],
 "PMOS": [{"id":"V1","type":"VoltageSource","value":"10","nodes":["vdd","0"]},{"id":"Vg","type":"VoltageSource","value":"6","nodes":["g","0"]},{"id":"Rd","type":"Resistor","value":"1k","nodes":["d","0"]},{"id":"M1","type":"PMOS","vto":"-1","kp":"1m","lambda":"0.01","nodes":["d","g","vdd"]}],
 "NJFET": [{"id":"V1","type":"VoltageSource","value":"12","nodes":["vdd","0"]},{"id":"Rd","type":"Resistor","value":"2k","nodes":["vdd","d"]},{"id":"Rs","type":"Resistor","value":"1k","nodes":["s","0"]},{"id":"Rg","type":"Resistor","value":"1meg","nodes":["g","0"]},{"id":"J1","type":"NJFET","vto":"-2","beta":"1m","nodes":["d","g","s"]}],
 "CMOS inverter mid": [{"id":"V1","type":"VoltageSource","value":"5","nodes":["vdd","0"]},{"id":"Vi","type":"VoltageSource","value":"2.5","nodes":["in","0"]},{"id":"Mp","type":"PMOS","vto":"-1","kp":"2m","nodes":["out","in","vdd"]},{"id":"Mn","type":"NMOS","vto":"1","kp":"2m","nodes":["out","in","0"]},{"id":"Rl","type":"Resistor","value":"1meg","nodes":["out","0"]}],
}
if __name__ == "__main__":
    bad = 0
    for name, c in CASES.items():
        nl = mk(c); v, _ = nl.solve(); ng, deck, out = ng_op(nl)
        if not ng: print("NGSPICE gave nothing for", name); print(deck); print(out[-600:]); bad += 1; continue
        worst = max(abs(v[n] - ng[n.lower()]) / (2e-3 + 5e-4 * abs(ng[n.lower()])) for n in ng if n in v)      # worst diff in units of the allowed tolerance
        print(f"{'ok  ' if worst < 1 else 'DIFF'} {name:20s} worst {worst:.2f} x tol  " + "  ".join(f"{n}: {v[n]:.4f} vs {ng[n]:.4f}" for n in sorted(ng) if n in v and n not in ("vcc","vdd")))
        bad += worst >= 1
    print("DIFFS", bad)
