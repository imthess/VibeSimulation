"""Packages and file-level declarations.

`package p; ... endpackage` and any `typedef`, `parameter`, `localparam` or function written outside every module (the SystemVerilog
"$unit" scope) are copied to the top of each module that imports the package (`import p::*;`, `import p::name;`) or that names one of
its items as `p::name`. File-level items are visible to every module. `p::name` becomes `name`."""
from ...verilog.lexer import VError
from ..analysis import modules
from ..editor import TokenEditor
from ..feature import Feature, feature
from ..scan import block_end, semi_end

ITEM_STARTS = {"typedef", "parameter", "localparam", "function", "task", "enum", "struct"}


def top_level_items(toks, lo, hi):
    """[(start, end)] of the declarations between lo and hi that are packaged (typedef, parameter, function ...)."""
    out, i = [], lo
    while i < hi:
        t = toks[i]
        if t.kind == "id" and t.text in ("typedef", "parameter", "localparam"): e = semi_end(toks, i)
        elif t.kind == "id" and t.text in ("function", "task"): e = block_end(toks, i)
        elif t.kind == "comment": i += 1; continue
        elif t.kind == "id" and t.text in ("import", "export"): e = semi_end(toks, i)
        else: raise VError(f"'{t.text}' cannot be declared here (only typedef, parameter, localparam, function, task and import)", t.line)
        out.append((i, e)); i = e
    return out


@feature
class Packages(Feature):
    name = "packages"
    summary = "package ... endpackage, import p::*, p::name and file-level typedefs / parameters / functions"
    order = 50

    def applies(self, ctx): return True

    def apply(self, ctx):
        toks = ctx.tokens; mods = modules(toks)
        # 1. packages and the loose items between modules
        pkgs, drop, loose = {}, [], []
        i = 0
        while i < len(toks):
            t = toks[i]
            if t.kind == "id" and t.text == "package":
                e = block_end(toks, i); name = toks[i + 1].text; hi = e - 1
                pkgs[name] = (toks, semi_end(toks, i), hi); drop.append((i, e)); i = e; continue
            if t.kind == "id" and t.text in ("module", "macromodule"): i = next(m.end for m in mods if m.kw == i) + 1; continue
            if t.kind == "id" and t.text in ("typedef", "parameter", "localparam", "function", "task"):
                e = block_end(toks, i) if t.text in ("function", "task") else semi_end(toks, i); loose.append((i, e)); drop.append((i, e)); i = e; continue
            i += 1
        if not pkgs and not loose and not any(t.text == "::" for t in toks): return
        items = {name: top_level_items(toks, a, b) for name, (_, a, b) in pkgs.items()}
        unit, seen = [], set()                             # the same file-level item may appear again when module texts are joined
        for a, b in loose:
            key = " ".join(t.text for t in toks[a:b])
            if key not in seen: seen.add(key); unit.append(toks[a:b])
        ed = TokenEditor(toks)
        for a, b in drop: ed.delete(a, b)
        for m in mods:
            used = self.imported(toks, m, pkgs)
            copy = []
            for tl in unit: copy += [self.at(t, toks[m.body - 1].line) for t in tl]
            for p in used:
                for a, b in items[p]:
                    if toks[a].text in ("import", "export"): continue
                    copy += [self.at(t, toks[m.body - 1].line) for t in toks[a:b]]
            if copy: ed.insert(m.body, copy)
            self.in_header(toks, m, used, items, ed)
            self.unscope(toks, m, ed, set(pkgs))
            self.drop_imports(toks, m, ed)
        ctx.commit(ed)

    @staticmethod
    def constants(toks, items):
        """{name: value tokens} of the parameters / localparams among the package items."""
        out = {}
        for a, b in items:
            if toks[a].text not in ("parameter", "localparam"): continue
            k = a + 1; depth = 0
            while k < b - 1:
                if toks[k].kind == "id" and toks[k + 1].text == "=":
                    n = toks[k].text; v = k + 2; e = v
                    while e < b - 1 and not (toks[e].text == "," and depth == 0):
                        depth += {"(": 1, "[": 1, "{": 1, ")": -1, "]": -1, "}": -1}.get(toks[e].text, 0); e += 1
                    out[n] = toks[v:e]; k = e
                k += 1
        return out

    def in_header(self, toks, m, used, items, ed):
        """The header is read before the body's declarations, so a package constant used in it is written out as its value."""
        from ..lexer import Tok
        consts = {}
        for p in used: consts.update(self.constants(toks, items[p]))
        for k in range(m.kw, m.body):
            t = toks[k]
            if t.kind == "id" and t.text in consts and toks[k - 1].text != "." and toks[k + 1].text != "::" and toks[k - 2].text != "import":
                scoped = toks[k - 1].text == "::"
                ed.replace(k - 2 if scoped else k, k + 1, [Tok("op", "(", t.line)] + [self.at(x, t.line) for x in consts[t.text]] + [Tok("op", ")", t.line)])

    @staticmethod
    def at(t, line):
        from ..lexer import Tok
        return Tok(t.kind, t.text, line)

    def imported(self, toks, m, pkgs):
        used = []
        for k in range(m.kw, m.end):
            if toks[k].kind == "id" and toks[k].text == "import" and toks[k + 2].text == "::":
                p = toks[k + 1].text
                if p not in pkgs: raise VError(f"there is no package '{p}' in this file", toks[k].line)
                if p not in used: used.append(p)
            elif toks[k].kind == "op" and toks[k].text == "::" and toks[k - 1].text in pkgs and toks[k - 1].text not in used: used.append(toks[k - 1].text)
        return used

    @staticmethod
    def unscope(toks, m, ed, pkgnames):
        for k in range(m.body, m.end):
            if toks[k].kind == "op" and toks[k].text == "::" and toks[k - 1].text in pkgnames and not (toks[k - 2].text == "import"): ed.delete(k - 1, k + 1)

    @staticmethod
    def drop_imports(toks, m, ed):
        k = m.kw
        while k < m.end:
            if toks[k].kind == "id" and toks[k].text == "import" and toks[k + 2].text == "::":
                e = k
                while toks[e].text != ";": e += 1
                ed.delete(k, e + 1); k = e
            k += 1
