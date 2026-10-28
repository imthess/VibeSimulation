"""Casts: `signed'(x)`, `unsigned'(x)`, `int'(x)`, `8'(x)`, `state_t'(x)`."""
from ..editor import toks as snippet
from ..feature import Feature, feature
from ..scan import group_end

INTS = {"int", "integer", "byte", "shortint", "longint"}


@feature
class Casts(Feature):
    name = "casts"
    summary = "type'(expr) and size'(expr) casts"
    order = 72
    triggers = ("'",)

    def apply(self, ctx):
        toks = ctx.tokens; ed = ctx.editor()
        for i, t in enumerate(toks[:-2]):
            if not (t.kind == "op" and t.text == "'" and toks[i + 1].text == "("): continue
            e = group_end(toks, i + 1); inner = " ".join(x.text for x in toks[i + 2:e - 1]); p = toks[i - 1]
            if p.kind == "id" and p.text == "signed": new = f"$signed({inner})"
            elif p.kind == "id" and p.text == "unsigned": new = f"$unsigned({inner})"
            elif p.kind == "id" and (p.text in INTS or p.text in ctx.types): new = f"({inner})"; ctx.warn(t.line, f"the cast to {p.text} only changes the width through the context it is used in")
            elif p.kind == "num" or p.kind == "id": new = f"(({inner}) & {{{p.text}{{1'b1}}}})"
            elif p.text == ")":
                s = i - 1; d = 0
                while True:
                    if toks[s].text == ")": d += 1
                    elif toks[s].text == "(":
                        d -= 1
                        if d == 0: break
                    s -= 1
                size = " ".join(x.text for x in toks[s:i]); new = f"(({inner}) & {{{size}{{1'b1}}}})"; ed.replace(s, e, snippet(new, t.line)); continue
            else: ctx.fail(t.line, "SystemVerilog: this cast is not supported")
            ed.replace(i - 1, e, snippet(new, t.line))
        ctx.commit(ed)
