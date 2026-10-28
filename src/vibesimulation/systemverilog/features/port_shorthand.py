"""Instance port shorthand: `.clk` means `.clk(clk)`, and `.*` connects every remaining port to the signal of the same name."""
from ..analysis import modules
from ..editor import toks as snippet
from ..feature import Feature, feature
from ..scan import group_end

DIRS = {"input", "output", "inout"}


def port_names(toks, m):
    """Names of the ports in the header of module m."""
    k = m.kw + 2
    while toks[k].text != "(" or toks[k - 1].text == "#":
        if toks[k].text == "#" and toks[k + 1].text == "(": k = group_end(toks, k + 1); continue
        if toks[k].text == ";": return []
        k += 1
    e = group_end(toks, k); names, seg = [], []
    for x in toks[k + 1:e - 1] + [type(toks[0])("op", ",", 0)]:
        if x.kind == "op" and x.text == "," and seg == [] : continue
        if x.kind == "op" and x.text == ",":
            ids = [y.text for y in seg if y.kind == "id" and y.text not in DIRS]
            if ids: names.append(ids[-1])
            seg = []
        else: seg.append(x)
    return names


@feature
class PortShorthand(Feature):
    name = "port_shorthand"
    summary = ".name and .* in instances"
    order = 98
    triggers = (".*", ".")

    def applies(self, ctx): return any(t.kind == "op" and t.text == ".*" for t in ctx.tokens) or any(t.kind == "op" and t.text == "." and ctx.tokens[i + 2].text in (",", ")") for i, t in enumerate(ctx.tokens[:-2]))

    def apply(self, ctx):
        toks = ctx.tokens; ed = ctx.editor(); mods = {m.name: m for m in modules(toks)}
        for i, t in enumerate(toks[:-2]):
            if t.kind == "op" and t.text == "." and toks[i + 1].kind == "id" and toks[i + 2].kind == "op" and toks[i + 2].text in (",", ")") and toks[i - 1].text in ("(", ","):
                n = toks[i + 1]; ed.insert(i + 2, snippet(f"( {n.text} )", n.line))
            elif t.kind == "op" and t.text == ".*":
                open_i = i
                while not (toks[open_i].text == "(" and toks[open_i].kind == "op" and group_end(toks, open_i) > i): open_i -= 1
                k = open_i - 1
                if toks[k].kind == "id" and toks[k - 1].text == ")" : pass
                inst = toks[k]; k -= 1
                if toks[k].text == ")":                                   # `mod #(...) inst (`
                    d = 0
                    while True:
                        if toks[k].text == ")": d += 1
                        elif toks[k].text == "(":
                            d -= 1
                            if d == 0: break
                        k -= 1
                    k -= 2
                mod = toks[k].text
                if mod not in mods and mod not in ctx.known: ctx.fail(t.line, f"'.*' needs the module '{mod}' to be written in this file (it is not): connect its ports by name instead")
                e = group_end(toks, open_i); given = {toks[n + 1].text for n in range(open_i, e) if toks[n].text == "." and toks[n].kind == "op" and toks[n + 1].kind == "id"}
                ports = port_names(toks, mods[mod]) if mod in mods else ctx.known[mod]
                rest = [p for p in ports if p not in given]
                ed.replace(i, i + 1, snippet(", ".join(f".{p}({p})" for p in rest), t.line) or [])
        ctx.commit(ed)
