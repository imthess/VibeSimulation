"""`typedef struct packed { logic [3:0] a; logic [3:0] b; } pair_t;`

A packed struct is one vector: the first field takes the top bits. A variable of the type is declared as that vector and `s.a`
becomes the matching slice `s[7:4]`, so the circuit is built from plain bit selects. Unpacked structs are not supported."""
from ..analysis import modules, parameter_env
from ..consteval import range_width
from ..editor import toks as snippet
from ..feature import Feature, feature
from ..scan import group_end, semi_end
from ..typetable import TypeInfo

SIZES = {"byte": 8, "shortint": 16, "int": 32, "longint": 64, "integer": 32, "logic": 1, "bit": 1, "reg": 1}
NOT_NAMES = {"input", "output", "inout", "logic", "bit", "reg", "wire", "int", "byte", "signed", "unsigned", "integer", "parameter", "localparam", "assign", "always", "initial"}


def field_width(ctx, words, rng, line, env):
    if rng:
        w = range_width(rng, env)
        if w is None: ctx.fail(line, "a struct field's size must be a constant number such as [7:0]")
        return w
    for w in words:
        if w in SIZES: return SIZES[w]
        info = ctx.types.get(w)
        if info is not None and info.width: return info.width
    ctx.fail(line, f"cannot tell how wide the struct field type '{' '.join(words)}' is")


@feature
class Structs(Feature):
    name = "structs"
    summary = "packed structs become vectors; s.field becomes a bit slice"
    order = 65
    triggers = ("struct",)

    def apply(self, ctx):
        toks = ctx.tokens; ed = ctx.editor(); vars_by_module = []
        for m in modules(toks):
            self.define(ctx, toks, m, ed)
            vars_by_module.append((m, self.declare(ctx, toks, m, ed)))
        for m, vs in vars_by_module: self.slices(ctx, toks, m, vs, ed)
        ctx.commit(ed)

    def define(self, ctx, toks, m, ed):
        i = m.body; env = parameter_env(toks, m.kw, m.end)
        while i < m.end:
            t = toks[i]
            if t.kind == "id" and t.text == "struct":
                td = toks[i - 1].text == "typedef"
                if not td: ctx.fail(t.line, "SystemVerilog: a struct must be given a name with typedef")
                j = i + 1
                if toks[j].text != "packed": ctx.fail(t.line, "SystemVerilog: only packed structs are supported (write 'struct packed')")
                j += 1
                while toks[j].text in ("signed", "unsigned"): j += 1
                if toks[j].text != "{": ctx.fail(t.line, "a struct needs its fields in { }")
                e = group_end(toks, j); fields = []; k = j + 1
                while k < e - 1:
                    if toks[k].kind == "comment": k += 1; continue
                    s_end = semi_end(toks, k); seg = [x for x in toks[k:s_end - 1] if x.kind != "comment"]
                    words = []; rng = []; n = 0
                    while n < len(seg) and seg[n].kind == "id" and (seg[n].text in SIZES or seg[n].text in ("signed", "unsigned") or seg[n].text in ctx.types): words.append(seg[n].text); n += 1
                    if n < len(seg) and seg[n].text == "[": ge = group_end(seg, n); rng = seg[n:ge]; n = ge
                    w = field_width(ctx, words, rng, seg[0].line, env)
                    for part in " ".join(x.text for x in seg[n:]).split(","):
                        if part.strip(): fields.append((part.strip(), w))
                    k = s_end
                total = sum(w for _, w in fields); hi = total; table = {}
                for name, w in fields: table[name] = (hi - 1, hi - w); hi -= w
                name_i = e
                if toks[name_i].kind != "id": ctx.fail(t.line, "the typedef needs a name")
                head = f"logic [{total - 1}:0]" if total > 1 else "logic"
                ctx.types.define(TypeInfo(toks[name_i].text, head, total, "struct", fields=table))
                end = semi_end(toks, e); ed.replace(i - 1, end, []); i = end; continue
            i += 1

    def declare(self, ctx, toks, m, ed):
        """Replace `pair_t a, b;` by the vector type and remember which names are structs: {name: TypeInfo}."""
        mine = {}; structs = {t.name for t in ctx.types.of_kind("struct")}
        for i in range(m.kw, m.end - 1):
            t = toks[i]
            if t.kind == "id" and t.text in structs and toks[i + 1].kind == "id" and toks[i - 1].text not in ("typedef", ".", "::"):
                info = ctx.types.get(t.text); ed.replace(i, i + 1, snippet(info.head, t.line)); j = i + 1
                while True:
                    mine[toks[j].text] = info
                    if toks[j + 1].text == "," and toks[j + 2].kind == "id" and toks[j + 2].text not in NOT_NAMES: j += 2
                    else: break
        return mine

    def slices(self, ctx, toks, m, vs, ed):
        if not vs: return
        for i in range(m.body, m.end - 2):
            t = toks[i]
            if t.kind == "id" and t.text in vs and toks[i + 1].text == "." and toks[i + 2].kind == "id" and toks[i - 1].text != ".":
                info = vs[t.text]; f = toks[i + 2].text
                if f not in info.fields: ctx.fail(t.line, f"the struct type '{info.name}' has no field '{f}'")
                hi, lo = info.fields[f]
                ed.replace(i + 1, i + 3, snippet(f"[{hi}]" if hi == lo else f"[{hi}:{lo}]", t.line))
