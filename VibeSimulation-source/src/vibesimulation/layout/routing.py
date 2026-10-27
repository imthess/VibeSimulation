"""Wire-routing strategies.

Both routers share one small interface: ``route(net, src, dst, ...)`` adds horizontal/vertical
segments to ``self.segs``. ``RailRouter`` makes tidy "bus lane" layouts for plain gate circuits;
``MazeRouter`` (A* on a 10 px grid) handles anything, including pins on the top/bottom of a part.
"""
import heapq
import time


# ---------- geometry helpers (all segments are horizontal or vertical) ----------
def norm(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))


def touch(a, b):
    """True if two segments overlap, or meet where at least one of them ends.
    (Wires that merely cross each other are NOT connected in Logisim.)"""
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    if x1 > x2 or y1 > y2:
        return False
    if (x1, y1) != (x2, y2):
        return True
    p = (x1, y1)
    return p in ((a[0], a[1]), (a[2], a[3]), (b[0], b[1]), (b[2], b[3]))


def on_seg(s, p):
    return s[0] <= p[0] <= s[2] and s[1] <= p[1] <= s[3]


def hits_rect(s, r):
    return s[0] < r[2] and s[2] > r[0] and s[1] < r[3] and s[3] > r[1]




class RailRouter:
    def __init__(self, ports, rects, step=10):
        self.ports, self.rects, self.segs, self.step = ports, rects, [], step   # segs: (x1,y1,x2,y2,net)
        self.deadline = None

    def _ok(self, path, net):
        for a, b in zip(path, path[1:]):
            if a == b:
                continue
            s = norm(a, b)
            if any(hits_rect(s, r) for r in self.rects):
                return False
            if any(n != net and on_seg(s, p) for p, n in self.ports.items()):
                return False
            if any(t[4] != net and touch(s, t) for t in self.segs):
                return False
        return self._still_joined(path, net)

    def _still_joined(self, path, net):
        """After Logisim merges straight pieces, all wires of this signal must still touch each other."""
        new = [norm(a, b) + (net,) for a, b in zip(path, path[1:]) if a != b]
        return net_joined([t for t in self.segs if t[4] == net] + new)

    def route(self, net, src, dst, gap_left, src_gap_right, lane0, asc=False):
        (sx, sy), (dx, dy) = src, dst
        st = self.step; first = dx - (20 if st > 10 else 10)
        chans = list(range(first, gap_left + 10, -st))      # vertical-jog x positions in the gap before the pin (st apart: wires get air)
        if asc:
            chans.reverse()
        self.tick = 0
        def paths():
            if sy == dy:
                yield [src, dst]
            for xc in chans:
                yield [src, (xc, sy), (xc, dy), dst]
            for ly in range(lane0, lane0 + 300 + 100 * (st > 10), st):
                for xs in range(sx + (20 if st > 10 else 10), src_gap_right - 10, st):
                    for xe in chans:
                        if xs != xe:
                            yield [src, (xs, sy), (xs, ly), (xe, ly), (xe, dy), dst]
        for p in paths():
            self.tick += 1
            if self.tick % 300 == 0 and self.deadline and time.time() > self.deadline:
                raise ValueError("routing took too long")
            if self._ok(p, net):
                for a, b in zip(p, p[1:]):
                    if a != b:
                        self.segs.append(norm(a, b) + (net,))
                return
        raise ValueError(f"Could not route signal '{net}'")




