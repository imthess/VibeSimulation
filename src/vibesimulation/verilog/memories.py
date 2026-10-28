"""Memories: `reg [7:0] mem [0:15];`

How a memory becomes parts (decided once the whole module has been read):
  * never written, filled by an `initial` block            -> a ROM per read address
  * one clocked write, every read uses the write address   -> one RAM (asynchronous read, so `assign q = mem[a]` works
                                                              and `q <= mem[a]` in a clocked block reads the old word)
  * anything else (register file, two read addresses ...)  -> one Register per word, a decoder for the write enable
                                                              and a multiplexer tree per read (at most 256 words)
Reading an address past the end gives 0 (Verilog gives x). Writing past the end does nothing.
"""
from ..components.registry import ComponentRegistry as R
from ..core.bits import mask
from .lexer import VError

MAX_REG_WORDS = 256


def clog2(n): return max(0, (n - 1).bit_length())


class Mem:
    def __init__(self, name, w, signed, depth, line):
        self.name, self.w, self.signed, self.depth, self.line = name, w, signed, depth, line
        self.writes = []      # (clock V, trigger, addr V, data V, enable V | None, line)
        self.reads = []       # (addr V, signal, line)
        self.init = {}        # address -> value (from an initial block)


class MemoryMixin:
    # ---------------------------------------------------------------- declaration
    def declare_mem(self, it, nm, ln):
        a, b = it.arrays[nm]
        hi, lo = self.ci(a), self.ci(b)
        if min(hi, lo) != 0: self.err(f"memory '{nm}': the address range must start at 0 (use [0:N] or [N:0])", ln)
        depth = max(hi, lo) + 1
        w = 32 if it.netkind == "integer" else self.rng(it.rng)[0]
        if depth > (1 << 24): self.err(f"memory '{nm}' has {depth} words; the most is {1 << 24}", ln)
        self.mems[nm] = Mem(nm, w, it.netkind == "integer" or bool(it.signed), depth, ln)

    # ---------------------------------------------------------------- reading
    def is_mem_ref(self, e):
        return e.kind == "index" and e.base.kind == "id" and e.base.name in self.mems

    def mem_read(self, e):
        m = self.mems[e.base.name]; b = self.b
        iv, wi, _ = self.ev_self(e.idx)
        for (a, s, ln) in m.reads:
            if a.k == iv.k and a.x == iv.x and a.w == iv.w: return b_sig(s, m.w)
        s = b.new_sig(m.w); m.reads.append((iv, s, e.line))
        return b_sig(s, m.w)

    # ---------------------------------------------------------------- writing (inside a clocked always block)
    def mem_write(self, st, env, seq):
        lv = st.lhs; m = self.mems[lv.base.name]
        if seq != "init" and seq is not True: self.err(f"memory '{m.name}' can only be written in a clocked always block", st.line)
        self.env = env
        w, s, _ = self.info(st.rhs); data = self.ev(st.rhs, max(m.w, w), s, m.w)
        if seq == "init":
            if not self.is_const(lv.idx) or data.k != "c": self.err("an initial block can only fill a memory with constants", st.line)
            i = self.ci(lv.idx)
            if not 0 <= i < m.depth: self.err(f"address {i} is outside memory '{m.name}'", st.line)
            m.init[i] = data.x; return
        if st.blocking: self.err(f"write memory '{m.name}' with '<=' (non-blocking)", st.line)
        iv, _, _ = self.ev_self(lv.idx)
        env.mw.append((m, iv, data, None))

    def and_en(self, c, en):
        return c if en is None else self.b.gate("AND", [c, en])

    # ---------------------------------------------------------------- end of a clocked block: one write port per memory
    def emit_mem_writes(self, env, clock, trig, line):
        b = self.b
        for m in {id(x[0]): x[0] for x in env.mw}.values():
            ents = [x for x in env.mw if x[0] is m]
            aw = max(x[1].w for x in ents)
            addr = data = en = None
            for (_, a, d, e) in ents:
                a = b.ext(a, aw, False); e1 = e if e is not None else b.const(1, 1)
                if addr is None: addr, data, en = a, d, e1
                else:
                    en2 = b.gate("OR", [en, e1]) if not (en.k == "c" and en.x) else en
                    addr, data = b.mux(e1, a, addr), b.mux(e1, d, data); en = en2
            if m.writes: self.err(f"memory '{m.name}' is written in two always blocks", line)
            m.writes.append((clock, trig, addr, data, None if (en.k == "c" and en.x) else en, line))

    # ---------------------------------------------------------------- building the parts
    def finish_mems(self):
        for m in self.mems.values():
            if not m.reads and not m.writes: continue
            self.line = m.line
            if m.init and m.writes: self.err(f"memory '{m.name}' has start values and is also written: a start value other than 0 is not possible for a RAM (Logisim parts start at 0)", m.line)
            if not m.writes: self.build_rom(m)
            elif len(m.writes) == 1 and not m.init and self.same_addr(m) and m.reads: self.build_ram(m)
            else: self.build_regs(m)

    def same_addr(self, m):
        a = m.writes[0][2]
        return all(r[0].k == a.k and r[0].x == a.x and r[0].w == a.w for r in m.reads) and a.k == "s"

    def fit_addr(self, addr, bits):
        """The address as exactly `bits` wide (extra high bits are dropped; reads that use them are guarded, see guarded)."""
        b = self.b
        return b.ext(addr, bits, False) if addr.w <= bits else b.slice(addr, 0, bits - 1)

    def tie(self, v, sig, w):
        """Make `sig` carry the value v."""
        c = R.create("BUFFER", "", {"width": w}, ins={"In1": self.b.sig(v)}, outs={"Out": sig}); self.b.comps.append(c)

    def guarded(self, addr, bits, m, raw):
        """A read with an address wider than the memory: outside the memory the value is 0."""
        b = self.b
        if addr.w <= bits or m.depth >= (1 << addr.w): return raw
        return b.mux(b.cmp(addr, b.const(m.depth, addr.w), False, "LT"), raw, b.const(0, m.w))

    def build_rom(self, m):
        b = self.b; bits = max(1, clog2(m.depth))
        if bits > 16: self.err(f"memory '{m.name}' has too many words for a ROM (the most is 65536)", m.line)
        for addr, sig, ln in m.reads:
            raw = b.new_sig(m.w)
            c = R.create("ROM", "", {"addr": bits, "width": m.w, "contents": {k: v for k, v in m.init.items() if v}}, ins={"A": b.sig(self.fit_addr(addr, bits))}, outs={"D": raw}); b.comps.append(c)
            self.tie(self.guarded(addr, bits, m, V_s(raw, m.w)), sig, m.w)

    def build_ram(self, m):
        b = self.b; clock, trig, addr, data, en, ln = m.writes[0]; bits = max(1, clog2(m.depth))
        if bits > 24: self.err(f"memory '{m.name}' is too big for a RAM (the most is {1 << 24} words)", ln)
        ins = {"A": b.sig(self.fit_addr(addr, bits)), "Din": b.sig(data), "WE": b.sig(en if en is not None else b.const(1, 1)), "Clk": b.sig(clock)}
        raw = b.new_sig(m.w)
        c = R.create("RAM", "", {"addr": bits, "width": m.w, "asyncread": True, "trigger": trig}, ins=ins, outs={"Dout": raw}); b.comps.append(c)
        v = self.guarded(addr, bits, m, V_s(raw, m.w))
        for _, s, _ in m.reads: self.tie(v, s, m.w)

    def build_regs(self, m):
        b = self.b
        if m.depth > MAX_REG_WORDS: self.err(f"memory '{m.name}' has {m.depth} words: this form (several read addresses, or reads at another address than the write) is limited to {MAX_REG_WORDS} words. Use one address for reading and writing to get a RAM.", m.line)
        qs = []
        if m.writes:
            clock, trig, addr, data, en, ln = m.writes[0]; aw = max(addr.w, max(1, clog2(m.depth)))
            ae = b.ext(addr, aw, False)
            for i in range(m.depth):
                hit = b.cmp(ae, b.const(i, aw), False, "EQ")
                wen = hit if en is None else b.gate("AND", [hit, en])
                q = b.new_sig(m.w)
                c = R.create("Register", "", {"width": m.w, "trigger": trig}, ins={"D": b.sig(data), "Clk": b.sig(clock), "En": b.sig(wen)}, outs={"Q": q}); b.comps.append(c)
                qs.append(V_s(q, m.w))
        else:
            qs = [b.const(m.init.get(i, 0), m.w) for i in range(m.depth)]
        for addr, sig, ln in m.reads:
            self.tie(self.read_tree(qs, addr, m), sig, m.w)

    def read_tree(self, words, addr, m):
        b = self.b; cur = list(words); shift = 0
        need = max(1, clog2(len(cur)))
        ae = addr if addr.w >= need else b.ext(addr, need, False)
        while len(cur) > 1:
            sb = min(5, clog2(len(cur))); size = 1 << sb
            sel = b.slice(ae, shift, shift + sb - 1); nxt = []
            for i in range(0, len(cur), size):
                grp = cur[i:i + size] + [b.const(0, m.w)] * (size - len(cur[i:i + size]))
                nxt.append(b.comp("MUX", {"select": sb, "width": m.w}, {**{f"In{j}": g for j, g in enumerate(grp)}, "Sel": sel}, ["Out"])["Out"])
            cur = nxt; shift += sb
        out = cur[0]
        if addr.w > shift and m.depth < (1 << addr.w):
            inside = b.cmp(addr, b.const(m.depth, addr.w), False, "LT"); out = b.mux(inside, out, b.const(0, m.w))
        return out


def V_s(sig, w):
    from .elab import V
    return V("s", sig, w)


def b_sig(sig, w): return V_s(sig, w)
