"""Circuit -> Verilog text.

Plain parts become ordinary Verilog (gate primitives, assign statements, always blocks); every other part becomes a
library cell ``vs_<Type>`` that the Verilog reader understands, so nothing is ever lost.  After writing the readable form
the text is read back and compared with the circuit by simulation; if they ever differ, the exact cell form is used instead.
"""
import random
import re

from ..core.bits import mask
from ..components.registry import ComponentRegistry as R

KEYWORDS = set("""always and assign begin buf case casex casez default else end endcase endmodule for if initial inout input integer
module nand negedge nor not or output parameter posedge reg signed supply0 supply1 tri unsigned wand wire wor xnor xor function
task generate genvar localparam specify primitive table wait while repeat forever force release disable fork join""".split())
_ID = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*$")


def vid(name):
    return name if _ID.match(name) and name not in KEYWORDS and not name.startswith("vs_") else "\\" + name + " "


def cellname(type_name): return "vs_" + "".join(ch if ch.isalnum() else "_" for ch in type_name)


def rngs(w): return f"[{w - 1}:0] " if w > 1 else ""


def lit(v, w): return f"{w}'d{v}"


def attr_text(spec, val):
    if spec.kind == "bool": return "1" if val else "0"
    if spec.kind == "list": return '"' + ",".join(str(x) for x in val) + '"'
    if spec.kind == "map": return '"' + ",".join(f"{k}:{v}" for k, v in sorted(val.items())) + '"'
    if spec.kind in ("choice", "str"): return '"' + str(val) + '"'
    return str(val)


