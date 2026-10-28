"""i++, i--, ++i, x += e, x <<= n ... as statements (and in a for header): rewritten as `x = x + e`."""
from ..analysis import at_statement_start
from ..editor import toks as snippet
from ..feature import Feature, feature
from ..scan import group_end

OPS = {"+=": "+", "-=": "-", "*=": "*", "/=": "/", "%=": "%", "&=": "&", "|=": "|", "^=": "^", "<<=": "<<", ">>=": ">>", "<<<=": "<<<", ">>>=": ">>>"}


def target_end(toks, i):
    j = i + 1
    while toks[j].kind == "op" and toks[j].text in ("[", "."): j = group_end(toks, j) if toks[j].text == "[" else j + 2
    return j


@feature
class CompoundOps(Feature):
    name = "compound_ops"
    summary = "++ -- += -= ... in statements"
    order = 85
    triggers = tuple(OPS) + ("++", "--")

    def apply(self, ctx):
        toks = ctx.tokens; ed = ctx.editor(); i = 0
        while i < len(toks):
            t = toks[i]
            if t.kind == "op" and t.text in ("++", "--") and toks[i + 1].kind == "id" and at_statement_start(toks, i):      # ++x
                j = target_end(toks, i + 1); name = toks[i + 1:j]; text = " ".join(x.text for x in name)
                ed.replace(i, j, snippet(f"{text} = {text} {t.text[0]} 1", t.line)); i = j; continue
            if t.kind == "id" and at_statement_start(toks, i) and t.text not in ("if", "for", "while", "case", "begin", "end", "else", "return", "assign"):
                j = target_end(toks, i); op = toks[j]
                if op.kind == "op" and op.text in ("++", "--"):
                    text = " ".join(x.text for x in toks[i:j])
                    ed.replace(j, j + 1, snippet(f"= {text} {op.text[0]} 1", op.line)); i = j + 1; continue
                if op.kind == "op" and op.text in OPS:
                    text = " ".join(x.text for x in toks[i:j]); k = j + 1; depth = 0
                    while True:
                        x = toks[k]
                        if x.kind == "op" and x.text in ("(", "[", "{"): k = group_end(toks, k); continue
                        if x.kind == "op" and x.text in (";", ",", ")") : break
                        if x.kind == "eof": ctx.fail(op.line, "a ';' is missing")
                        k += 1
                    ed.replace(j, j + 1, snippet(f"= {text} {OPS[op.text]} (", op.line)); ed.insert(k, snippet(")", toks[k - 1].line)); i = k; continue
            i += 1
        ctx.commit(ed)
