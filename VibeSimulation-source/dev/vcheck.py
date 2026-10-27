"""Compare an elaborated circuit with iverilog, for combinational and clocked modules."""
import random, subprocess, sys, tempfile
sys.path.insert(0, "src")
import vibesimulation.components
from vibesimulation.verilog.elab import elaborate
from vibesimulation.core import sim, project


def compare(src, top, nvec=60, seed=1, clk="clk", resets=(), quiet=False):
    r = random.Random(seed)
    circs, _, ctx = elaborate(src, top)
    lib = dict(circs)
    from vibesimulation.core import serializer
    project.set_project({n: serializer.dumps(c) for n, c in circs}, top)
    circ = lib[top]
    errs = circ.validate()
    assert not errs, errs
    ins = [(p.name, p.width) for p in circ.inputs]; outs = [(p.name, p.width) for p in circ.outputs]
    data = [(n, w) for n, w in ins if n != clk and n not in [x for x, _ in resets]]
    seq = any(n == clk for n, _ in ins)
    steps = []
    for i in range(nvec):
        v = {n: r.randrange(1 << w) for n, w in data}
        for n, active in resets:                      # reset asserted for the first 2 steps and rarely later
            v[n] = active if (i < 2 or r.random() < .08) else 1 - active
        steps.append(v)
    tb = "module tb;\n"
    for n, w in ins: tb += f"  reg [{w-1}:0] {n};\n"
    for n, w in outs: tb += f"  wire [{w-1}:0] {n};\n"
    tb += f"  {top} uut__({', '.join('.'+n+'('+n+')' for n,_ in ins+outs)});\n  initial begin\n"
    if seq: tb += f"    {clk} = 0;\n"
    disp = lambda: "    $display(\"" + " ".join("%0d" for _ in outs) + "\", " + ", ".join(n for n, _ in outs) + ");\n"
    for v in steps:
        tb += "".join(f"    {n} = {w}'d{v[n]};\n" for n, w in ins if n in v)
        tb += "    #1;\n" + disp()
        if seq: tb += f"    {clk} = 1; #1;\n" + disp() + f"    {clk} = 0; #1;\n" + disp()
    tb += "    $finish;\n  end\nendmodule\n"
    d = tempfile.mkdtemp(); open(d + "/t.v", "w").write(src + "\n" + tb)
    p = subprocess.run(["iverilog", "-g2005", "-o", d + "/x", d + "/t.v"], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    lines = subprocess.run(["vvp", d + "/x"], capture_output=True, text=True).stdout.strip().splitlines()
    st = sim.fresh(circ); k = 0; bad = 0; checked = 0; tick = 0
    for v in steps:
        phases = [({**v, clk: 0} if seq else v)] + ([{**v, clk: 1}, {**v, clk: 0}] if seq else [])
        for ph in phases:
            tick += 1
            vals, osc = sim.settle(circ, {n: ph.get(n, 0) for n, _ in ins}, st, tick)
            exp = lines[k].split(); k += 1
            for (n, w), x in zip(outs, exp):
                if any(ch in x.lower() for ch in "xz"): continue
                checked += 1
                if vals[n] != int(x):
                    bad += 1
                    if bad < 4 and not quiet: print(f"  MISMATCH step {k} {n}: iverilog {x} ours {vals[n]}  inputs {ph}")
    return bad, checked
