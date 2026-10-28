"""Verilog parser (a practical synthesizable subset) -> AST. Everything it does not understand is reported with its line."""
from .lexer import VError, lex, Num


class N:
    """AST node: kind plus fields (attribute access); every node knows its line."""
    def __init__(self, kind, line, **kw): self.kind, self.line = kind, line; self.__dict__.update(kw)

    def __repr__(self): return f"N({self.kind}, " + ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items() if k not in ("kind", "line")) + ")"


GATES = {"and", "or", "nand", "nor", "xor", "xnor", "not", "buf"}
UNSUPPORTED_GATES = {"bufif0", "bufif1", "notif0", "notif1", "nmos", "pmos", "cmos", "tran", "pullup", "pulldown", "rnmos", "rpmos", "tranif0", "tranif1"}
NETKINDS = {"wire", "reg", "tri", "wand", "wor", "supply0", "supply1", "integer", "time"}
BIN_PREC = [("||",), ("&&",), ("|",), ("^", "~^", "^~"), ("&",), ("==", "!=", "===", "!=="), ("<", "<=", ">", ">="), ("<<", ">>", "<<<", ">>>"), ("+", "-"), ("*", "/", "%"), ("**",)]


class Parser:
    def __init__(self, text):
        self.toks, self.comments = lex(text); self.i = 0
        self.hoist = []            # declarations found inside begin..end blocks: they become module-level nets

    # ---- token helpers
    @property
    def t(self): return self.toks[self.i]

    def peek(self, k=1): return self.toks[min(self.i + k, len(self.toks) - 1)]

    def err(self, msg, tok=None): raise VError(msg, (tok or self.t).line)

    def is_op(self, v): return self.t.kind == "op" and self.t.val == v

    def is_kw(self, v): return self.t.kind == "id" and self.t.val == v

    def accept_op(self, v):
        if self.is_op(v): self.i += 1; return True
        return False

    def accept_kw(self, v):
        if self.is_kw(v): self.i += 1; return True
        return False

    def expect_op(self, v):
        if not self.is_op(v):
            got = "the end of the file" if self.t.kind == "eof" else f"'{self.t.val}'" if self.t.kind != "num" else "a number"
            self.err(f"expected '{v}' but found {got}")
        self.i += 1

    def expect_kw(self, v):
        if not self.is_kw(v): self.err(f"expected '{v}'")
        self.i += 1

    def ident(self, what="a name"):
        if self.t.kind != "id": self.err(f"expected {what}")
        v = self.t.val; self.i += 1; return v

    # ---- file / module
    def parse(self):
        mods = []
        while self.t.kind != "eof":
            if self.is_kw("module"): mods.append(self.module())
            elif self.t.kind == "id" and self.t.val in ("primitive", "package", "interface", "program"): self.err(f"'{self.t.val}' is not supported")
            else: self.err(f"expected 'module' but found '{self.t.val}'")
        return mods

    def module(self):
        line = self.t.line; self.expect_kw("module"); name = self.ident("the module name")
        m = N("module", line, name=name, ports=[], items=[], header=[], params=[])
        if self.is_op("#"):
            self.i += 1; self.expect_op("(")
            while not self.is_op(")"):
                self.accept_kw("parameter"); self.accept_kw("integer"); sg = self.accept_kw("signed"); self.accept_kw("unsigned"); pr = self.rng()
                pn = self.ident("a parameter name"); self.expect_op("="); m.params.append(N("param", self.t.line, name=pn, value=self.expr(), rng=pr, signed=sg))
                if not self.accept_op(","): break
            self.expect_op(")")
        if self.is_op("("):
            self.i += 1
            if self.t.kind == "id" and self.t.val in ("input", "output", "inout"):
                self.ansi_ports(m)
            else:
                while not self.is_op(")"):
                    m.header.append(self.ident("a port name"))
                    if not self.accept_op(","): break
            self.expect_op(")")
        self.expect_op(";")
        while not self.is_kw("endmodule"):
            if self.t.kind == "eof": self.err(f"module '{name}' has no 'endmodule'", self.toks[-1])
            m.items += self.item(m); m.items += self.hoist; self.hoist = []
        self.i += 1
        return m

    def skip_type(self):
        while self.t.kind == "id" and self.t.val in ("signed", "unsigned"): self.i += 1

    def rng(self):
        """[msb:lsb] or nothing -> (msb, lsb) expression nodes."""
        if not self.is_op("["): return None
        self.i += 1; a = self.expr(); self.expect_op(":"); b = self.expr(); self.expect_op("]"); return (a, b)

    def ansi_ports(self, m):
        direction, kind, signed, rng = None, "wire", False, None
        while not self.is_op(")"):
            line = self.t.line
            if self.t.kind == "id" and self.t.val in ("input", "output", "inout"):
                direction = self.t.val; self.i += 1; kind, signed, rng = "wire", False, None
                if self.t.kind == "id" and self.t.val in NETKINDS: kind = self.t.val; self.i += 1
                if self.accept_kw("signed"): signed = True
                rng = self.rng()
            if direction is None: self.err("expected 'input' or 'output'")
            name = self.ident("a port name")
            m.ports.append(N("port", line, name=name, dir=direction, netkind=kind, signed=signed, rng=rng))
            if not self.accept_op(","): break

    # ---- module items
    def hint(self, line):
        for c in self.comments.get(line, []):
            for w in c.split():
                if w.startswith("@") and len(w) > 1: return w[1:]
        return None

    def item(self, m):
        t = self.t; line = t.line
        if t.kind != "id": self.err(f"unexpected '{t.val}' in a module")
        v = t.val
        if v in ("input", "output", "inout"):
            direction = v; self.i += 1; kind, signed = "wire", False
            if self.t.kind == "id" and self.t.val in NETKINDS: kind = self.t.val; self.i += 1
            if self.accept_kw("signed"): signed = True
            rng = self.rng(); out = []
            while True:
                nm = self.ident("a port name"); out.append(N("port", line, name=nm, dir=direction, netkind=kind, signed=signed, rng=rng))
                if not self.accept_op(","): break
            self.expect_op(";"); return [N("portdecl", line, ports=out)]
        if v in NETKINDS:
            kind = v; self.i += 1; signed = self.accept_kw("signed"); rng = self.rng(); names = []; arrays = {}
            while True:
                ln = self.t.line; nm = self.ident("a name")
                if self.is_op("["):                                  # memory: reg [7:0] mem [0:15]
                    a = self.rng()
                    arrays[nm] = a
                    if self.is_op("["): self.err(f"'{nm}': memories with two dimensions are not supported")
                init = None
                if self.accept_op("="): init = self.expr()
                names.append((nm, init, ln))
                if not self.accept_op(","): break
            self.expect_op(";"); return [N("net", line, netkind=kind, signed=signed, rng=rng, names=names, arrays=arrays)]
        if v in ("parameter", "localparam"):
            self.i += 1; self.accept_kw("integer"); sg = self.accept_kw("signed"); self.accept_kw("unsigned"); pr = self.rng(); out = []
            while True:
                nm = self.ident("a parameter name"); self.expect_op("="); out.append(N("param", line, name=nm, value=self.expr(), rng=pr, signed=sg))
                if not self.accept_op(","): break
            self.expect_op(";"); return out
        if v == "assign":
            self.i += 1
            if self.is_op("#"): self.skip_delay()
            out = []; hint = self.hint(line)
            while True:
                ln = self.t.line; lhs = self.lvalue(); self.expect_op("="); rhs = self.expr(); out.append(N("assign", ln, lhs=lhs, rhs=rhs, hint=self.hint(ln) or hint))
                if not self.accept_op(","): break
            self.expect_op(";"); return out
        if v == "always": return [self.always()]
        if v == "initial": return [self.initial()]
        if v == "genvar":
            self.i += 1
            while True:
                self.ident("a genvar name")
                if not self.accept_op(","): break
            self.expect_op(";"); return []
        if v == "generate":
            self.i += 1; out = []
            while not self.is_kw("endgenerate"):
                if self.t.kind == "eof": self.err("'generate' has no 'endgenerate'", t)
                out += self.gen_item(m)
            self.i += 1; return out
        if v in ("for", "if", "case", "casez", "casex"): return self.gen_item(m)
        if v == "function": return [self.function()]
        if v == "task": return [self.task()]
        if v in ("specify", "defparam", "endgenerate"): self.err(f"'{v}' is not supported")
        if v in UNSUPPORTED_GATES: self.err(f"the '{v}' primitive (tri-state / switch level) is not supported")
        if v in GATES: return self.gate()
        return [self.instance()]

    def skip_delay(self):
        self.expect_op("#")
        if self.accept_op("("):
            depth = 1
            while depth:
                if self.is_op("("): depth += 1
                elif self.is_op(")"): depth -= 1
                elif self.t.kind == "eof": self.err("unbalanced parentheses in a delay")
                self.i += 1
        elif self.t.kind in ("num", "id"): self.i += 1

    def gate(self):
        line = self.t.line; kind = self.t.val; self.i += 1; out = []
        if self.is_op("#"): self.skip_delay()
        while True:
            ln = self.t.line; name = None
            if self.t.kind == "id": name = self.ident()
            if self.is_op("["): self.err("arrays of instances are not supported")
            self.expect_op("("); conns = [self.expr()]
            while self.accept_op(","): conns.append(self.expr())
            self.expect_op(")"); out.append(N("gate", ln, gate=kind, name=name, conns=conns, hint=self.hint(ln)))
            if not self.accept_op(","): break
        self.expect_op(";"); return out

    def instance(self):
        line = self.t.line; mod = self.ident("a module name"); params = []
        if self.is_op("#"):
            self.i += 1; self.expect_op("(")
            while not self.is_op(")"):
                if self.accept_op("."):
                    pn = self.ident(); self.expect_op("("); params.append((pn, self.expr())); self.expect_op(")")
                else: params.append((None, self.expr()))
                if not self.accept_op(","): break
            self.expect_op(")")
        if self.t.kind != "id": self.err(f"'{mod}' is not a Verilog keyword; expected an instance name after the module name")
        name = self.ident("an instance name")
        if self.is_op("["): self.err("arrays of instances are not supported")
        self.expect_op("("); conns = []
        while not self.is_op(")"):
            if self.accept_op("."):
                pn = self.ident("a port name"); self.expect_op("(")
                e = None if self.is_op(")") else self.expr()
                self.expect_op(")"); conns.append((pn, e))
            else: conns.append((None, self.expr()))
            if not self.accept_op(","): break
        self.expect_op(")"); self.expect_op(";")
        return N("inst", line, module=mod, params=params, name=name, conns=conns, hint=self.hint(line))

    # ---- procedural
    def always(self):
        line = self.t.line; self.expect_kw("always"); events = []; star = False
        if not self.is_op("@"):                                    # always #5 clk = ~clk;  (testbench style)
            return N("always", line, star=False, events=None, body=self.stmt(), hint=self.hint(line))
        self.i += 1
        if self.accept_op("*"): star = True
        else:
            self.expect_op("(")
            if self.accept_op("*"): star = True
            else:
                while True:
                    edge = None
                    if self.t.kind == "id" and self.t.val in ("posedge", "negedge"): edge = self.t.val; self.i += 1
                    e = self.expr(); events.append((edge, e))
                    if self.accept_kw("or") or self.accept_op(","): continue
                    break
            self.expect_op(")")
        body = self.stmt()
        return N("always", line, star=star, events=events, body=body, hint=self.hint(line))

    def initial(self):
        line = self.t.line; self.expect_kw("initial"); return N("initial", line, body=self.stmt())

    # ---- functions and tasks
    def sub_decls(self, args, decls, named_dirs):
        """Declarations at the top of a function/task: inputs/outputs go to args, everything else to decls."""
        while self.t.kind == "id":
            v = self.t.val
            if v in ("input", "output", "inout"):
                line = self.t.line; self.i += 1; sg = self.accept_kw("signed"); rng = None
                if self.t.kind == "id" and self.t.val in NETKINDS:
                    if self.t.val == "integer": sg = True; rng = self.int_range(line)
                    self.i += 1
                if self.accept_kw("signed"): sg = True
                rng = self.rng() or rng
                while True:
                    args.append((self.ident("a name"), v, rng, sg))
                    if not self.accept_op(","): break
                self.expect_op(";")
            elif v in NETKINDS or v in ("parameter", "localparam"):
                decls += self.item(None)
            else: break

    def int_range(self, line):
        """[31:0] as syntax-tree numbers (an `integer` argument)."""
        return (N("num", line, num=Num(31, None, True, False)), N("num", line, num=Num(0, None, True, False)))

    def sub_ansi(self, args):
        direction, sg, rng = "input", False, None
        while not self.is_op(")"):
            if self.t.kind == "id" and self.t.val in ("input", "output", "inout"):
                direction = self.t.val; self.i += 1; sg = False; rng = None
                if self.t.kind == "id" and self.t.val in NETKINDS:
                    if self.t.val == "integer": sg = True; rng = self.int_range(self.t.line)
                    self.i += 1
                if self.accept_kw("signed"): sg = True
                rng = self.rng() or rng
            args.append((self.ident("a name"), direction, rng, sg))
            if not self.accept_op(","): break

    def sub_body(self, end):
        line = self.t.line; st = []
        while not self.is_kw(end):
            if self.t.kind == "eof": self.err(f"'{end[3:]}' has no '{end}'")
            st.append(self.stmt())
        self.i += 1
        return st[0] if len(st) == 1 else N("block", line, stmts=st)

    def function(self):
        line = self.t.line; self.expect_kw("function")
        while self.t.kind == "id" and self.t.val in ("automatic", "static"): self.i += 1
        sg = self.accept_kw("signed"); isint = False
        if self.accept_kw("integer"): isint = True
        rng = self.rng(); name = self.ident("a function name"); args, decls = [], []
        saved, self.hoist = self.hoist, []
        if self.accept_op("("): self.sub_ansi(args); self.expect_op(")")
        self.expect_op(";"); self.sub_decls(args, decls, None)
        body = self.sub_body("endfunction"); decls += self.hoist; self.hoist = saved
        return N("function", line, name=name, rng=rng, signed=sg or isint, integer=isint, args=args, decls=decls, body=body)

    def task(self):
        line = self.t.line; self.expect_kw("task")
        while self.t.kind == "id" and self.t.val in ("automatic", "static"): self.i += 1
        name = self.ident("a task name"); args, decls = [], []
        saved, self.hoist = self.hoist, []
        if self.accept_op("("): self.sub_ansi(args); self.expect_op(")")
        self.expect_op(";"); self.sub_decls(args, decls, None)
        body = self.sub_body("endtask"); decls += self.hoist; self.hoist = saved
        return N("task", line, name=name, args=args, decls=decls, body=body)

    # ---- generate constructs (also allowed without the generate keyword)
    def gen_item(self, m):
        t = self.t; line = t.line
        if self.is_kw("for"):
            self.i += 1; self.expect_op("("); var = self.ident("the loop variable"); self.expect_op("="); init = self.expr(); self.expect_op(";")
            cond = self.expr(); self.expect_op(";"); v2 = self.ident("the loop variable"); self.expect_op("="); step = self.expr(); self.expect_op(")")
            return [N("genfor", line, var=var, init=init, cond=cond, stepvar=v2, step=step, body=self.genbody(m))]
        if self.is_kw("if"):
            self.i += 1; self.expect_op("("); c = self.expr(); self.expect_op(")"); a = self.genbody(m); b = None
            if self.accept_kw("else"): b = self.genbody(m)
            return [N("genif", line, cond=c, then=a, els=b)]
        if self.t.kind == "id" and self.t.val in ("case", "casez", "casex"):
            self.i += 1; self.expect_op("("); e = self.expr(); self.expect_op(")"); items, default = [], None
            while not self.is_kw("endcase"):
                if self.t.kind == "eof": self.err("'case' has no 'endcase'", t)
                if self.accept_kw("default"): self.accept_op(":"); default = self.genbody(m)
                else:
                    labels = [self.expr()]
                    while self.accept_op(","): labels.append(self.expr())
                    self.expect_op(":"); items.append((labels, self.genbody(m)))
            self.i += 1; return [N("gencase", line, expr=e, items=items, default=default)]
        if self.is_kw("begin"): return [self.genbody(m)]
        return self.item(m) + self.take_hoist()

    def take_hoist(self):
        h, self.hoist = self.hoist, []; return h

    def genbody(self, m):
        line = self.t.line; label = None
        if self.accept_kw("begin"):
            if self.accept_op(":"): label = self.ident("a block name")
            items = []
            while not self.is_kw("end"):
                if self.t.kind == "eof": self.err("'begin' has no 'end'")
                items += self.gen_item(m)
            self.i += 1
            return N("genblock", line, label=label, items=items)
        return N("genblock", line, label=None, items=self.gen_item(m))

    def stmt(self):
        t = self.t; line = t.line
        if t.kind == "op" and t.val == ";": self.i += 1; return N("block", line, stmts=[])
        if t.kind == "op" and t.val == "#":
            self.i += 1
            amount = self.paren_expr() if self.is_op("(") else self.primary()
            return N("delay", line, amount=amount, body=self.opt_stmt())
        if t.kind == "op" and t.val == "@":
            self.i += 1; events = []; star = False
            if self.accept_op("*"): star = True
            elif self.is_op("("):
                self.i += 1
                if self.accept_op("*"): star = True
                else:
                    while True:
                        edge = None
                        if self.t.kind == "id" and self.t.val in ("posedge", "negedge"): edge = self.t.val; self.i += 1
                        events.append((edge, self.expr()))
                        if self.accept_kw("or") or self.accept_op(","): continue
                        break
                self.expect_op(")")
            else:
                edge = None
                if self.t.kind == "id" and self.t.val in ("posedge", "negedge"): edge = self.t.val; self.i += 1
                events.append((edge, self.primary()))
            return N("event", line, events=events, star=star, body=self.opt_stmt())
        if t.kind == "id":
            v = t.val
            if v == "begin":
                self.i += 1; label = None
                if self.accept_op(":"): label = self.ident()
                st = []
                while not self.is_kw("end"):
                    if self.t.kind == "eof": self.err("'begin' has no 'end'", t)
                    if self.t.kind == "id" and self.t.val in NETKINDS | {"parameter", "localparam"} and label is not None:
                        self.hoist += self.item(None); continue
                    st.append(self.stmt())
                self.i += 1; return N("block", line, stmts=st, label=label)
            if v == "if":
                self.i += 1; c = self.paren_expr(); a = self.stmt(); b = None
                if self.accept_kw("else"): b = self.stmt()
                return N("if", line, cond=c, then=a, els=b)
            if v in ("case", "casez", "casex"):
                self.i += 1; e = self.paren_expr(); items, default = [], None
                while not self.is_kw("endcase"):
                    if self.t.kind == "eof": self.err("'case' has no 'endcase'", t)
                    if self.accept_kw("default"):
                        self.accept_op(":"); default = self.stmt()
                    else:
                        labels = [self.expr()]
                        while self.accept_op(","): labels.append(self.expr())
                        self.expect_op(":"); items.append((labels, self.stmt()))
                self.i += 1; return N("case", line, casekind=v, expr=e, items=items, default=default)
            if v == "for":
                self.i += 1; self.expect_op("(")
                init = self.simple_assign(); self.expect_op(";"); cond = self.expr(); self.expect_op(";"); step = self.simple_assign(); self.expect_op(")")
                return N("for", line, init=init, cond=cond, step=step, body=self.stmt())
            if v == "while": self.i += 1; c = self.paren_expr(); return N("while", line, cond=c, body=self.stmt())
            if v == "repeat": self.i += 1; c = self.paren_expr(); return N("repeat", line, count=c, body=self.stmt())
            if v == "forever": self.i += 1; return N("forever", line, body=self.stmt())
            if v == "wait": self.i += 1; c = self.paren_expr(); return N("wait", line, cond=c, body=self.opt_stmt())
            if v == "disable": self.i += 1; nm = self.ident(); self.expect_op(";"); return N("disable", line, name=nm)
            if v in ("fork", "force", "release", "deassign"): self.err(f"'{v}' is not supported")
            if self.peek().kind == "op" and self.peek().val in ("(", ";") and v not in ("if", "else"):      # task call
                self.i += 1; args = []
                if self.accept_op("("):
                    while not self.is_op(")"):
                        args.append(self.expr())
                        if not self.accept_op(","): break
                    self.expect_op(")")
                self.expect_op(";"); return N("taskcall", line, name=v, args=args)
        if t.kind == "sys":
            self.i += 1; args = []
            if self.accept_op("("):
                while not self.is_op(")"):
                    args.append(self.expr())
                    if not self.accept_op(","): break
                self.expect_op(")")
            self.expect_op(";"); return N("systask", line, name=t.val, args=args)
        lhs = self.lvalue()
        if self.is_op("=") or self.is_op("<="):
            blocking = self.t.val == "="; self.i += 1; delay = None
            if self.is_op("#"): self.i += 1; delay = self.paren_expr() if self.is_op("(") else self.primary()
            elif self.is_op("@") or self.is_kw("repeat"): self.err("event controls inside an assignment are not supported")
            rhs = self.expr(); self.expect_op(";"); return N("assign", line, lhs=lhs, rhs=rhs, blocking=blocking, delay=delay)
        self.err("expected '=' or '<=' in an assignment")

    def paren_expr(self):
        self.expect_op("("); e = self.expr(); self.expect_op(")"); return e

    def opt_stmt(self):
        """The statement after a delay/event control; a bare ';' means none."""
        if self.is_op(";"): self.i += 1; return None
        return self.stmt()

    def simple_assign(self):
        line = self.t.line; lhs = self.lvalue(); self.expect_op("="); rhs = self.expr()
        return N("assign", line, lhs=lhs, rhs=rhs, blocking=True, delay=None)

    def lvalue(self):
        if self.is_op("{"):
            line = self.t.line; self.i += 1; parts = [self.lvalue()]
            while self.accept_op(","): parts.append(self.lvalue())
            self.expect_op("}"); return N("concat", line, parts=parts)
        line = self.t.line; name = self.ident("a signal name"); e = N("id", line, name=name)
        while self.is_op("["): e = self.select(e)
        return e

    # ---- expressions
    def expr(self):
        c = self.binary(0)
        if self.is_op("?"):
            line = self.t.line; self.i += 1; a = self.expr(); self.expect_op(":"); b = self.expr(); return N("cond", line, c=c, a=a, b=b)
        return c

    def binary(self, lvl):
        if lvl >= len(BIN_PREC): return self.unary()
        a = self.binary(lvl + 1)
        while self.t.kind == "op" and self.t.val in BIN_PREC[lvl]:
            op = self.t.val; line = self.t.line; self.i += 1; b = self.binary(lvl + 1)
            a = N("bin", line, op="~^" if op == "^~" else op, a=a, b=b)
        return a

    def unary(self):
        t = self.t
        if t.kind == "op" and t.val in ("+", "-", "!", "~", "&", "|", "^", "~&", "~|", "~^", "^~"):
            self.i += 1; x = self.unary(); return N("un", t.line, op="~^" if t.val == "^~" else t.val, x=x)
        return self.primary()

    def select(self, base):
        line = self.t.line; self.expect_op("["); a = self.expr()
        if self.accept_op(":"):
            b = self.expr(); self.expect_op("]"); return N("slice", line, base=base, msb=a, lsb=b)
        if self.is_op("+:") or self.is_op("-:"):
            d = self.t.val; self.i += 1; w = self.expr(); self.expect_op("]"); return N("islice", line, base=base, start=a, width=w, dir=d)
        self.expect_op("]"); return N("index", line, base=base, idx=a)

    def primary(self):
        t = self.t; line = t.line
        if t.kind == "num": self.i += 1; return N("num", line, num=t.val)
        if t.kind == "str": self.i += 1; return N("str", line, val=t.val)
        if t.kind == "sys":
            self.i += 1
            if t.val in ("$signed", "$unsigned", "$clog2"):
                self.expect_op("("); a = self.expr(); self.expect_op(")"); return N("call", line, fn=t.val, arg=a)
            args = []
            if self.accept_op("("):
                while not self.is_op(")"):
                    args.append(self.expr())
                    if not self.accept_op(","): break
                self.expect_op(")")
            return N("sysfn", line, fn=t.val, args=args)
        if t.kind == "op" and t.val == "(":
            self.i += 1; e = self.expr(); self.expect_op(")")
            e = N("paren", line, x=e)
            return e
        if t.kind == "op" and t.val == "{":
            self.i += 1; first = self.expr()
            if self.is_op("{"):                                    # replication {n{...}}
                self.i += 1; parts = [self.expr()]
                while self.accept_op(","): parts.append(self.expr())
                self.expect_op("}"); self.expect_op("}"); return N("repl", line, count=first, parts=parts)
            parts = [first]
            while self.accept_op(","): parts.append(self.expr())
            self.expect_op("}"); return N("concat", line, parts=parts)
        if t.kind == "id":
            if t.val in ("begin", "end", "module", "endmodule", "assign", "always", "wire", "reg", "input", "output"): self.err(f"unexpected '{t.val}' in an expression")
            self.i += 1
            if self.is_op("."): self.err("hierarchical names (a.b) are not supported")
            if self.is_op("("):                                     # function call
                self.i += 1; args = []
                while not self.is_op(")"):
                    args.append(self.expr())
                    if not self.accept_op(","): break
                self.expect_op(")"); return N("fcall", line, name=t.val, args=args)
            e = N("id", line, name=t.val)
            while self.is_op("["): e = self.select(e)
            return e
        got = "the end of the file" if t.kind == "eof" else f"'{t.val}'"
        self.err(f"expected a value but found {got}")


def parse_modules(text):
    p = Parser(text); mods = p.parse(); return mods, p.comments
