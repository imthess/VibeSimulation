"""AC and transient comparison with ngspice."""
import sys, os, json, subprocess, tempfile, re, math, cmath
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ngtest import mk, to_spice
from vibesimulation.analog import ac, transient as T
def run(nl, ctl):
    lines = [l for l in to_spice(nl).splitlines() if not l.strip().lower().startswith((".end", ".op", ".dc", ".ac", ".tran"))]
    f = tempfile.NamedTemporaryFile("w", suffix=".cir", delete=False); f.write("\n".join(lines) + "\n.control\n" + ctl + "\n.endc\n.end\n"); f.close()
    return subprocess.run(["ngspice", "-b", f.name], capture_output=True, text=True).stdout
AMP = [{"id":"V1","type":"VoltageSource","value":"12","nodes":["vcc","0"]},{"id":"Vs","type":"VoltageSource","value":"0","ac":"1m","freq":"1k","nodes":["in","0"]},
 {"id":"Cin","type":"Capacitor","value":"10u","nodes":["in","b"]},{"id":"R1","type":"Resistor","value":"47k","nodes":["vcc","b"]},{"id":"R2","type":"Resistor","value":"10k","nodes":["b","0"]},
 {"id":"Rc","type":"Resistor","value":"2.2k","nodes":["vcc","c"]},{"id":"Re","type":"Resistor","value":"1k","nodes":["e","0"]},{"id":"Ce","type":"Capacitor","value":"100u","nodes":["e","0"]},
 {"id":"Q1","type":"NPN","bf":"150","vaf":"80","cbe":"20p","cbc":"4p","nodes":["c","b","e"]},{"id":"Cl","type":"Capacitor","value":"10u","nodes":["c","out"]},{"id":"Rl","type":"Resistor","value":"10k","nodes":["out","0"]}]
bad = 0
# AC
nl = mk(AMP); out = run(nl, "ac dec 4 10 100meg\nprint vm(out) vp(out)")
rows = []
for l in out.splitlines():
    m = re.match(r"\s*\d+\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)", l)
    if m: rows.append(tuple(map(float, m.groups())))
prep = ac.prepare(nl); worst = 0
for f, mag, ph in rows:
    r = ac.point(prep, f)["V"]["out"]
    dm = abs(abs(r) - mag) / (mag + 1e-12); dp = abs(((math.degrees(cmath.phase(r)) - math.degrees(ph) + 180) % 360) - 180)
    worst = max(worst, dm / 5e-3, dp / 0.5)
    if f in (10.0, 1000.0, 1e6, 1e8) or dm > 5e-3: print(f"   f={f:10.4g}  |out| ours {abs(r):.5e} ng {mag:.5e}  phase ours {math.degrees(cmath.phase(r)):8.3f} ng {math.degrees(ph):8.3f}")
print(("ok  " if worst < 1 else "DIFF"), f"BJT amplifier AC, {len(rows)} frequencies, worst {worst:.2f} x tol"); bad += worst >= 1
# transient: same amplifier, 1 kHz sine, 20 mV, compare steady-state waveform
d = json.loads(json.dumps(AMP)); d[1].update({"ac": "20m"}); nt = mk(d)
out = run(nt, "tran 2u 6m\nprint v(out)")
ref = []
for l in out.splitlines():
    m = re.match(r"\s*\d+\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)", l)
    if m: ref.append((float(m.group(1)), float(m.group(2))))
r = T.run(nt, 6e-3, 6000); tt = r["t"]; vo = r["V"]["out"]
import bisect
def at(t):
    k = bisect.bisect_left(tt, t); k = min(max(k, 1), len(tt) - 1); a, b = tt[k - 1], tt[k]; return vo[k - 1] + (vo[k] - vo[k - 1]) * (t - a) / (b - a)
