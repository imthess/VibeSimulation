"""The activity log: what the program does in the background (network calls, scans, conversions, errors), kept in memory and shown live on
the Activity page (the </> icon). Every tab can write to it; it never holds API keys (``secret`` registers keys that are masked).

Thread safe: background threads call ``log`` / ``begin`` / ``end``; the window reads with ``since`` on its own thread."""
import collections
import re
import threading
import time

LEVELS = ("debug", "info", "ok", "warn", "error")
MAX_ENTRIES = 3000
_SECRETS = set()
_KEY_SHAPES = re.compile(r"(AIza[0-9A-Za-z_\-]{20,}|AQ\.[0-9A-Za-z_\-.]{20,}|sk-[0-9A-Za-z_\-]{16,}|gsk_[0-9A-Za-z]{16,}|Bearer\s+[0-9A-Za-z_\-.]{12,})")


class Entry:
    __slots__ = ("seq", "t", "level", "source", "text", "data")

    def __init__(self, seq, level, source, text, data):
        self.seq, self.t, self.level, self.source, self.text, self.data = seq, time.time(), level, source, text, data

    def clock(self): return time.strftime("%H:%M:%S", time.localtime(self.t)) + f".{int(self.t * 1000) % 1000:03d}"


class Log:
    def __init__(self):
        self._lock = threading.Lock(); self._items = collections.deque(maxlen=MAX_ENTRIES); self._seq = 0
        self.jobs = {}                      # id -> dict(name, t0, info): work that is running now
        self._job_seq = 0
        self.last_request = None            # sanitised copy of the newest request sent to a service
        self.last_response = None           # sanitised summary of the newest answer
        self.started = time.time()

    # ---- writing
    def log(self, source, text, level="info", **data):
        text = redact(str(text))
        with self._lock:
            self._seq += 1; e = Entry(self._seq, level if level in LEVELS else "info", source, text, {k: v for k, v in data.items()})
            self._items.append(e)
        return e

    def begin(self, name, **info):
        """Mark a piece of work as running (shown live, with the seconds it has taken). Returns its id for ``end``."""
        with self._lock: self._job_seq += 1; jid = self._job_seq; self.jobs[jid] = dict(name=name, t0=time.time(), info=info)
        return jid

    def end(self, jid, ok=True, text=""):
        with self._lock: j = self.jobs.pop(jid, None)
        if j: self.log(j["info"].get("source", "job"), f"{j['name']}: {text or ('finished' if ok else 'failed')} ({time.time() - j['t0']:.1f} s)", "ok" if ok else "error")

    def clear(self):
        with self._lock: self._items.clear()

    # ---- reading
    def since(self, seq=0):
        with self._lock: return [e for e in self._items if e.seq > seq]

    def all(self):
        with self._lock: return list(self._items)

    def running(self):
        """[(name, seconds so far)] for work in progress."""
        now = time.time()
        with self._lock: return [(j["name"], now - j["t0"]) for j in self.jobs.values()]

    def counts(self):
        c = dict.fromkeys(LEVELS, 0)
        for e in self.all(): c[e.level] += 1
        return c


LOG = Log()


def log(source, text, level="info", **data): return LOG.log(source, text, level, **data)


def secret(key):
    """Never show this text (an API key) in the log or in exports."""
    if key and len(key) >= 8: _SECRETS.add(key)


def redact(text):
    for s in _SECRETS: text = text.replace(s, "***")
    return _KEY_SHAPES.sub("***", text)


def shrink(obj, limit=160):
    """A copy of a request/answer body that is safe and short to show: long strings (pictures, prompts) become '<first characters> … [N characters]'."""
    if isinstance(obj, dict): return {k: ("***" if str(k).lower() in ("authorization", "x-api-key", "x-goog-api-key") else shrink(v, limit)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)): return [shrink(v, limit) for v in obj[:12]] + (["… %d more" % (len(obj) - 12)] if len(obj) > 12 else [])
    if isinstance(obj, str) and len(obj) > limit: return redact(obj[:limit - 40]) + f" … [{len(obj):,} characters]"
    return redact(obj) if isinstance(obj, str) else obj


def heartbeat(jid, label, every=15):
    """Background thread that writes 'still waiting' lines while job ``jid`` runs; returns a function that stops it."""
    stop = threading.Event()
    def run():
        t0 = time.time()
        while not stop.wait(every):
            s = int(time.time() - t0)
            LOG.log("net", f"still waiting for {label} … {s} s", "warn" if s >= 60 else "info")
    threading.Thread(target=run, daemon=True).start()
    return stop.set
