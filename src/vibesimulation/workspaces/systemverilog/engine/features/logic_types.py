"""logic, bit, int, byte, shortint, longint in ports, declarations, functions and loops -> reg / wire / integer.

`logic` can be driven either way, Verilog needs to know: a name assigned inside always / initial becomes `reg`, anything else `wire`
(an output that is not assigned in a process is left as a plain output, which is a wire). A declaration with names of both kinds is
split. `bit` is treated like `logic` (two-state checking is not done); `int` is `integer`; `byte`, `shortint`, `longint` are signed vectors."""
from ..analysis import modules, procedural_regions, procedural_targets
from ..editor import toks as snippet
from ..feature import Feature, feature
from ..scan import block_end, group_end, semi_end

TYPE_WORDS = {"logic", "bit", "int", "byte", "shortint", "longint"}
SIZED = {"int": 32, "byte": 8, "shortint": 16, "longint": 64}
DIRS = {"input", "output", "inout"}
NETS = {"wire", "tri", "wand", "wor", "supply0", "supply1", "reg"}
NOT_A_NAME = DIRS | TYPE_WORDS | NETS | {"signed", "unsigned", "integer"}


class Head:
    """The type part of a declaration: words (logic, signed ...) and an optional [range]."""
    def __init__(self, toks, i):
        self.start, j, self.words, self.range = i, i, [], []
        while toks[j].kind == "id" and (toks[j].text in TYPE_WORDS or toks[j].text in ("signed", "unsigned", "integer", "reg")):
            self.words.append(toks[j].text); j += 1
        if toks[j].text == "[" and toks[j].kind == "op": e = group_end(toks, j); self.range = toks[j:e]; j = e
        self.end = j
        self.kind = next((w for w in self.words if w in TYPE_WORDS or w == "integer"), "reg")
        self.signed = "signed" in self.words or (self.kind in SIZED and "unsigned" not in self.words)
        self.integer = self.kind in ("int", "integer")

    def vector(self):
        """`signed [7:0]` (what is left of the type once reg / wire is chosen)."""
        parts = []
        if self.signed: parts.append("signed")
        if self.range: parts.append(" ".join(x.text for x in self.range))
        elif self.kind in SIZED: parts.append(f"[{SIZED[self.kind] - 1}:0]")
        return " ".join(parts)

    def decl(self, word):
        """The type as a Verilog declaration head for `reg`, `wire` or no word at all."""
        if self.integer and word == "reg": return "integer"
        return (word + " " + self.vector()).strip()