pts = [(t, v) for t, v in ref if t > 4e-3]; err = max(abs(at(t) - v) for t, v in pts); amp = max(abs(v) for _, v in pts)
print(("ok  " if err < 0.03 * amp else "DIFF"), f"BJT amplifier transient (ngspice {len(ref)} points): amplitude {amp*1000:.2f} mV, worst difference {err*1000:.3f} mV"); bad += err >= 0.03 * amp
# transformer with a diode rectifier and capacitor (transient)
TR = [{"id":"V1","type":"VoltageSource","value":"0","ac":"10","freq":"1k","nodes":["a","0"]},{"id":"T1","type":"Transformer","value":"100m","ratio":"2","k":"0.98","nodes":["a","0","s","0"]},
      {"id":"D1","type":"Diode","nodes":["s","o"]},{"id":"C1","type":"Capacitor","value":"10u","nodes":["o","0"]},{"id":"Rl","type":"Resistor","value":"2k","nodes":["o","0"]}]
nt = mk(TR); out = run(nt, "tran 2u 8m\nprint v(o)")
ref = []
for l in out.splitlines():
    m = re.match(r"\s*\d+\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)", l)
    if m: ref.append((float(m.group(1)), float(m.group(2))))
r = T.run(nt, 8e-3, 8000); tt = r["t"]; vo = r["V"]["o"]
pts = [(t, v) for t, v in ref if t > 5e-3]; err = max(abs(at(t) - v) for t, v in pts); amp = max(v for _, v in pts)
print(("ok  " if err < 0.03 * amp else "DIFF"), f"Transformer + rectifier transient: peak {amp:.3f} V, worst difference {err*1000:.1f} mV"); bad += err >= 0.03 * amp
print("DIFFS", bad)
# MOSFET and JFET common-source amplifiers, AC with gate capacitances
def ac_cmp(name, comps, node="out"):
    nl = mk(comps); out = run(nl, f"ac dec 3 100 1g\nprint vm({node}) vp({node})"); rows = []
    for l in out.splitlines():
        m = re.match(r"\s*\d+\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)", l)
        if m: rows.append(tuple(map(float, m.groups())))
    prep = ac.prepare(nl); w = 0
    for f, mag, ph in rows:
        r = ac.point(prep, f)["V"][node]; w = max(w, abs(abs(r) - mag) / (mag + 1e-12) / 5e-3, abs(((math.degrees(cmath.phase(r)) - math.degrees(ph) + 180) % 360) - 180) / 0.5)
    print(("ok  " if rows and w < 1 else "DIFF"), f"{name} AC, {len(rows)} frequencies, worst {w:.2f} x tol"); return not rows or w >= 1
for name, dev_ in (("NMOS common source", {"id": "M1", "type": "NMOS", "vto": "1", "kp": "2m", "lambda": "0.02", "cgs": "5p", "cgd": "1p", "nodes": ["d", "g", "0"]}),
                   ("PMOS common source", None), ("NJFET common source (no gate capacitance)", {"id": "J1", "type": "NJFET", "vto": "-2", "beta": "1m", "lambda": "0.01", "cgs": "0", "cgd": "0", "nodes": ["d", "g", "0"]})):
    if dev_ is None: continue
    comps = [{"id": "V1", "type": "VoltageSource", "value": "10", "nodes": ["vdd", "0"]}, {"id": "Vs", "type": "VoltageSource", "value": "3" if dev_["type"] == "NMOS" else "-1", "ac": "1", "freq": "1k", "nodes": ["g", "0"]},
             {"id": "Rd", "type": "Resistor", "value": "2k", "nodes": ["vdd", "d"]}, {"id": "Rs", "type": "Resistor", "value": "10k", "nodes": ["g", "gg"]}, dev_, {"id": "Co", "type": "Capacitor", "value": "10p", "nodes": ["d", "0"]}]
    comps[-2]["nodes"] = ["d", "gg", "0"]; comps.append({"id": "Rb", "type": "Resistor", "value": "1meg", "nodes": ["gg", "0"]}); bad += ac_cmp(name, comps, "d")
print("TOTAL DIFFS", bad)
