"""Measure how often a model reads the circuit pictures correctly.

    python dev/finetune/evaluate.py data_dir --model qwen3-vl:4b-instruct [--server http://localhost:11434] [--limit 100]
    python dev/finetune/evaluate.py data_dir --model any-name --provider "Custom (OpenAI-compatible)" --server http://localhost:8080

Uses the same request the app sends (ai.providers), so the number is what you would see in the app.
Writes data_dir/report_<model>.json with every answer, and prints a summary."""
import argparse, json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
from score import score


def run(rows, ask, data_dir, log=print):
    """ask(png_bytes) -> answer text. Returns the list of per-picture results."""
    out = []
    for i, row in enumerate(rows, 1):
        png = open(os.path.join(data_dir, row["image"]), "rb").read()
        t0 = time.time()
        try: text = ask(png)
        except Exception as e: text = f"ERROR {e}"
        kind_ok, checks, correct = score(row["truth"], text)
        out.append({"image": row["image"], "kind": row["kind"], "kind_ok": kind_ok, "checks": checks, "correct": correct, "seconds": round(time.time() - t0, 1), "answer": text})
        log(f"[{i}/{len(rows)}] {row['kind']:7} {'OK ' if correct else 'BAD'} {out[-1]['seconds']}s")
    return out


def summary(results):
    lines = []
    for kind in ("digital", "analog"):
        rs = [r for r in results if r["kind"] == kind]
        if not rs: continue
        n = len(rs); lines.append(f"{kind}: {sum(r['correct'] for r in rs)}/{n} fully correct ({100 * sum(r['correct'] for r in rs) / n:.0f}%)")
        for k in sorted({k for r in rs for k in r["checks"]}):
            lines.append(f"    {k:11} {100 * sum(bool(r['checks'].get(k)) for r in rs) / n:5.0f}%")
        lines.append(f"    right kind  {100 * sum(r['kind_ok'] for r in rs) / n:5.0f}%")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("data"); ap.add_argument("--model", required=True)
    ap.add_argument("--server", default="http://localhost:11434"); ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--provider", default="Ollama (local, free)", help='"Custom (OpenAI-compatible)" for llama-server / vLLM; any name from the app\'s provider list')
    ap.add_argument("--key", default="x", help="API key (llama-server accepts anything)")
    a = ap.parse_args()
    from vibesimulation.workspaces.ai_import.core import ask_model
    rows = [json.loads(l) for l in open(os.path.join(a.data, "test.jsonl"), encoding="utf8")][:a.limit]
    res = run(rows, lambda png: ask_model(a.provider, a.model, a.key, png, "image/png", a.server), a.data)
    path = os.path.join(a.data, "report_" + a.model.replace(":", "_").replace("/", "_") + ".json")
    json.dump(res, open(path, "w"), indent=1)
    print("\n" + summary(res) + f"\n\nfull report: {path}")


if __name__ == "__main__":
    main()
