"""Random procedural code (nested if/case, blocking/nonblocking, enables, resets) vs iverilog."""
import random, sys
sys.path.insert(0, "dev"); sys.path.insert(0, "src")
import vfuzz_expr as FE
from vcheck import compare
from vibesimulation.verilog.lexer import VError

def expr(r, d=2): return FE.gen(r, d)

def stmts(r, vars_, depth, ind, seq):
    out = []
    for _ in range(r.randint(1, 3)):
        k = r.random()
        pad = "  " * ind
        v, w = r.choice(vars_)
        op = "<=" if seq else "="
        if depth > 0 and k < 0.3:
            out.append(f"{pad}if ({expr(r, 1)}) begin"); out += stmts(r, vars_, depth - 1, ind + 1, seq)
            if r.random() < .6: out.append(f"{pad}end else begin"); out += stmts(r, vars_, depth - 1, ind + 1, seq)
            out.append(f"{pad}end")
        elif depth > 0 and k < 0.5:
            sel = r.choice(["f", "b[1:0]", "a[2:0]"]); sw = {"f": 3, "b[1:0]": 2, "a[2:0]": 3}[sel]
            out.append(f"{pad}case ({sel})")
            for val in r.sample(range(1 << sw), r.randint(1, min(4, 1 << sw))):
                lab = f"{sw}'d{val}" if r.random() < .8 else f"{sw}'d{val}, {sw}'d{(val + 1) % (1 << sw)}"
                out.append(f"{pad}  {lab}: begin"); out += stmts(r, vars_, depth - 1, ind + 2, seq); out.append(f"{pad}  end")
            if r.random() < .6: out.append(f"{pad}  default: begin"); out += stmts(r, vars_, depth - 1, ind + 2, seq); out.append(f"{pad}  end")
            out.append(f"{pad}endcase")
        else:
            out.append(f"{pad}{v} {op} {expr(r)};")
    return out

def one(seed, seq):
    r = random.Random(seed)
    vars_ = [("y0", 8), ("y1", 4), ("y2", 1)]
    ports = "input [7:0] a, input [4:0] b, input signed [3:0] c, input d, input signed [11:0] e, input [2:0] f"
    outs = ", ".join(f"output reg [{w-1}:0] {n}" if w > 1 else f"output reg {n}" for n, w in vars_)
    if not seq:
        body = [f"  {n} = {w}'d0;" for n, w in vars_] + stmts(r, vars_, 3, 1, False)
        src = f"module dut({ports}, {outs});\n  always @* begin\n" + "\n".join(body) + "\n  end\nendmodule\n"
        res = ()
    else:
        arst = r.random() < .5
        head = "posedge clk or negedge rn" if arst else "posedge clk"
        body = stmts(r, vars_, 3, 3, True)
        rst = "\n".join(f"      {n} <= {w}'d0;" for n, w in vars_)
        if arst: core = f"    if (!rn) begin\n{rst}\n    end else begin\n" + "\n".join(body) + "\n    end"
        else: core = "    begin\n" + "\n".join(body) + "\n    end"
        src = f"module dut(input clk, {'input rn, ' if arst else ''}{ports}, {outs});\n  always @({head}) begin\n{core}\n  end\nendmodule\n"
        res = (("rn", 0),) if arst else ()
    return src, res

if __name__ == "__main__":
    lo, hi, seq = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3] == "seq"
    stat = {}; shown = 0
    for sd in range(lo, hi):
        src, res = one(sd, seq)
        try:
            bad, n = compare(src, "dut", nvec=40, seed=sd, resets=res, quiet=True)
            st = "ok" if not bad else "MISMATCH"
        except VError as e:
            st = "skip" if any(x in e.msg for x in ("signed division", "wider than", "most is 32", "not possible", "latch", "never driven", "has no reset", "too big", "reset value")) else "err"
            if st == "err" and shown < 3: shown += 1; print(sd, e.msg, e.line); print(src)
        except AssertionError as e:
            st = "assert"; 
            if shown < 3: shown += 1; print(sd, str(e)[:300]); print(src)
        stat[st] = stat.get(st, 0) + 1
        if st == "MISMATCH" and shown < 3: shown += 1; print("MISMATCH", sd); print(src); compare(src, "dut", nvec=40, seed=sd, resets=res)
    print(stat)