class MazeRouter:
    """Fallback router for big circuits: A* on a 10px grid. Wires may cross other nets only straight through
    their middle (never at an end or a corner), never touch other nets' pins, and may join their own net's wires."""
    def __init__(self, ports, rects, bounds, deadline, reserved=None):
        self.ports, self.segs, self.bounds, self.deadline = ports, [], bounds, deadline
        self.reserved = reserved or {}      # cells in front of pins, kept free for the pin's own signal
        self.blocked = set(); self.occ = {}; self.own = {}; self.bynet = {}
        self.hw = 1          # weight of the distance estimate: above 1 the search is greedier (faster, routes slightly longer): used for big circuits
        self.dep = {}       # (net, point) -> directions wires of that net already leave that point in
        for (x0, y0, x1, y1) in rects:
            for x in range(x0, x1 + 1, 10):
                for y in range(y0, y1 + 1, 10): self.blocked.add((x, y))

    def _add(self, seg, net):
        x1, y1, x2, y2 = seg; horiz = y1 == y2
        pts = [(x, y1) for x in range(x1, x2 + 1, 10)] if horiz else [(x1, y) for y in range(y1, y2 + 1, 10)]
        for i, p in enumerate(pts):
            k = "E" if i in (0, len(pts) - 1) else ("H" if horiz else "V")
            self.occ.setdefault(p, []).append((net, k)); self.own.setdefault(net, set()).add(p)
        self.segs.append(seg + (net,)); self.bynet.setdefault(net, []).append(seg + (net,))

    def route(self, net, src, dst, *_, **__):
        banned = set()
        for _try in range(8):
            before = len(self.segs)
            start = self._search(net, src, dst, banned)
            new = [s for s in self.segs[before:]]
            if net_joined(self.bynet.get(net, [])):
                return
            del self.segs[before:]          # undo: this junction would be lost when Logisim merges straight wires
            if new: del self.bynet[net][-len(new):]
            for t in new: self._unmark(t)
            banned.add(start)
        raise ValueError(f"Could not route signal '{net}'")

    def _unmark(self, seg):
        x1, y1, x2, y2 = seg[:4]; horiz = y1 == y2
        pts = [(x, y1) for x in range(x1, x2 + 1, 10)] if horiz else [(x1, y) for y in range(y1, y2 + 1, 10)]
        for p in pts:
            lst = self.occ.get(p, [])
            for i, (m, k) in enumerate(lst):
                if m == seg[4]: del lst[i]; break
            if not lst: self.occ.pop(p, None)
        # own-cell set is rebuilt from what is left
        self.own[seg[4]] = {p for t in self.bynet.get(seg[4], []) for p in
                            ([(x, t[1]) for x in range(t[0], t[2] + 1, 10)] if t[1] == t[3] else [(t[0], y) for y in range(t[1], t[3] + 1, 10)])}

    def _search(self, net, src, dst, banned):
        xmin, ymin, xmax, ymax = self.bounds; exempt = {src, dst}
        def plain(q):
            if self.reserved.get(q, net) != net: return False
            if q in self.blocked and q not in exempt and self.reserved.get(q) != net: return False
            n = self.ports.get(q)
            if n is not None and n != net and q not in exempt: return False
            return q == dst or not self.occ.get(q)      # never run over (and so merge with) an existing wire
        def crossable(q, horiz):
            if q in self.blocked or q in self.ports or self.reserved.get(q, net) != net: return False
            o = self.occ.get(q)
            return bool(o) and all(m != net and k == ("V" if horiz else "H") for m, k in o)
        starts = ({src} | self.own.get(net, set())) - banned
        heap, best, par, cnt = [], {}, {}, 0
        for s in starts:
            st = (s, None); best[st] = 0; par[st] = None
            heapq.heappush(heap, (self.hw * (abs(s[0] - dst[0]) // 10 + abs(s[1] - dst[1]) // 10), 0, cnt, st)); cnt += 1
        goal = None
        while heap:
            f, g, _, st = heapq.heappop(heap)
            if best.get(st, 1e9) < g: continue
            p, d = st
            if p == dst: goal = st; break
            first = d is None
            cnt += 1
            if cnt % 2000 == 0 and time.time() > self.deadline: raise ValueError("routing took too long")
            for dd, (dx, dy) in (("H", (10, 0)), ("H", (-10, 0)), ("V", (0, 10)), ("V", (0, -10))):
                if first and (-dx, -dy) in self.dep.get((net, p), ()):
                    continue         # Logisim would merge two opposite wires into one and lose the junction
                q = (p[0] + dx, p[1] + dy); cost = 1 + (6 if d is not None and d != dd else 0); steps = 1
                if not (xmin <= q[0] <= xmax and ymin <= q[1] <= ymax): continue
                if not plain(q):
                    while steps < 16 and crossable(q, dd == "H"):
                        q = (q[0] + dx, q[1] + dy); steps += 1; cost += 7
                        if not (xmin <= q[0] <= xmax and ymin <= q[1] <= ymax): break
                    else:
                        pass
                    if steps == 1 or not plain(q) or not (xmin <= q[0] <= xmax and ymin <= q[1] <= ymax): continue
                    cost += steps - 1
                if any(self.occ.get((q[0] + ax, q[1] + ay)) and not all(m == net for m, _ in self.occ[(q[0] + ax, q[1] + ay)])
                       for ax, ay in ((10, 0), (-10, 0), (0, 10), (0, -10))): cost += 3      # keep a free grid line between different signals when possible
                ns = (q, dd); ng = g + cost
                if ng < best.get(ns, 1e9):
                    best[ns] = ng; par[ns] = st
                    heapq.heappush(heap, (ng + self.hw * (abs(q[0] - dst[0]) // 10 + abs(q[1] - dst[1]) // 10), ng, cnt, ns)); cnt += 1
        if goal is None:
            raise ValueError(f"Could not route signal '{net}'")
        pts, st = [], goal
        while st is not None: pts.append(st[0]); st = par[st]
        pts.reverse()
        if len(pts) > 1:
            v = ((pts[1][0] > pts[0][0]) - (pts[1][0] < pts[0][0]), (pts[1][1] > pts[0][1]) - (pts[1][1] < pts[0][1]))
            self.dep.setdefault((net, pts[0]), set()).add((v[0] * 10, v[1] * 10))
        corners = [pts[0]]
        for i in range(1, len(pts) - 1):
            a, b, c = pts[i - 1], pts[i], pts[i + 1]
            if (a[0] == b[0] == c[0]) or (a[1] == b[1] == c[1]): continue
            corners.append(b)
        corners.append(pts[-1])
        for a, c in zip(corners, corners[1:]):
            if a != c: self._add(norm(a, c), net)
        return pts[0]


def merge_collinear(segs):
    """Join same-net segments that overlap or meet end to end, the way Logisim does when it loads a file."""
    out = []
    for net in dict.fromkeys(s[4] for s in segs):
        for horiz in (True, False):
            mine = sorted((s for s in segs if s[4] == net and (s[1] == s[3]) == horiz and (s[0], s[1]) != (s[2], s[3])),
                          key=lambda s: (s[1], s[0]) if horiz else (s[0], s[1]))
            cur = None
            for s in mine:
                if cur and ((horiz and s[1] == cur[1] and s[0] <= cur[2]) or (not horiz and s[0] == cur[0] and s[1] <= cur[3])):
                    cur = (cur[0], cur[1], max(cur[2], s[2]), max(cur[3], s[3]), net)
                else:
                    if cur: out.append(cur)
                    cur = s
            if cur: out.append(cur)
    return out


def net_joined(segs):
    """True if these same-signal wires, once merged the way Logisim merges them, form one connected piece."""
    segs = merge_collinear(segs)
    comp = list(range(len(segs)))
    def f(i):
        while comp[i] != i: comp[i] = comp[comp[i]]; i = comp[i]
        return i
    for i, j in _joined_pairs(segs): comp[f(i)] = f(j)
    return len({f(i) for i in range(len(segs))}) <= 1


def _joined_pairs(segs):
    """Pairs (i, j) of segments that touch. On the 10-grid (always the case here) segments are bucketed by the grid points they cover,
    so this is linear instead of comparing every pair; otherwise every pair is compared."""
    if not all(v % 10 == 0 for s in segs for v in s[:4]):
        for i in range(len(segs)):
            for j in range(i):
                if touch(segs[i][:4], segs[j][:4]): yield i, j
        return
    cells = {}
    for i, s in enumerate(segs):
        x1, y1, x2, y2 = s[:4]
        pts = [(x, y1) for x in range(x1, x2 + 1, 10)] if y1 == y2 else [(x1, y) for y in range(y1, y2 + 1, 10)]
        for k, p in enumerate(pts): cells.setdefault(p, []).append((i, k == 0 or k == len(pts) - 1))
    for lst in cells.values():
        if len(lst) < 2: continue
        ends = [i for i, e in lst if e]
        if not ends: continue
        for i, _ in lst:                     # a point shared where at least one segment ends joins all of them
            for j in ends:
                if i != j: yield i, j


def check_connectivity(ports, segs):
    """Independent connectivity check: the wires must join exactly the ports of each signal."""
    par = list(range(len(segs) + len(ports)))
    def f(i):
        while par[i] != i:
            par[i] = par[par[i]]; i = par[i]
        return i
    def u(i, j): par[f(i)] = f(j)
    for i, j in _joined_pairs(segs): u(i, j)
    plist = list(ports.items())
    byp = {}
    for i, s in enumerate(segs):
        x1, y1, x2, y2 = s[:4]
        if all(v % 10 == 0 for v in s[:4]):
            for p in ([(x, y1) for x in range(x1, x2 + 1, 10)] if y1 == y2 else [(x1, y) for y in range(y1, y2 + 1, 10)]): byp.setdefault(p, []).append(i)
    grid = all(v % 10 == 0 for s in segs for v in s[:4])
    for k, (p, _) in enumerate(plist):
        if grid and p[0] % 10 == 0 and p[1] % 10 == 0:
            for i in byp.get(p, ()): u(len(segs) + k, i)
        else:
            for i, s in enumerate(segs):
                if on_seg(s, p): u(len(segs) + k, i)
    comp_nets, net_comps = {}, {}
    for k, (p, n) in enumerate(plist):
        r = f(len(segs) + k)
        comp_nets.setdefault(r, set()).add(n)
        net_comps.setdefault(n, set()).add(r)
    if any(len(v) > 1 for v in comp_nets.values()) or any(len(v) > 1 for v in net_comps.values()):
        bad = sorted({n for v in comp_nets.values() if len(v) > 1 for n in v} | {n for n, v in net_comps.items() if len(v) > 1})
        raise ValueError("Internal error: generated wires do not match the netlist (" + ", ".join(map(str, bad)) + ")")


