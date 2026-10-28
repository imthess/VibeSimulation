"""`typedef logic [7:0] byte_t;` : the name stands for what it was defined as."""
from ..analysis import parameter_env
from ..consteval import range_width
from ..editor import toks as snippet
from ..feature import Feature, feature
from ..lexer import Tok
from ..scan import semi_end
from ..typetable import TypeInfo
from .structs import SIZES

WORDS = set(SIZES) | {"signed", "unsigned"}


@feature
class Typedefs(Feature):
    name = "typedefs"
    summary = "typedef of plain types (logic [7:0], int ...)"
    order = 70
    triggers = ("typedef",)

    def apply(self, ctx):
        toks = ctx.tokens; ed = ctx.editor(); i = 0; env = parameter_env(toks)
        while i < len(toks):
            t = toks[i]
            if not (t.kind == "id" and t.text == "typedef"): i += 1; continue
            e = semi_end(toks, i); body = [x for x in toks[i + 1:e - 1] if x.kind != "comment"]
            if body and body[-1].text == "]": ctx.fail(t.line, "SystemVerilog: arrays in a typedef are not supported")
            if not body or body[-1].kind != "id": ctx.fail(t.line, "the typedef needs a name")
            name = body[-1].text; defn = body[:-1]
            if not defn: ctx.fail(t.line, "the typedef needs a type")
            text = " ".join(x.text for x in defn)
            words = [x.text for x in defn if x.kind == "id"]
            width = None
            if "[" in text:
                k = next(n for n, x in enumerate(defn) if x.text == "[")
                width = range_width(defn[k:], env)
            else:
                for w in words:
                    if w in SIZES and w not in ("signed", "unsigned"): width = SIZES[w]; break
                    if w in ctx.types and ctx.types.get(w).width: width = ctx.types.get(w).width
            first = ctx.types.get(words[0]) if words and words[0] in ctx.types else None
            if first is not None: text = first.head + " " + " ".join(x.text for x in defn[1:])
            ctx.types.define(TypeInfo(name, text, width, "alias"))
            ed.delete(i, e); i = e
        ctx.commit(ed); self.uses(ctx)

    def uses(self, ctx):
        aliases = {t.name for t in ctx.types.of_kind("alias")}
        if not aliases: return
        toks = ctx.tokens; ed = ctx.editor()
        for i, t in enumerate(toks[:-1]):
            if t.kind == "id" and t.text in aliases and toks[i + 1].kind == "id" and toks[i - 1].text not in (".", "::", "typedef"): ed.replace(i, i + 1, snippet(ctx.types.get(t.text).head, t.line))
        ctx.commit(ed)
