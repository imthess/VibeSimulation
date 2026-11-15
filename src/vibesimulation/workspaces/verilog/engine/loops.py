"""for / while / repeat inside always blocks, functions and tasks: the loop is unrolled while the circuit is built.

The loop condition has to be known at build time (numbers, parameters, the loop counter), because a circuit cannot
repeat itself. A loop counter is an ordinary variable whose value is a constant at every step, so a[i] picks a fixed bit.
"""
MAX_ITER = 4096


class LoopMixin:
    def exec_loop(self, st, env, seq):
        k = st.kind; self.env = env
        if k == "repeat":
            n = self.ci(st.count)
            if n > MAX_ITER: self.err(f"the loop would run {n} times (the most is {MAX_ITER})", st.line)
            for _ in range(max(0, n)): self.exec(st.body, env, seq)
            return
        if k == "for": self.exec(st.init, env, seq)
        count = 0
        while True:
            self.env = env; self.line = st.line
            c = self.b.truth(self.ev_self(st.cond)[0])
            if c.k != "c": self.err("the loop condition must be known when the circuit is built (use numbers, parameters and the loop counter only)", st.line)
            if not c.x: break
            count += 1
            if count > MAX_ITER: self.err(f"the loop runs more than {MAX_ITER} times (does it ever end?)", st.line)
            self.exec(st.body, env, seq)
            if k == "for": self.exec(st.step, env, seq)

    def loop_assigned(self, st, out, nb):
        """Names a loop's body assigns (the counter's own init/step are not circuit variables)."""
        if st.kind == "for":
            tmp = set(); self.assigned(st.init, tmp, None); self.assigned(st.step, tmp, None)
            body = set(); self.assigned(st.body, body, nb)
            out |= body
            self.loop_vars |= (tmp - body)
        else: self.assigned(st.body, out, nb)
