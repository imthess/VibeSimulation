"""`parameter int W = 8`, `localparam logic [3:0] X = 4'h1`: the type is dropped (a range is kept)."""
from ..feature import Feature, feature
from ..lexer import Tok

TYPES = {"int", "integer", "logic", "bit", "byte", "shortint", "longint", "reg", "signed", "unsigned"}


@feature
class TypedParams(Feature):
    name = "typed_params"
    summary = "types on parameter / localparam"
    order = 110
    triggers = ("parameter", "localparam")

    def apply(self, ctx):
        ed = ctx.editor(); toks = ctx.tokens
        for i, t in enumerate(toks):
            if t.kind != "id" or t.text not in ("parameter", "localparam"): continue
            j = i + 1
            if toks[j].text == "type": ctx.fail(t.line, "SystemVerilog: 'parameter type' is not supported")
            k = j
            while toks[k].kind == "id" and toks[k].text in TYPES: k += 1
            if k > j:
                ed.delete(j, k)
                if toks[k - 1].text in ("signed",) or any(x.text == "signed" for x in toks[j:k]): ed.insert(j, [Tok("id", "signed", t.line)])
        ctx.commit(ed)