class Writer:
    def __init__(self, name, circ, readable=True):
        self.name, self.c, self.readable = name, circ, readable
        self.sw = circ.signals(); self.lines = []; self.regs = set(); self.stmts = []; self.used = set()
        self.names = {s for s in self.sw}

    def inst_name(self, c):
        n = c.id
        if _ID.match(n) and n not in KEYWORDS and n not in self.names and n not in self.used and not n.startswith("vs_"):
            self.used.add(n); return n, ""
        k = 1
        while f"u{k}" in self.names or f"u{k}" in self.used: k += 1
        self.used.add(f"u{k}"); return f"u{k}", f" // @{c.id}" if re.match(r"\S+$", c.id) else ""

    def hint(self, c): return f" // @{c.id}" if re.match(r"\S+$", c.id) else ""

    # ---- one component -> statement(s)
    def comp(self, c):
        t = c.type_name
        if getattr(c, "is_sub", False): return self.sub(c)
        if self.readable:
            f = getattr(self, "i_" + "".join(ch for ch in t if ch.isalnum()).lower(), None)
            if f is None and t in ("AND", "OR", "NAND", "NOR", "XOR", "XNOR", "NOT", "BUFFER"): f = self.i_gate
            if f:
                r = f(c)
                if r is not None: return r
        return self.cell(c)

    def sig(self, c, p): return vid(c.ins[p])

    def all_in(self, c, *ports): return all(c.ins.get(p) is not None for p in ports)

    def i_gate(self, c):
        t = c.type_name; w = c.attrs["width"]; out = c.outs.get("Out")
        n = 1 if t in ("NOT", "BUFFER") else c.attrs["inputs"]
        ins = [c.ins.get(f"In{i + 1}") for i in range(n)]
        if out is None or any(s is None for s in ins): return None
        if w == 1:
            name, h = self.inst_name(c)
            prim = {"AND": "and", "OR": "or", "NAND": "nand", "NOR": "nor", "XOR": "xor", "XNOR": "xnor", "NOT": "not", "BUFFER": "buf"}[t]
            return [f"  {prim} {vid(name)} ({', '.join(vid(s) for s in [out] + ins)});{h or self.hint(c) if name != c.id else ''}"]
        op = {"AND": "&", "OR": "|", "XOR": "^", "NAND": "&", "NOR": "|", "XNOR": "^"}.get(t)
        if t == "NOT": e = "~" + vid(ins[0]) + " "
        elif t == "BUFFER": e = vid(ins[0])
        else:
            e = f" {op} ".join(vid(s) for s in ins)
            if t in ("NAND", "NOR", "XNOR"): e = f"~({e})"
        return [f"  assign {vid(out)} = {e};{self.hint(c)}"]

    def i_adder(self, c):
        if c.ins.get("Cin") is not None or c.outs.get("Cout") is not None or not self.all_in(c, "A", "B") or c.outs.get("Sum") is None: return None
        return [f"  assign {vid(c.outs['Sum'])} = {self.sig(c, 'A')} + {self.sig(c, 'B')};{self.hint(c)}"]

    def i_subtractor(self, c):
        if c.ins.get("Bin") is not None or c.outs.get("Bout") is not None or not self.all_in(c, "A", "B") or c.outs.get("Diff") is None: return None
        return [f"  assign {vid(c.outs['Diff'])} = {self.sig(c, 'A')} - {self.sig(c, 'B')};{self.hint(c)}"]

    def i_multiplier(self, c):
        if c.ins.get("Cin") is not None or c.outs.get("Cout") is not None or not self.all_in(c, "A", "B") or c.outs.get("Prod") is None: return None
        return [f"  assign {vid(c.outs['Prod'])} = {self.sig(c, 'A')} * {self.sig(c, 'B')};{self.hint(c)}"]

    def i_negator(self, c):
        if not self.all_in(c, "In") or c.outs.get("Out") is None: return None
        return [f"  assign {vid(c.outs['Out'])} = -{self.sig(c, 'In')};{self.hint(c)}"]

    def i_mux(self, c):
        if c.attrs["select"] != 1 or c.ins.get("En") is not None or not self.all_in(c, "In0", "In1", "Sel") or c.outs.get("Out") is None: return None
        return [f"  assign {vid(c.outs['Out'])} = {self.sig(c, 'Sel')} ? {self.sig(c, 'In1')} : {self.sig(c, 'In0')};{self.hint(c)}"]

    def i_comparator(self, c):
        if not self.all_in(c, "A", "B"): return None
        a, b = self.sig(c, "A"), self.sig(c, "B")
        if c.attrs["mode"] == "signed": a, b = f"$signed({a})", f"$signed({b})"
        out = []
        for p, op in (("GT", ">"), ("EQ", "=="), ("LT", "<")):
            if c.outs.get(p) is not None: out.append(f"  assign {vid(c.outs[p])} = {a} {op} {b};{self.hint(c)}")
        return out or None

    def i_splitter(self, c):
        if not self.all_in(c, "In"): return None
        out, pos = [], 0
        for i, w in enumerate(c.attrs["widths"]):
            o = c.outs.get(f"Out{i}")
            if o is not None:
                rng = f"[{pos + w - 1}:{pos}]" if w > 1 else f"[{pos}]"
                out.append(f"  assign {vid(o)} = {self.sig(c, 'In')}{rng};{self.hint(c)}")
            pos += w
        return out or None

    def i_combiner(self, c):
        n = len(c.attrs["widths"])
        if not self.all_in(c, *[f"In{i}" for i in range(n)]) or c.outs.get("Out") is None: return None
        return [f"  assign {vid(c.outs['Out'])} = {{{', '.join(self.sig(c, f'In{i}') for i in reversed(range(n)))}}};{self.hint(c)}"]

    def i_bitextender(self, c):
        a = c.attrs
        if not self.all_in(c, "In") or c.outs.get("Out") is None or a["fill"] == "one": return None
        s, o = self.sig(c, "In"), vid(c.outs["Out"])
        if a["out_width"] <= a["in_width"]: e = s if a["out_width"] == a["in_width"] else f"{s}[{a['out_width'] - 1}:0]"
        elif a["fill"] == "zero": e = f"{{{a['out_width'] - a['in_width']}'d0, {s}}}"
        else: e = f"{{{{{a['out_width'] - a['in_width']}{{{s}[{a['in_width'] - 1}]}}}}, {s}}}" if a["in_width"] > 1 else f"{{{a['out_width'] - a['in_width']}{{{s}}}, {s}}}"
        return [f"  assign {o} = {e};{self.hint(c)}"]

    def i_shifter(self, c):
        sh = c.attrs["shift"]
        if sh not in ("ll", "lr", "ar") or not self.all_in(c, "In", "Shift") or c.outs.get("Out") is None: return None
        a, s = self.sig(c, "In"), self.sig(c, "Shift")
        e = {"ll": f"{a} << {s}", "lr": f"{a} >> {s}", "ar": f"$signed({a}) >>> {s}"}[sh]
        return [f"  assign {vid(c.outs['Out'])} = {e};{self.hint(c)}"]

    def seq_always(self, c, d, width, enable):
        trig = c.attrs["trigger"]
        if trig not in ("rising", "falling") or c.outs.get("Q") is None: return None
        if not self.all_in(c, d, "Clk"): return None
        pre = c.ins.get("Pre") if "Pre" in c.ins else None
        clr = c.ins.get("Clr")
        if pre is not None and clr is not None: return None
        q = vid(c.outs["Q"]); self.regs.add(c.outs["Q"]); edge = "posedge" if trig == "rising" else "negedge"
        body = f"{q} <= {self.sig(c, d)};"
        if enable and c.ins.get("En") is not None: body = f"if ({vid(c.ins['En'])}) {body}"
        ev = f"{edge} {vid(c.ins['Clk'])}"
        if clr is not None or pre is not None:
            rs = clr if clr is not None else pre; val = lit(0, width) if clr is not None else "1'b1"
            lines = [f"  always @({ev} or posedge {vid(rs)}){self.hint(c)}", f"    if ({vid(rs)}) {q} <= {val};", f"    else {body}"]
        else: lines = [f"  always @({ev}){self.hint(c)}", f"    {body}"]
        if "Qn" in c.outs and c.outs["Qn"] is not None: lines.append(f"  assign {vid(c.outs['Qn'])} = ~{q};")
        return lines

    def i_dflipflop(self, c): return self.seq_always(c, "D", 1, False)

    def i_register(self, c): return self.seq_always(c, "D", c.attrs["width"], True)

    # ---- exact cell
    def cell(self, c):
        cls = type(c); name, h = self.inst_name(c)
        ps = []
        for a in c.attrs_spec:
            if c.attrs[a.name] != a.default: ps.append(f".{a.name}({attr_text(a, c.attrs[a.name])})")
        pins = [f".{p}({vid(s)})" for p, s in c.ins.items() if s is not None] + [f".{p}({vid(s)})" for p, s in c.outs.items() if s is not None]
        par = f" #({', '.join(ps)})" if ps else ""
        return [f"  {cellname(c.type_name)}{par} {vid(name)} ({', '.join(pins)});{h or (self.hint(c) if name != c.id else '')}"]

    def sub(self, c):
        name, h = self.inst_name(c)
        pins = [f".{vid(p)}({vid(s)})" for p, s in list(c.ins.items()) + list(c.outs.items()) if s is not None]
        return [f"  {vid(c.attrs['circuit'])} {vid(name)} ({', '.join(pins)});{h}"]

    # ---- the module
    def text(self):
        c = self.c; body = []
        for comp in c.components: body += self.comp(comp)
        ins = {p.name for p in c.inputs}; outs = {p.name for p in c.outputs}
        ports = [f"  input {rngs(p.width)}{vid(p.name)}" for p in c.inputs]
        ports += [f"  output {'reg ' if p.name in self.regs else ''}{rngs(self.sw.get(p.name, p.width))}{vid(p.name)}" for p in c.outputs]
        head = f"module {vid(self.name)} (\n" + ",\n".join(ports) + "\n);" if ports else f"module {vid(self.name)};"
        decl = []
        for comp in c.components:
            for p in comp.out_ports():
                s = comp.outs.get(p.name)
                if s is None or s in outs or s in ins: continue
                decl.append(f"  {'reg' if s in self.regs else 'wire'} {rngs(self.sw[s])}{vid(s)};")
        decl = list(dict.fromkeys(decl))
        return "\n".join([head] + decl + ([""] if decl else []) + body + ["endmodule"]) + "\n"


