"""Editing a wire by hand: drag one straight piece sideways, and check that a hand-made route is still a correct one.

A route is a list of straight pieces (x1, y1, x2, y2) with x1 <= x2 and y1 <= y2, all on the 10-unit grid.
"""
from .routing import hits_rect, net_joined, norm, on_seg


def _horiz(s): return s[1] == s[3] and s[0] != s[2]


def _touches(s, p):
    """True if point p lies on piece s (end or inside)."""
    return on_seg(s, p)


def move_segment(segs, i, dx, dy, ports):
    """Move piece i of one signal's wires sideways (a horizontal piece up/down by dy, a vertical one left/right by dx).
    Pieces of the same signal that end on it are stretched along (so they stay joined); a pin that sits on the piece gets
    a short connecting piece. Returns the new list of pieces, or None when nothing would change."""
    S = segs[i]
    horiz = _horiz(S)
    sh = (0, dy) if horiz else (dx, 0)
    if sh == (0, 0): return None
    new = [list(t) for t in segs]
    extra = []
    for j, t in enumerate(segs):
        if j == i: continue
        for k in (0, 1):
            q = (t[2 * k], t[2 * k + 1])
            if not on_seg(S, q) or q in ports: continue
            if _horiz(t) != horiz and (t[0] != t[2] or t[1] != t[3]) and not (t[1] == t[3] and t[0] == t[2]):
                new[j][2 * k], new[j][2 * k + 1] = q[0] + sh[0], q[1] + sh[1]        # perpendicular neighbour: stretch it
            else:
                extra.append((q, (q[0] + sh[0], q[1] + sh[1])))                       # collinear neighbour: join with a short piece
    for p in ports:
        if on_seg(S, p): extra.append((p, (p[0] + sh[0], p[1] + sh[1])))             # a pin on the piece stays where it is
    new[i] = [S[0] + sh[0], S[1] + sh[1], S[2] + sh[0], S[3] + sh[1]]
    res = [norm((t[0], t[1]), (t[2], t[3])) for t in new] + [norm(a, b) for a, b in extra]
    res = [t for t in res if (t[0], t[1]) != (t[2], t[3])]
    return list(dict.fromkeys(res))


def valid_route(net, segs, ports, rects=()):
    """Is this hand-made route of signal `net` acceptable? Straight pieces on the grid, one connected piece of wire that
    reaches every pin of the signal, touches no other signal's pin, and does not run through a part."""
    if not segs: return False
    for s in segs:
        if len(s) != 4 or any(not isinstance(v, int) or v % 10 for v in s): return False
        if s[0] > s[2] or s[1] > s[3] or (s[0] != s[2] and s[1] != s[3]): return False
    if not net_joined([s + (net,) for s in segs]): return False
    for p, n in ports.items():
        hit = any(on_seg(s, p) for s in segs)
        if n == net and not hit: return False
        if n != net and hit: return False
    return not any(hits_rect(s, r) for s in segs for r in rects)


def stretch_end(segs, old, new, final_vertical):
    """A pin moved from `old` to `new`: every piece that ended on the old pin position now ends on the new one, with one
    right-angle bend (like Logisim). The last stretch runs into the pin vertically if final_vertical, else horizontally."""
    out = []
    for t in segs:
        ends = [(t[0], t[1]), (t[2], t[3])]
        if old not in ends or old == new: out.append(tuple(t)); continue
        P = ends[1] if ends[0] == old else ends[0]
        if P[0] == new[0] or P[1] == new[1]: out.append(norm(P, new)); continue
        bend = (new[0], P[1]) if final_vertical else (P[0], new[1])
        out += [norm(P, bend), norm(bend, new)]
    return list(dict.fromkeys(t for t in out if (t[0], t[1]) != (t[2], t[3])))


def move_vertex(segs, V, V2, ports=()):
    """Drag a corner or an open end V of a wire to V2: every piece that ends on V follows, with one right-angle bend if it
    is no longer straight (it keeps leaving its other end in the direction it had)."""
    if V == V2: return list(segs)
    out = []
    here = [t for t in segs if V in ((t[0], t[1]), (t[2], t[3]))]
    straight = len({_horiz(t) for t in here}) == 1            # a bend point or an open end: pulling it must really bend the wire
    for t in segs:
        ends = [(t[0], t[1]), (t[2], t[3])]
        if V not in ends: out.append(tuple(t)); continue
        P = ends[1] if ends[0] == V else ends[0]
        if P == V2 or P == V: continue
        if P[0] == V2[0] or P[1] == V2[1]: out.append(norm(P, V2)); continue
        keep = _horiz(t) if (not straight or P in ports) else not _horiz(t)
        bend = (V2[0], P[1]) if keep else (P[0], V2[1])
        out += [norm(P, bend), norm(bend, V2)]
    return list(dict.fromkeys(t for t in out if (t[0], t[1]) != (t[2], t[3])))


def split_at(segs, Q):
    """Put a new corner on the wire at Q (a point inside one of the pieces)."""
    out, done = [], False
    for t in segs:
        if not done and on_seg(t, Q) and Q not in ((t[0], t[1]), (t[2], t[3])):
            out += [norm((t[0], t[1]), Q), norm(Q, (t[2], t[3]))]; done = True
        else: out.append(tuple(t))
    return out


def tidy(segs):
    """Join pieces that lie end to end on one line (keeps junctions)."""
    from .routing import merge_collinear
    return [t[:4] for t in merge_collinear([tuple(s) + ("n",) for s in segs])]


def snap10(v):
    return int(round(v / 10.0)) * 10


def reach(segs, points):
    """The set of piece indices that are joined (end to end or in a T) to a piece touching one of `points`."""
    seen, todo = set(), [i for i, s in enumerate(segs) if any(on_seg(s, p) for p in points)]
    while todo:
        i = todo.pop()
        if i in seen: continue
        seen.add(i); a = segs[i]
        ends = ((a[0], a[1]), (a[2], a[3]))
        for j, b in enumerate(segs):
            if j in seen: continue
            if any(on_seg(b, q) for q in ends) or any(on_seg(a, q) for q in ((b[0], b[1]), (b[2], b[3]))): todo.append(j)
    return seen


def cut_pieces(segs, removed, drivers, sinks):
    """Take the pieces with indices `removed` out of one signal's wires. Returns (kept pieces, sink points that lost their connection to a driver).
    Pieces that no longer lead from a driver are dropped too (a floating wire carries nothing)."""
    left = [s for i, s in enumerate(segs) if i not in removed]
    keep = reach(left, drivers)
    kept = [left[i] for i in sorted(keep)]
    return kept, [p for p in sinks if not any(on_seg(s, p) for s in kept)]
