"""Draw random circuits, check each answer is valid, and write a training set.

    python dev/finetune/make_dataset.py out_dir --train 4000 --test 300 [--seed 1]

out_dir/images/*.png   the pictures
out_dir/train.jsonl    one chat example per line: image + the app's prompt -> the exact JSON answer (for Unsloth / TRL)
out_dir/test.jsonl     held-out examples for evaluate.py (image path + the true JSON)
"""
import argparse, json, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
from vibesimulation.workspaces.logisim.components import load_all; load_all()
import vibesimulation.workspaces.logisim.core.serializer as serializer
import vibesimulation.workspaces.multisim.core.netlist as anet
from vibesimulation.common.png_writer import LIGHT, MONO
from vibesimulation.workspaces.logisim.export.png import digital_png
from vibesimulation.workspaces.multisim.export.png import analog_png
from vibesimulation.workspaces.ai_import.core.prompt import build_prompt
import augment, circuits_analog, circuits_digital


def make_one(rng, kind):
    """Returns (truth_dict, PIL image) or None if this random circuit could not be drawn."""
    truth = circuits_digital.generate(rng) if kind == "digital" else circuits_analog.generate(rng)
    pal, scale = rng.choice((LIGHT, MONO)), rng.choice((1.0, 1.5, 2.0))
    try:
        if kind == "digital":
            c, errs = serializer.parse(truth)
            if errs or c is None or c.order() is None: return None
            img = digital_png(c, scale=scale, palette=pal)
        else:
            nl, errs = anet.parse(truth)
            if errs or nl is None: return None
            img = analog_png(nl, scale=scale, palette=pal)
    except Exception:
        return None
    return truth, img


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--train", type=int, default=1000); ap.add_argument("--test", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1); ap.add_argument("--analog", type=float, default=0.35, help="share of analog circuits")
    ap.add_argument("--augment", type=float, default=1.0, help="0 = clean pictures, 2 = rough")
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "images"), exist_ok=True)
    prompt, rng = build_prompt(), random.Random(a.seed)
    for split, n in (("train", a.train), ("test", a.test)):
        made, f = 0, open(os.path.join(a.out, f"{split}.jsonl"), "w", encoding="utf8")
        while made < n:
            kind = "analog" if rng.random() < a.analog else "digital"
            r = make_one(rng, kind)
            if not r: continue
            truth, img = r
            img = augment.augment(img, rng, a.augment if split == "train" or a.augment else 0)
            rel = f"images/{split}_{made:05d}.png"; img.save(os.path.join(a.out, rel))
            answer = json.dumps(truth, separators=(",", ":"))
            row = {"image": rel, "kind": kind, "truth": truth} if split == "test" else {
                "messages": [{"role": "user", "content": [{"type": "image", "image": rel}, {"type": "text", "text": prompt}]},
                             {"role": "assistant", "content": [{"type": "text", "text": answer}]}]}
            f.write(json.dumps(row) + "\n"); made += 1
            if made % 200 == 0: print(split, made, "/", n)
        f.close()
    print("done:", a.out)


if __name__ == "__main__":
    main()