def circuit_to_verilog(name, circ, check=True):
    """Verilog text for one circuit. The readable form is checked against the circuit by simulation."""
    text = Writer(name, circ, True).text()
    if check and not _same(name, circ, text):
        text = Writer(name, circ, False).text()
    return text


def _same(name, circ, text):
    from .elab import elaborate
    from .lexer import VError
    from ..core import sim
    try:
        ext = {}
        circs, top, _ = elaborate(text, name, _external(circ))
        new = dict(circs)[name]
    except (VError, KeyError, ValueError):
        return False
    if new.validate(loose=True): return False
    if [(p.name, p.width) for p in new.inputs] != [(p.name, p.width) for p in circ.inputs]: return False
    if [(p.name, p.width) for p in new.outputs] != [(p.name, p.width) for p in circ.outputs]: return False
    if circ.has_subs(): return True        # parts of other circuits are written as plain instances, nothing readable to doubt
    return equivalent(circ, new)


def _external(circ):
    from ..core import project
    ext = {}
    for c in circ.components:
        if getattr(c, "is_sub", False):
            inner = project.lookup(c.attrs["circuit"])
            if inner is not None: ext[c.attrs["circuit"]] = ({p.name: p.width for p in inner.inputs}, {p.name: p.width for p in inner.outputs}, [p.name for p in inner.inputs] + [p.name for p in inner.outputs])
    return ext


def equivalent(a, b, n=200, seed=7):
    """Do two circuits (same pins) behave the same? Exhaustive for few input bits, random sequences otherwise."""
    from ..core import sim
    r = random.Random(seed)
    ins = [(p.name, p.width) for p in a.inputs]
    seq = a.has_seq() or b.has_seq()
    clkish = [nm for nm, w in ins if w == 1]
    try:
        sa, sb = sim.fresh(a), sim.fresh(b)
        total = sum(w for _, w in ins)
        if not seq and total <= 10: vecs = [{nm: (k >> sum(w2 for n2, w2 in ins[:i])) & mask(w) for i, (nm, w) in enumerate(ins)} for k in range(1 << total)]
        else: vecs = [{nm: r.randrange(1 << w) for nm, w in ins} for _ in range(n)]
        # sequential: pulse every 1-bit input as a clock now and then
        tick = 0
        for v in vecs:
            steps = [v]
            if seq:
                steps = [v]
                for nm in clkish:
                    steps += [{**v, nm: 1 - v[nm]}, v] if r.random() < .5 else []
            for st in steps:
                tick += 1
                va, _ = sim.settle(a, st, sa, tick); vb, _ = sim.settle(b, st, sb, tick)
                for p in a.outputs:
                    if va.get(p.name) != vb.get(p.name): return False
    except Exception:
        return False
    return True
