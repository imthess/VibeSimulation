"""Fill literals: '0, '1, 'x, 'z take the width of the signal they are assigned to or compared with.

`q <= '0;` -> `q <= {8{1'b0}};`, `if (q == '1)` -> `if (q == {8{1'b1}})`. '0, 'x and 'z need no width when no signal is in sight
(zero and x extend by themselves); '1 does, so it is reported when the width cannot be found."""
from ..analysis import modules, parameter_env
from ..consteval import range_width
from ..editor import toks as snippet
from ..feature import Feature, feature
from ..scan import group_end

DECL = {"reg", "wire", "input", "output", "inout", "integer", "logic", "tri", "signed", "unsigned"}
CMP = {"==", "!=", "===", "!==", "<", ">", "<=", ">="}


def widths(toks, m):
    """{name: width} of the declared vectors of module m (numbers and parameters that are constants)."""
    env = parameter_env(toks, m.kw, m.end)
    out = {}
    for i in range(m.kw, m.end):
        t = toks[i]
        if not (t.kind == "id" and t.text in DECL) or (i and toks[i - 1].text in DECL and toks[i - 1].text not in ("input", "output", "inout")): continue
        j = i
        while toks[j].kind == "id" and toks[j].text in DECL | {"var", "logic"}: j += 1
        w = 1
        if toks[j].text == "[" and toks[j].kind == "op":
            e = group_end(toks, j); w = range_width(toks[j:e], env); j = e
        if t.text == "integer": w = 32
        while toks[j].kind == "id":
            if w is not None: out.setdefault(toks[j].text, w)
            j += 1
            while toks[j].text == "[" and toks[j].kind == "op": j = group_end(toks, j)
            if toks[j].text == "," and toks[j + 1].kind == "id" and toks[j + 1].text not in DECL: j += 1
            else: break
    return out


@feature
class FillLiterals(Feature):
    name = "fill_literals"
    summary = "'0 '1 'x 'z sized from the signal they meet"
    order = 150

    def applies(self, ctx): return any(t.kind == "fill" for t in ctx.tokens)

    def apply(self, ctx):
        toks = ctx.tokens; ed = ctx.editor()
        for m in modules(toks):
            w = widths(toks, m)
            for i in range(m.kw, m.end):
                t = toks[i]
                if t.kind != "fill": continue
                width = self.width(toks, i, w, m)
                digit = t.text[1].lower()
                if width: ed.replace(i, i + 1, snippet(f"{{{width}{{1'b{digit}}}}}", t.line))
                elif digit == "1": ctx.fail(t.line, "'1 needs to meet a signal of known width, for example `q <= '1;` or `if (q == '1)`")
                else: ed.replace(i, i + 1, snippet("0" if digit == "0" else f"'b{digit}", t.line))
        ctx.commit(ed)

    @staticmethod
    def width(toks, i, w, m):
        p, n = toks[i - 1], toks[i + 1]
        if p.kind == "op" and p.text in CMP and toks[i - 2].kind == "id": return w.get(toks[i - 2].text)
        if n.kind == "op" and n.text in CMP and toks[i + 2].kind == "id": return w.get(toks[i + 2].text)
        k = i - 1; depth = 0
        while k > m.kw:                                   # `target = ... '1 ...`: the nearest assignment to the left
            x = toks[k]
            if x.kind == "op" and x.text in (")", "]", "}"): depth += 1
            elif x.kind == "op" and x.text in ("(", "[", "{"):
                if depth == 0: return None
                depth -= 1
            elif x.kind == "op" and x.text == ";" or (x.kind == "id" and x.text in ("begin", "end")): return None
            elif depth == 0 and x.kind == "op" and x.text in ("=", "<="):
                tgt = toks[k - 1]
                return w.get(tgt.text) if tgt.kind == "id" and toks[k - 2].text not in (".",) else None
            k -= 1
        return None
