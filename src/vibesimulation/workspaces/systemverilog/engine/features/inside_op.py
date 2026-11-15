"""`a inside {1, 2, [4:7]}` becomes a chain of comparisons; `case (x) inside` becomes casez."""
from ..editor import toks as snippet
from ..feature import Feature, feature
from ..scan import group_end


@feature
class InsideOp(Feature):
    name = "inside_op"
    summary = "the inside operator"
    order = 86
    triggers = ("inside",)

    def apply(self, ctx):
        toks = ctx.tokens; ed = ctx.editor()
        for i, t in enumerate(toks):
            if not (t.kind == "id" and t.text == "inside"): continue
            if toks[i - 1].text == ")" and self.is_case(toks, i): ed.replace(i, i + 1, []); continue
            # left operand: a name with selects, a number, or a parenthesised expression
            s = i - 1
            if toks[s].text == ")":
                d = 0
                while True:
                    if toks[s].text == ")": d += 1
                    elif toks[s].text == "(":
                        d -= 1
                        if d == 0: break
                    s -= 1
            else:
                while toks[s].text == "]":
                    d = 0
                    while True:
                        if toks[s].text == "]": d += 1
                        elif toks[s].text == "[":
                            d -= 1
                            if d == 0: break
                        s -= 1
                    s -= 1
            left = " ".join(x.text for x in toks[s:i])
            if toks[i + 1].text != "{": ctx.fail(t.line, "after 'inside' write a list in { }")
            e = group_end(toks, i + 1); parts, cur, k = [], [], i + 2
            while k < e - 1:
                x = toks[k]
                if x.text == "[" and x.kind == "op":
                    g = group_end(toks, k); parts.append(("range", toks[k + 1:g - 1])); k = g
                    if toks[k].text == ",": k += 1
                    continue
                if x.text == "," and x.kind == "op": k += 1; continue
                parts.append(("one", [x])); k += 1
            tests = []
            for kind, ts in parts:
                if kind == "one": tests.append(f"{left} == {ts[0].text}")
                else:
                    c = next(n for n, y in enumerate(ts) if y.text == ":")
                    tests.append(f"({left} >= {' '.join(y.text for y in ts[:c])} && {left} <= {' '.join(y.text for y in ts[c + 1:])})")
            ed.replace(s, e, snippet("(" + " || ".join(tests) + ")", t.line))
        ctx.commit(ed)

    @staticmethod
    def is_case(toks, i):
        d = 0; j = i - 1
        while j >= 0:
            if toks[j].text == ")": d += 1
            elif toks[j].text == "(":
                d -= 1
                if d == 0: return toks[j - 1].text in ("case", "casez", "casex")
            j -= 1
        return False
