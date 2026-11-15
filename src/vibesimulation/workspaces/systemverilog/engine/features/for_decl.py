"""`for (int i = 0; ...)` and `for (genvar i = 0; ...)`: the loop variable is declared once, where Verilog wants it.

Inside always / initial the `integer i;` goes before the block (module level); inside a function or task it goes at the top of the body;
a genvar is declared right before its loop."""
from ..analysis import modules, procedural_regions
from ..editor import toks as snippet
from ..feature import Feature, feature
from ..scan import block_end, group_end

INT_WORDS = {"int", "integer", "byte", "shortint", "longint", "logic", "bit"}


@feature
class ForDecl(Feature):
    name = "for_decl"
    summary = "variables declared in a for header"
    order = 80
    triggers = ("for",)

    def apply(self, ctx):
        toks = ctx.tokens; ed = ctx.editor()
        for m in modules(toks):
            done = set(); regions = procedural_regions(toks, m.body, m.end)
            funcs = [(i, block_end(toks, i)) for i in range(m.body, m.end) if toks[i].kind == "id" and toks[i].text in ("function", "task")]
            for i in range(m.body, m.end):
                t = toks[i]
                if not (t.kind == "id" and t.text == "for" and toks[i + 1].text == "("): continue
                e = group_end(toks, i + 1); j = i + 2
                gen = toks[j].text == "genvar"
                if not gen and not (toks[j].kind == "id" and toks[j].text in INT_WORDS and toks[j + 1].kind == "id"): continue
                k = j
                while toks[k].text not in (";",) and k < e: k += 1
                names = [toks[n].text for n in range(j + 1, k) if toks[n].kind == "id" and toks[n + 1].text == "=" and (toks[n - 1].text in ("int", "integer", "byte", "shortint", "longint", "logic", "bit", "genvar", ",") or n == j + 1)]
                if not names: names = [toks[j + 1].text]
                if gen: ed.insert(i, snippet("genvar " + ", ".join(names) + ";", t.line)); ed.delete(j, j + 1); continue
                ed.delete(j, j + 1)
                where = next(((a, b) for a, b in funcs if a < i < b), None)
                if where:
                    h = where[0]
                    while toks[h].text != ";": h += 1
                    at = h + 1; key = ("f", where[0])
                else:
                    reg = next((a for a, b in regions if a <= i < b), None)
                    if reg is None: ctx.fail(t.line, "a loop variable can only be declared in a for loop inside always, initial, a function or a task (use genvar in a generate loop)")
                    at = reg; key = ("m", m.kw)
                new = [n for n in names if (key, n) not in done]
                for n in new: done.add((key, n))
                if new: ed.insert(at, snippet("integer " + ", ".join(new) + ";", toks[at].line))
        ctx.commit(ed)
