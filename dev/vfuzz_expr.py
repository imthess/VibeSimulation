"""Random Verilog expressions: the circuit we build must agree with iverilog on every vector."""
import random, subprocess, sys, os, tempfile
sys.path.insert(0, "src")
import vibesimulation.components
from vibesimulation.verilog.elab import elaborate
from vibesimulation.verilog.lexer import VError
from vibesimulation.core import sim

REASONS = {}
IN = [("a", 8, False), ("b", 5, False), ("c", 4, True), ("d", 1, False), ("e", 12, True), ("f", 3, False), ("g", 40, False), ("h", 64, True)]
WIDE = len(sys.argv) > 3 and sys.argv[3] == "wide"
if not WIDE: IN = IN[:6]


def sized(r):
    k = r.random()
    if k < .5:
        n, w, s = r.choice(IN); return n
    if k < .7: w = r.choice([1, 2, 4]); return f"{w}'d{r.randrange(1 << w)}"
    n, w, s = r.choice(IN)
    if w == 1: return n
    i = r.randrange(w); return f"{n}[{r.randrange(i, w)}:{i}]"


def gen(r, depth):
    if depth <= 0 or r.random() < 0.18:
        k = r.random()
        if k < 0.45:
            n, w, s = r.choice(IN); return n
        if k < 0.6: return str(r.choice([0, 1, 2, 3, 5, 7, 15, 100, 255]))
        if k < 0.7: w = r.choice([1, 2, 4, 6, 9]); return f"{w}'d{r.randrange(1 << w)}"
        if k < 0.78: w = r.choice([3, 5, 8]); return f"{w}'sd{r.randrange(1 << (w - 1))}"
        if k < 0.9:
            n, w, s = r.choice(IN)
            if w == 1: return n
            i = r.randrange(w); return f"{n}[{i}]" if r.random() < .5 else f"{n}[{r.randrange(i, w)}:{i}]"
        return f"{r.choice(['a','e'])}[{r.choice(['b','f','d'])}]" if False else "a[f]"
    k = r.random(); sub = lambda: gen(r, depth - 1)
    if k < 0.3: return f"({sub()} {r.choice(['+','-','*','&','|','^','~^'])} {sub()})"
    if k < 0.4: return f"({sub()} {r.choice(['==','!=','<','<=','>','>=','===','!=='])} {sub()})"
    if k < 0.47: return f"({sub()} {r.choice(['&&','||'])} {sub()})"
    if k < 0.57: return f"({sub()} {r.choice(['<<','>>','<<<','>>>'])} {r.choice(['d','f','b','c[1:0]','2','1','0','3','9','40'])})"
    if k < 0.65: return f"({r.choice(['-','~','!','+','&','|','^','~&','~|','~^'])}{sub()})"
    if k < 0.75: return f"({sub()} ? {sub()} : {sub()})"
    if k < 0.82: return "{" + ", ".join(sized(r) for _ in range(r.randint(2, 3))) + "}"
    if k < 0.86: return f"{{{r.randint(1,3)}{{{sized(r)}}}}}"
    if k < 0.92: return f"({sub()} {r.choice(['/','%'])} ({sub()} | 1))"
    if k < 0.96: return f"$signed({sub()})"
    return f"$unsigned({sub()})"


def run_case(seed, nout=6, depth=3, nvec=24):
    r = random.Random(seed); outs = []
    for i in range(nout): outs.append((f"y{i}", r.choice([1, 3, 4, 8, 13, 20] + ([33, 48, 64] if WIDE else [])), gen(r, depth)))
    ports = ", ".join(f"input {'signed ' if s else ''}[{w-1}:0] {n}" if w > 1 else f"input {n}" for n, w, s in IN)
    outp = ", ".join(f"output [{w-1}:0] {n}" for n, w, _ in outs)
    dut = f"module dut({ports}, {outp});\n" + "".join(f"  assign {n} = {e};\n" for n, _, e in outs) + "endmodule\n"
    try: circs, top, _ = elaborate(dut)
    except VError as e:
        REASONS[e.msg[:30]] = REASONS.get(e.msg[:30], 0) + 1
        if "wider" in e.msg or "too wide" in e.msg or "bit value is not possible" in e.msg or "is too big" in e.msg or "the most is 64" in e.msg or "wider than 64" in e.msg: return "skip", dut
        return "err", dut + f"\n{e.msg} line {e.line}"
    circ = circs[-1][1]
    errs = circ.validate()
    if errs: return "invalid", dut + "\n" + "\n".join(errs)
    vecs = [{n: r.randrange(1 << w) for n, w, _ in IN} for _ in range(nvec)]
    tb = "module tb;\n" + "".join(f"  reg {'signed ' if s else ''}[{w-1}:0] {n};\n" for n, w, s in IN) + "".join(f"  wire [{w-1}:0] {n};\n" for n, w, _ in outs)
    tb += f"  dut u({', '.join('.'+n+'('+n+')' for n,_,_ in IN)}, {', '.join('.'+n+'('+n+')' for n,_,_ in outs)});\n  initial begin\n"
    for v in vecs:
        tb += "".join(f"    {n} = {w}'d{v[n]};\n" for n, w, _ in IN) + "    #1; $display(\"" + " ".join("%0d" for _ in outs) + "\", " + ", ".join(n for n, _, _ in outs) + ");\n"
    tb += "    $finish;\n  end\nendmodule\n"
    d = tempfile.mkdtemp()
    open(d + "/t.v", "w").write(dut + tb)
    p = subprocess.run(["iverilog", "-g2005", "-o", d + "/x", d + "/t.v"], capture_output=True, text=True)
    if p.returncode and "indefinite width" in p.stderr: return "skip", dut
    if p.returncode: return "ivlerr", dut + p.stderr
    out = subprocess.run(["vvp", d + "/x"], capture_output=True, text=True).stdout.strip().splitlines()
    for v, line in zip(vecs, out):
        exp = line.split()
        got = circ.simulate(v)
        for (n, w, e), x in zip(outs, exp):
            if "x" in x or "z" in x: continue
            if got[n] != int(x): return "MISMATCH", dut + f"\nvec {v}\n{n} = {e}\nexpected {x}, got {got[n]}"
    return "ok", dut


if __name__ == "__main__":
    lo, hi = int(sys.argv[1]), int(sys.argv[2]); stats = {}; shown = 0
    for sd in range(lo, hi):
        st, msg = run_case(sd); stats[st] = stats.get(st, 0) + 1
        if st not in ("ok", "skip") and shown < 3: shown += 1; print("seed", sd, st); print(msg[-1500:])
    print(stats); print(REASONS)
