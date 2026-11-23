"""Update check: is there a newer version than the one running?

Nothing is contacted unless the person turns the check on and gives an address (Settings: update_url). The address answers with JSON
in one of two shapes: ``{"version": "1.2.0", "url": "...", "notes": "..."}`` or a GitHub release (``tag_name``, ``html_url``, ``body``).
"""
import json
import re
import threading
import urllib.request


def parse_version(text):
    """'v1.2.10-beta' -> (1, 2, 10). Unreadable text gives ()."""
    m = re.match(r"\s*v?(\d+(?:\.\d+)*)", str(text or ""))
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def is_newer(latest, current):
    a, b = parse_version(latest), parse_version(current)
    if not a or not b: return False
    n = max(len(a), len(b)); a += (0,) * (n - len(a)); b += (0,) * (n - len(b))
    return a > b


def normalize(data):
    """The answer of the server as {'version', 'url', 'notes'} (ValueError if it is neither shape)."""
    if not isinstance(data, dict): raise ValueError("The update address did not answer with a JSON object.")
    v = data.get("version") or data.get("tag_name")
    if not v or not parse_version(v): raise ValueError("The answer has no readable version number.")
    return {"version": str(v).lstrip("vV"), "url": str(data.get("url") or data.get("html_url") or ""), "notes": str(data.get("notes") or data.get("body") or "")[:2000]}


def fetch_latest(url, timeout=6.0):
    if not str(url).lower().startswith(("https://", "http://")): raise ValueError("The update address must start with https://")
    req = urllib.request.Request(url, headers={"User-Agent": "VibeSimulation-update-check", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(200_000)
    try: return normalize(json.loads(raw.decode("utf-8")))
    except json.JSONDecodeError: raise ValueError("The update address did not answer with JSON.")


def check(url, current):
    """-> (newer?, info). Raises on network problems or a bad answer."""
    info = fetch_latest(url); return is_newer(info["version"], current), info


def check_async(url, current, done, schedule):
    """Run check() in a thread; call done(newer, info, error) on the UI thread through `schedule(fn)` (for Tk: lambda f: root.after(0, f))."""
    def work():
        try: newer, info = check(url, current); res = (newer, info, None)
        except Exception as e: res = (False, None, e)
        schedule(lambda: done(*res))
    threading.Thread(target=work, daemon=True).start()
