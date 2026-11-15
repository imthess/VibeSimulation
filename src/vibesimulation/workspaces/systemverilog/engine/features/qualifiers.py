"""Words that only matter to simulation or synthesis tools: automatic, static, var, const ... They are dropped."""
from ..feature import Feature, feature

DROP = {"automatic", "static", "var", "const", "timeunit", "timeprecision"}


@feature
class Qualifiers(Feature):
    name = "qualifiers"
    summary = "automatic / static / var are dropped"
    order = 40
    triggers = tuple(DROP)

    def apply(self, ctx):
        ed = ctx.editor(); toks = ctx.tokens
        for i, t in enumerate(toks):
            if t.kind != "id" or t.text not in DROP: continue
            if t.text in ("timeunit", "timeprecision"):
                j = i
                while toks[j].text != ";" and toks[j].kind != "eof": j += 1
                ed.delete(i, j + 1)
            else: ed.delete(i, i + 1)
        ctx.commit(ed)