@feature
class LogicTypes(Feature):
    name = "logic_types"
    summary = "logic / bit / int / byte ... to reg, wire and integer"
    order = 120
    triggers = tuple(TYPE_WORDS)

    def apply(self, ctx):
        toks = ctx.tokens; ed = ctx.editor(); self.named = set()
        for m in modules(toks):
            targets = procedural_targets(toks, m)
            local = procedural_regions(toks, m.body, m.end) + [(i, block_end(toks, i)) for i in range(m.body, m.end) if toks[i].kind == "id" and toks[i].text in ("function", "task")]
            i = m.kw
            while i < m.end:
                t = toks[i]
                if not (t.kind == "id" and t.text in TYPE_WORDS) or toks[i - 1].text in (".", "'", "::") or toks[i + 1].text == "'":
                    i += 1; continue
                head = Head(toks, i); prev = toks[i - 1]; in_local = any(a < i < b for a, b in local)
                if prev.text in DIRS or (prev.text in ("signed", "unsigned") and toks[i - 2].text in DIRS): i = self.port(toks, ed, head, prev, targets, in_local)
                elif in_local and prev.text in ("(", ","):                      # a function argument without a direction is an input
                    ed.replace(i, head.end, snippet(("input " + head.decl("")).strip(), t.line)); i = head.end
                elif prev.text == "function": i = self.return_type(toks, ed, head)
                elif in_local: i = self.local(toks, ed, head)
                else: i = self.declaration(toks, ed, head, prev, targets)
        ctx.commit(ed)

    @staticmethod
    def names(toks, j):
        """[(name, index)] of the comma separated names after a type, up to ';', ')' or a ',' that starts another declaration."""
        out = []
        while toks[j].kind == "id":
            out.append((toks[j].text, j)); j += 1
            while toks[j].text == "[" and toks[j].kind == "op": j = group_end(toks, j)
            if toks[j].text == "=" and toks[j].kind == "op":
                while not (toks[j].kind == "op" and toks[j].text in (",", ";", ")")): j = group_end(toks, j) if toks[j].kind == "op" and toks[j].text in ("(", "[", "{") else j + 1
            if toks[j].text == "," and toks[j + 1].kind == "id" and toks[j + 1].text not in NOT_A_NAME: j += 1; continue
            break
        return out, j

    def port(self, toks, ed, head, prev, targets, in_func):
        """`input logic [7:0] a` -> `input [7:0] a`; `output logic q` -> `output reg q` when q is assigned in a process."""
        i, j, line = head.start, head.end, toks[head.start].line
        d = prev.text if prev.text in DIRS else toks[head.start - 2].text
        names, _ = self.names(toks, j)
        reg = lambda n: (not in_func) and d == "output" and n in targets
        first_reg = bool(names) and reg(names[0][0])
        ed.replace(i, j, snippet(head.decl("reg" if first_reg else ""), line))
        for n in range(1, len(names)):                                        # a later name of the other kind needs its own head
            if reg(names[n][0]) != reg(names[n - 1][0]):
                ed.insert(names[n][1], snippet(f"{d} {head.decl('reg' if reg(names[n][0]) else '')}".strip(), toks[names[n][1]].line))
        return j

    def return_type(self, toks, ed, head):
        """`function logic [7:0] f` -> `function [7:0] f`; `function int f` -> `function integer f`."""
        ed.replace(head.start, head.end, snippet("integer" if head.integer else head.vector(), toks[head.start].line)); return head.end

    def name_block(self, toks, ed, i):
        """Verilog only allows declarations in a *named* begin..end: give the block a name."""
        depth, j = 0, i - 1
        while j >= 0:
            if toks[j].kind == "id" and toks[j].text == "end": depth += 1
            elif toks[j].kind == "id" and toks[j].text == "begin":
                if depth == 0:
                    if toks[j + 1].text != ":" and j not in self.named: self.named.add(j); ed.insert(j + 1, snippet(f": sv_block_{toks[j].line}_{j}", toks[j].line))
                    return
                depth -= 1
            j -= 1

    def local(self, toks, ed, head):
        """Inside a process, function or task a declared name is a variable."""
        self.name_block(toks, ed, head.start)
        ed.replace(head.start, head.end, snippet(head.decl("reg"), toks[head.start].line)); return head.end

    def declaration(self, toks, ed, head, prev, targets):
        """A module-level declaration: reg for names assigned in processes, wire for the others; split when mixed."""
        i, j, line = head.start, head.end, toks[head.start].line
        if prev.text in NETS:                                    # `wire logic [3:0] w`: the net keyword already says what it is
            ed.replace(i, j, snippet(head.vector(), line)); return j
        names, _ = self.names(toks, j)
        if not names: return j
        e = semi_end(toks, i); bounds = [n[1] for n in names] + [e]
        groups = []
        for n, (name, a) in enumerate(names):
            end = bounds[n + 1] - 1                              # drops the ',' (or the ';' for the last one)
            groups.append((name, a, end))
        runs = []                                                # consecutive names of the same kind share one statement
        for name, a, b in groups:
            kind = "reg" if (name in targets or head.integer) else "wire"
            if runs and runs[-1][0] == kind: runs[-1][1].append((a, b))
            else: runs.append((kind, [(a, b)]))
        new = []
        for kind, items in runs:
            new += snippet(head.decl(kind), line)
            for n, (a, b) in enumerate(items):
                if n: new += snippet(",", toks[a].line)
                new += toks[a:b]
            new += snippet(";", toks[e - 1].line)
        ed.replace(i, e, new); return e
