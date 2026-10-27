"""generate for / if / case: the blocks are unrolled into plain module items before anything is built.

A named block `begin : g ... end` repeated by a loop gives every net it declares the name `g_<n>_<net>`; genvars and
localparams of the block are replaced by their numbers. (Hierarchical names such as g[2].w are not supported.)
"""
from .astutil import clone
from .lexer import VError

MAX_ITER = 4096


class GenerateMixin:
    def expand_items(self, items, env=None, rename=None, scope=""):
        out = []; env = env or {}; rename = rename or {}
        for it in items:
            k = it.kind
            if k == "genblock": out += self.gen_block(it, env, rename, scope)
            elif k == "genfor": out += self.gen_for(it, env, rename, scope)
            elif k == "genif":
                br = it.then if self.gen_ci(it.cond, env, rename) else it.els
                if br is not None: out += self.gen_block(br, env, rename, self.gscope(scope, br, ""))
            elif k == "gencase":
                v = self.gen_ci(it.expr, env, rename); chosen = None
                for labels, body in it.items:
                    if any(self.gen_ci(l, env, rename) == v for l in labels): chosen = body; break
                if chosen is None: chosen = it.default
                if chosen is not None: out += self.gen_block(chosen, env, rename, self.gscope(scope, chosen, ""))
            elif k == "param" and env is not None and scope:
                env[it.name] = self.gen_ci(it.value, env, rename)
            else:
                out.append(clone(it, env, rename, scope) if (env or rename or scope) else it)
        return out

    def gscope(self, parent, block, idx):
        name = block.label or f"genblk{block.line}"
        return "_".join(x for x in (parent, name, str(idx) if idx != "" else "") if x)

    def gen_ci(self, e, env, rename):
        try: return self.ci(clone(e, env, rename))
        except VError as ex: raise VError(ex.msg + " (a generate condition may only use numbers, parameters and genvars)", ex.line)

    def gen_block(self, block, env, rename, scope):
        env = dict(env); rename = dict(rename)
        for it in block.items:                                       # nets declared inside the block get a private name
            if it.kind == "net":
                for nm, _, _ in it.names:
                    if scope: rename[nm] = f"{scope}_{nm}"
        # localparams first (in order), they may use each other
        out = []
        for it in block.items:
            if it.kind == "param": env[it.name] = self.gen_ci(it.value, env, rename)
        rest = [it for it in block.items if it.kind != "param"]
        return self.expand_items(rest, env, rename, scope)

    def gen_for(self, it, env, rename, scope):
        out = []; v = it.var
        val = self.gen_ci(it.init, env, rename); n = 0
        while True:
            env2 = dict(env); env2[v] = val
            if not self.gen_ci(it.cond, env2, rename): break
            n += 1
            if n > MAX_ITER: raise VError(f"the generate loop runs more than {MAX_ITER} times", it.line)
            out += self.gen_block(it.body, env2, rename, self.gscope(scope, it.body, val if val >= 0 else f"m{-val}"))
            if it.stepvar != v: raise VError("the generate loop must change its own variable", it.line)
            val = self.gen_ci(it.step, env2, rename)
        return out
