"""`typedef enum logic [1:0] {IDLE, RUN = 2, DONE} state_t;` and `enum {A, B} x;`

Each member becomes a sized `localparam`; a variable of the enum type is declared with the enum's base type. A base type of `int` (or none)
gets the smallest width that holds the largest value, so a state register stays small (an `int` enum is 32 bits in real SystemVerilog)."""
import math

from ..analysis import parameter_env
from ..consteval import evaluate, range_width
from ..editor import toks as snippet
from ..feature import Feature, feature
from ..lexer import Tok
from ..scan import block_end, group_end, semi_end
from ..typetable import TypeInfo

BASES = {"logic", "bit", "reg", "int", "integer", "byte", "shortint", "longint", "signed", "unsigned"}


def parse_members(ctx, toks, i, line):
    """toks[i] is '{' of an enum body; -> ([(name, value)], index after '}')"""
    e = group_end(toks, i); items, cur, k = [], [], i + 1
    body = toks[i + 1:e - 1]; groups = [[]]
    for t in body:
        if t.text == "," and t.kind == "op": groups.append([])
        else: groups[-1].append(t)
    nxt = 0
    for g in groups:
        g = [t for t in g if t.kind != "comment"]
        if not g: continue
        if g[0].kind != "id": ctx.fail(g[0].line, "an enum member must be a name")
        name = g[0].text
        if len(g) > 1:
            if g[1].text != "=": ctx.fail(g[0].line, f"enum member '{name}': ranges such as {name}[3] are not supported")
            v = evaluate(g[2:], {m: val for m, val in items})
            if v is None: ctx.fail(g[0].line, f"enum member '{name}': the value must be a constant number")
            nxt = v
        items.append((name, nxt)); nxt += 1
    return items, e


@feature
class Enums(Feature):
    name = "enums"
    summary = "enum, typedef enum: members become localparams, the type becomes a vector"
    order = 60
    triggers = ("enum",)

    def apply(self, ctx):
        toks = ctx.tokens; ed = ctx.editor(); i = 0; env = parameter_env(toks)
        while i < len(toks):
            t = toks[i]
            if not (t.kind == "id" and t.text == "enum"): i += 1; continue
            td = i > 0 and toks[i - 1].text == "typedef"
            start = i - 1 if td else i
            j = i + 1; base = []
            while toks[j].kind == "id" and toks[j].text in BASES: base.append(toks[j].text); j += 1
            rng = []
            if toks[j].text == "[": e = group_end(toks, j); rng = toks[j:e]; j = e
            if toks[j].text != "{": ctx.fail(t.line, "an enum needs its members in { }")
            members, j = parse_members(ctx, toks, j, t.line)
            width = range_width(rng, env) if rng else None
            if rng and width is None: ctx.fail(t.line, "the enum's vector size must be a constant")
            if width is None:
                if any(b in ("int", "integer", "longint") for b in base) and False: width = 32
                width = max(1, max(v for _, v in members).bit_length()) if members else 1
            if any(v >= (1 << width) or v < 0 for _, v in members): ctx.fail(t.line, f"an enum value does not fit in {width} bits")
            sign = "signed " if "signed" in base else ""
            head = f"logic {sign}[{width - 1}:0]" if width > 1 else f"logic {sign}".rstrip()
            params = "localparam " + ", ".join(f"{n} = {width}'d{v}" for n, v in members) + ";"
            if td:
                name_i = j
                if toks[name_i].kind != "id": ctx.fail(t.line, "the typedef needs a name")
                ctx.types.define(TypeInfo(toks[name_i].text, head, width, "enum", values=dict(members)))
                end = semi_end(toks, j); ed.replace(start, end, snippet(params, t.line)); i = end
            else:
                end = j                                                    # `enum {A, B} x, y;`: the variables follow the members
                ed.replace(start, end, snippet(params + " " + head, t.line)); i = end
        ctx.commit(ed)
        self.declarations(ctx)

    def declarations(self, ctx):
        """`state_t a, b;` -> `logic [1:0] a, b;`"""
        enums = [t for t in ctx.types.of_kind("enum")]
        if not enums: return
        toks = ctx.tokens; ed = ctx.editor()
        for i, t in enumerate(toks[:-1]):
            if t.kind == "id" and ctx.types.get(t.text) in enums and toks[i + 1].kind == "id" and not (i and toks[i - 1].text in ("typedef", ".", "::")):
                ed.replace(i, i + 1, snippet(ctx.types.get(t.text).head, t.line))
        ctx.commit(ed)
