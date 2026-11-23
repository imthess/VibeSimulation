# Making the AI import more accurate

What this folder does and does not do:

- It **measures** how accurate a model is (`evaluate.py`). Do this first. Without a number you cannot tell whether anything helped.
- It **makes training data**: random circuits are drawn with the app's own renderer, so the correct answer is known exactly (`make_dataset.py`). The pictures are then roughened to look like photos and scans (`augment.py`).
- It has a **training script** for Qwen3-VL-4B (`train_unsloth.py`). It needs an NVIDIA GPU and has **not been run** by the author.

Honest limits:
1. The generated pictures are in the style of VibeSimulation / Logisim and of textbook analog schematics. A model tuned only on them will get much better on screenshots of those styles. It may improve less on hand-drawn sketches or photos of other drawing styles. For those, add real pictures with correct JSON answers (see "Real pictures" below).
2. Fine-tuning is not guaranteed to fix your results. Step 1 tells you where the model fails; if it only fails on large circuits, the cure may be a bigger model (`qwen3-vl:8b`) or a cropped picture, not training.
3. The random circuits are small (up to about 10 gates, up to 4 nets plus ground). Bigger circuits are not in the training set yet.

## 1. Measure the models you have now
```bash
python dev/finetune/make_dataset.py data --train 2000 --test 100 --seed 1
python dev/finetune/evaluate.py data --model qwen3-vl:4b-instruct
python dev/finetune/evaluate.py data --model qwen3-vl:4b
```
It sends each test picture exactly as the app does and prints, per kind (digital / analog), how many answers are fully correct and which check fails (JSON valid, names, gate types, values, wiring). A digital answer is correct when it behaves the same on every input row, so a different but equivalent gate layout still counts. An analog answer is correct when parts, values and wiring match (net names may differ).
`--limit N` tests fewer pictures. The full per-picture answers are saved in `data/report_<model>.json`; read the wrong ones to see what the model gets confused about.

## 2. Make the training set
`make_dataset.py data --train 4000` (about 1 minute per 1000 pictures). `--augment 0` gives clean pictures, `--augment 2` rougher ones. `--analog 0.35` is the share of analog circuits. Keep `--seed` different from the test seed so the test circuits are not in the training set (the defaults already use a separate test split drawn after the training one).

## 3. Train (needs an NVIDIA GPU)
```bash
pip install unsloth trl datasets pillow
python dev/finetune/train_unsloth.py data --out qwen3vl-circuits --epochs 1
```
This writes a small LoRA adapter (`qwen3vl-circuits-lora`) and a merged model (`qwen3vl-circuits-merged`). About 16 GB of GPU memory is needed (a free Colab T4 can manage roughly 1000 examples; the training prompt is long). If an Unsloth call fails, the API has probably moved: compare with Unsloth's current Qwen3-VL vision notebook. The data format needs no change.

## 4. Test the tuned model before using it
Serve the tuned model (Ollama, or `llama-server` as in step 5), then run `evaluate.py` against it. For llama-server: `python dev/finetune/evaluate.py data --model tuned --provider "Custom (OpenAI-compatible)" --server http://localhost:8080`. The comparison with step 1 is the result. Keep the test split untouched.

## 5. Use it in the app
This is the least certain step because it depends on your Ollama version.
- **Ollama:** convert the merged model to GGUF with llama.cpp (`convert_hf_to_gguf.py qwen3vl-circuits-merged --outtype q8_0`; for a vision model also create the `mmproj` file with the same script's `--mmproj` option), then `ollama create qwen3vl-circuits -f Modelfile` and use that name in the app. Ollama's support for importing Qwen3-VL with its vision part has changed between versions; check the Ollama import documentation for yours.
- **If the Ollama import does not work:** run `llama-server -m model.gguf --mmproj mmproj.gguf --port 8080` and choose **Custom (OpenAI-compatible)** in the app with server URL `http://localhost:8080`, any model name and any text as the key (the app insists on one).

## Real pictures (recommended for photos and hand drawings)
Put each picture next to its true JSON answer and add a line to `train.jsonl` of the same shape as the generated ones (`messages`: user = image + `build_prompt()`, assistant = the JSON). Even 50 to 100 real examples, repeated a few times in the file, help more than thousands of extra generated ones. Keep 10 to 20 real examples out of training and score them with `evaluate.py` (add them to `test.jsonl` with `kind` and `truth`).

## Files
| File | Job |
|---|---|
| `circuits_digital.py` | random logic circuits in the app's JSON |
| `circuits_analog.py` | random resistor / capacitor / inductor / diode circuits |
| `augment.py` | tilt, shadows, blur, noise, JPEG, paper colour |
| `make_dataset.py` | draws pictures (via `export/png.py`) and writes `train.jsonl` / `test.jsonl` |
| `score.py` | decides whether an answer is correct |
| `evaluate.py` | asks a model about every test picture and reports |
| `train_unsloth.py` | QLoRA training |
