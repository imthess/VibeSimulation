"""`unique case`, `priority case`, `unique if` ...: the qualifier is a promise to the synthesis tool; the case / if behaves as written."""
from ..feature import Feature, feature

FOLLOWERS = {"case", "casez", "casex", "if"}


@feature
class UniquePriority(Feature):
    name = "unique_priority"
    summary = "unique / unique0 / priority before case and if"
    order = 41
    triggers = ("unique", "unique0", "priority")

    def apply(self, ctx):
        ed = ctx.editor(); toks = ctx.tokens
        for i, t in enumerate(toks[:-1]):
            if t.kind == "id" and t.text in ("unique", "unique0", "priority") and toks[i + 1].text in FOLLOWERS:
                ed.delete(i, i + 1); ctx.warn(t.line, f"'{t.text}' is accepted but not checked: the {toks[i + 1].text} behaves as written")
        ctx.commit(ed)
