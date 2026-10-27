"""function and task calls inside a circuit: the body is built right where it is called (inlined).

Arguments are evaluated at the call, the body runs on private nets (shadowing module nets of the same name), and the
value assigned to the function's own name is the result. Recursion is not supported (a circuit cannot be infinite).
Tasks work the same way; their `output` arguments are copied to the caller's variables after the body.
"""
from ..core.bits import mask
from .lexer import VError

MAX_DEPTH = 16


class SubprogramMixin:
    def register_subprograms(self, items):
        for it in items:
            if it.kind in ("function", "task"):
                table = self.funcs if it.kind == "function" else self.tasks
                if it.name in table: self.err(f"'{it.name}' is defined twice", it.line)
                table[it.name] = it

    def ret_info(self, f):
        if f.integer: return 32, True
        w, _ = self.rng(f.rng); return w, f.signed

    def fn_info(self, e):
        f = self.funcs.get(e.name)
        if f is None: self.err(f"function '{e.name}' is not defined", e.line)
        w, s = self.ret_info(f); return (w, s, True)

    # ---- private nets for one call
    def _enter(self, sub, extra):
        saved = {}; made = {}
        def decl(nm, w, sg, pre=None, kind="reg"):
            saved.setdefault(nm, self.nets.get(nm))
            from .elab import Net
            n = Net(nm, w, sg, kind, sub.line); n.is_reg = True; n.pre = pre; self.nets[nm] = n; made[nm] = n
        for item in extra: decl(*item)
        saved_params = {}
        for d in sub.decls:
            if d.kind == "net":
                for nm, init, ln in d.names:
                    if nm in d.arrays: self.err("memories inside a function or task are not supported", ln)
                    w, _ = (32, 0) if d.netkind == "integer" else self.rng(d.rng)
                    decl(nm, w, d.netkind == "integer" or bool(d.signed))
            elif d.kind == "param":
                saved_params[d.name] = self.params.get(d.name)
                self.params[d.name] = (self.ci(d.value), 32, True)
        return saved, saved_params, made

    def _leave(self, saved, saved_params):
        for nm, old in saved.items():
            if old is None: self.nets.pop(nm, None)
            else: self.nets[nm] = old
        for nm, old in saved_params.items():
            if old is None: self.params.pop(nm, None)
            else: self.params[nm] = old

    def _run_body(self, sub, saved_extra, seq=False):
        from .elab import Mod
        saved_env = self.env; fenv = Mod.Env(); self.env = fenv
        try:
            self.exec(sub.body, fenv, seq)
        finally: self.env = saved_env
        return fenv

    # ---- function call in an expression
    def call_function(self, e):
        f = self.funcs.get(e.name)
        if f is None: self.err(f"function '{e.name}' is not defined", e.line)
        if e.name in self.fstack: self.err(f"function '{e.name}' calls itself: recursion is not supported in a circuit", e.line)
        if len(self.fstack) >= MAX_DEPTH: self.err("functions are nested too deeply", e.line)
        ins = [a for a in f.args if a[1] == "input"]
        if len(e.args) != len(f.args) or len(ins) != len(f.args): self.err(f"function '{e.name}' takes {len(ins)} input(s) and no outputs", e.line)
        vals = []
        for (nm, d, rng, sg), a in zip(f.args, e.args):
            w, _ = self.rng(rng); vals.append(self.fit(a, w))
        rw, rs = self.ret_info(f)
        extra = [(nm, self.rng(rng)[0], sg, v) for (nm, d, rng, sg), v in zip(f.args, vals)] + [(f.name, rw, rs)]
        saved, sp, made = self._enter(f, extra)
        self.fstack.append(f.name); line = self.line
        try:
            fenv = self._run_body(f, saved)
            r = fenv.rd.get(f.name)
            res = self.mat(r, rw, made[f.name])
        finally:
            self.fstack.pop(); self._leave(saved, sp)
        self.line = line
        return res

    # ---- task call as a statement
    def exec_taskcall(self, st, env, seq):
        t = self.tasks.get(st.name)
        if t is None: self.err(f"task '{st.name}' is not defined", st.line)
        if st.name in self.fstack: self.err(f"task '{st.name}' calls itself: recursion is not supported in a circuit", st.line)
        if len(st.args) != len(t.args): self.err(f"task '{st.name}' takes {len(t.args)} argument(s)", st.line)
        self.env = env; extra = []; outs = []
        for (nm, d, rng, sg), a in zip(t.args, st.args):
            w, _ = self.rng(rng)
            if d == "input": extra.append((nm, w, sg, self.fit(a, w)))
            else:
                if d == "inout": self.err("inout task arguments are not supported", st.line)
                extra.append((nm, w, sg)); outs.append((nm, a, w))
        saved, sp, made = self._enter(t, extra)
        self.fstack.append(t.name); line = self.line
        try:
            fenv = self._run_body(t, saved, seq)
            results = [(self.mat(fenv.rd.get(nm), w, made[nm]), a) for nm, a, w in outs]
        finally:
            self.fstack.pop(); self._leave(saved, sp)
        self.line = line; self.env = env
        for v, a in results:
            parts = self.lv_parts(a); L = sum(hi - lo + 1 for _, lo, hi in parts)
            self.store(parts, self.b.ext(v, L, False), env, True)
