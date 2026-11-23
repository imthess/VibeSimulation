"""Run every test of the project and print one table.

    python dev/run_all.py                 # everything (window tests need a display; on a server use  xvfb-run -a python dev/run_all.py)
    python dev/run_all.py --fast          # only the tests that need no window (what the CI runs)
    python dev/run_all.py --window        # only the window tests
    python dev/run_all.py keytest guitest46   # just these

A test passes when it exits with 0, prints no line starting with FAIL and no Traceback. Exit code 1 if any test failed."""
import glob, json, os, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
HEADLESS = ["svtest", "instrtest", "sweeptest", "noisetest", "exampletest", "producttest", "analogtest4", "finetunetest", "keytest", "autodetecttest", "tokentest", "hdliotest", "simsettingstest", "tbinittest", "ic_test"]
# Scripts that are not tests of the app as it is now: they need Logisim 2.7.1 (dev/logisim.jar), take a file as argument, or are old one-off experiments.
SKIP = {"guitest": "first prototype test of the old single-window layout", "geotest": "needs logisim.jar", "gen_defaults": "needs logisim.jar", "semtest": "needs logisim.jar", "randtest": "needs logisim.jar"}
TIMEOUT = 420


def window_tests():
    names = sorted((os.path.basename(p)[:-3] for p in glob.glob(os.path.join(HERE, "guitest*.py"))), key=lambda n: (len(n), n))
    return [n for n in names if n not in SKIP]


def run(name, window):
    home = tempfile.mkdtemp(prefix="vs_test_home_")          # every test gets an empty home folder: settings, starred files and autosave never leak between tests or into yours
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"), PYTHONDONTWRITEBYTECODE="1", HOME=home, USERPROFILE=home)
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, os.path.join(HERE, name + ".py")], capture_output=True, text=True, timeout=TIMEOUT, env=env, cwd=ROOT)
        out = (p.stdout or "") + (p.stderr or ""); bad = [l for l in out.split("\n") if l.startswith("FAIL")]
        ok = p.returncode == 0 and not bad and "Traceback" not in out
        why = "" if ok else (bad[0][:110] if bad else (out.strip().split("\n")[-1][:110] if out.strip() else f"exit code {p.returncode}"))
    except subprocess.TimeoutExpired: ok, why = False, f"no answer after {TIMEOUT} s"
    return {"test": name, "window": window, "ok": ok, "why": why, "seconds": round(time.time() - t0, 1)}


def main(argv):
    fast = "--fast" in argv; only_window = "--window" in argv; picked = [a for a in argv if not a.startswith("--")]
    have_display = bool(os.environ.get("DISPLAY")) or sys.platform in ("win32", "darwin")
    jobs = []
    if picked: jobs = [(n, n not in HEADLESS) for n in picked]
    else:
        if not only_window: jobs += [(n, False) for n in HEADLESS]
        if not fast: jobs += [(n, True) for n in window_tests()]
    results = []
    for n, w in jobs:
        if w and not have_display: results.append({"test": n, "window": True, "ok": None, "why": "no display (use xvfb-run -a)", "seconds": 0}); continue
        r = run(n, w); results.append(r); print(f"{'ok  ' if r['ok'] else 'FAIL'} {n:<16} {r['seconds']:>6}s  {r['why']}", flush=True)
    bad = [r for r in results if r["ok"] is False]; skipped = [r for r in results if r["ok"] is None]
    print(f"\n{len(results) - len(bad) - len(skipped)} passed, {len(bad)} failed, {len(skipped)} skipped (of {len(results)})")
    for k, v in SKIP.items(): print(f"  not run: {k}.py — {v}")
    if "--json" in argv: json.dump(results, open(os.path.join(ROOT, "test-results.json"), "w"), indent=1)
    return 1 if bad else 0


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
