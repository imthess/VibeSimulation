"""Timing of big designs: 1000+ parts through parse -> layout -> truth/sim, Verilog compile, and a long testbench."""
import sys, os, time, json, cProfile, pstats
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from vibesimulation.core.document import Document
from vibesimulation.vlsi.document import VlsiDocument
from vibesimulation.vlsi import simulation

def timeit(name, fn):
    t = time.time(); r = fn(); dt = time.time() - t; print(f"{name:55s} {dt:7.2f} s"); return r, dt

def chain(n):          # n gates in a chain: worst case for depth
    gates = [{"id": "g1", "type": "AND", "in": ["A", "B"], "out": "n1"}]
    for i in range(2, n + 1): gates.append({"id": f"g{i}", "type": "XOR" if i % 2 else "AND", "in": [f"n{i-1}", "A" if i % 3 else "B"], "out": f"n{i}" if i < n else "Y"})
    return json.dumps({"inputs": ["A", "B"], "outputs": ["Y"], "gates": gates})

def tree(n):           # wide: n/2 independent gates feeding an OR tree
    gates, outs = [], []
    for i in range(n): gates.append({"id": f"a{i}", "type": "AND", "in": [f"I{i % 16}", f"I{(i * 7 + 3) % 16}"], "out": f"t{i}"}); outs.append(f"t{i}")
    lvl, k = outs, 0
    while len(lvl) > 1:
        nxt = []
        for j in range(0, len(lvl), 4):
            grp = lvl[j:j + 4]
            if len(grp) == 1: nxt.append(grp[0]); continue
            k += 1; name = f"o{k}"; gates.append({"id": f"or{k}", "type": "OR", "in": grp, "out": name}); nxt.append(name)
        lvl = nxt
    gates[-1]["out"] = "Y"
    return json.dumps({"inputs": [f"I{i}" for i in range(16)], "outputs": ["Y"], "gates": gates})

if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
    for nm, mk in (("chain", chain), ("tree", tree)):
        d = Document(); text = mk(N)
        _, t1 = timeit(f"Logisim {nm} {N}: load_text (parse+layout+calc)", lambda: d.load_text(text))
        print("   valid:", d.valid, d.errors[:1], "components:", len(d.circuit.components) if d.valid else 0)
        if d.valid:
            timeit(f"Logisim {nm}: toggle an input", lambda: d.set_inputs({"A": 1}))
            timeit(f"Logisim {nm}: truth table (12 bits)", lambda: d.circuit.table(12) if len(d.circuit.inputs) <= 12 else None)
    # VLSI: an adder with big width, a wide parity, a generate array
    for desc, src in (("64-bit adder", "module t(input [63:0] a, b, output [63:0] s); assign s = a + b; endmodule\n"),
                      ("generate 600 gates", "module t #(parameter N=600)(input [N-1:0] a, input [N-1:0] b, output [N-1:0] y);\n genvar i;\n generate for (i=0;i<N;i=i+1) begin:g assign y[i] = a[i] & ~b[i] ^ a[(i+1)%N]; end endgenerate\nendmodule\n"),
                      ("for-loop 1000 xors", "module t(input [999:0] d, output reg p);\n integer i;\n always @(*) begin p = 0; for (i=0;i<1000;i=i+1) p = p ^ d[i]; end\nendmodule\n")):
        v = VlsiDocument()
        errs, dt = timeit(f"VLSI compile: {desc}", lambda: v.new_blank(src))
        print("   errors:", errs[:1], "components:", len(v.circuit.components) if v.valid else 0)
    v = VlsiDocument(); v.new_blank("module counter(input clk, rst, output reg [31:0] q);\n always @(posedge clk) if (rst) q <= 0; else q <= q + 1;\nendmodule\n")
    timeit("VLSI testbench: 32-bit counter, 2000 cycles", lambda: simulation.run(v, cycles=2000, period=10))
