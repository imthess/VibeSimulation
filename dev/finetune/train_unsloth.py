"""Fine-tune Qwen3-VL-4B on the circuit pictures with QLoRA (Unsloth + TRL). Run on a machine with an NVIDIA GPU (about 16 GB; a free Colab T4 can do ~1000 examples).

    pip install unsloth trl datasets pillow
    python dev/finetune/train_unsloth.py data_dir --out qwen3vl-circuits [--epochs 1] [--base unsloth/Qwen3-VL-4B-Instruct]

NOT RUN by the author (no GPU in the environment it was written in). Unsloth changes its API now and then; if a call fails, compare with the
current "Qwen3-VL vision fine-tuning" notebook on unsloth.ai/docs - the data format here (image + prompt -> JSON) is the standard one.
The training prompt is the app's own prompt (ai.prompt.build_prompt), so the tuned model sees exactly what the app will send."""
import argparse, json, os

ap = argparse.ArgumentParser(); ap.add_argument("data"); ap.add_argument("--out", default="qwen3vl-circuits")
ap.add_argument("--base", default="unsloth/Qwen3-VL-4B-Instruct"); ap.add_argument("--epochs", type=float, default=1.0)
ap.add_argument("--lr", type=float, default=2e-4); ap.add_argument("--rank", type=int, default=16)
a = ap.parse_args()

from PIL import Image
from trl import SFTConfig, SFTTrainer
from unsloth import FastVisionModel, is_bf16_supported
from unsloth.trainer import UnslothVisionDataCollator


def load(path):
    rows = []
    for line in open(path, encoding="utf8"):
        r = json.loads(line)
        for part in r["messages"][0]["content"]:                      # replace the image file name by the picture itself
            if part["type"] == "image": part["image"] = Image.open(os.path.join(a.data, part["image"])).convert("RGB")
        rows.append({"messages": r["messages"]})
    return rows


model, tok = FastVisionModel.from_pretrained(a.base, load_in_4bit=True, use_gradient_checkpointing="unsloth")
model = FastVisionModel.get_peft_model(model, finetune_vision_layers=True, finetune_language_layers=True, finetune_attention_modules=True,
                                       finetune_mlp_modules=True, r=a.rank, lora_alpha=a.rank, lora_dropout=0, bias="none", random_state=3407)
FastVisionModel.for_training(model)
trainer = SFTTrainer(
    model=model, tokenizer=tok, data_collator=UnslothVisionDataCollator(model, tok), train_dataset=load(os.path.join(a.data, "train.jsonl")),
    args=SFTConfig(per_device_train_batch_size=1, gradient_accumulation_steps=8, warmup_steps=20, num_train_epochs=a.epochs, learning_rate=a.lr,
                   bf16=is_bf16_supported(), fp16=not is_bf16_supported(), logging_steps=10, optim="adamw_8bit", weight_decay=0.01,
                   lr_scheduler_type="linear", seed=3407, output_dir=a.out + "-ckpt", report_to="none", remove_unused_columns=False,
                   dataset_text_field="", dataset_kwargs={"skip_prepare_dataset": True}, max_length=6144, save_strategy="no"))
trainer.train()
model.save_pretrained(a.out + "-lora"); tok.save_pretrained(a.out + "-lora")                         # small adapter, always saved
model.save_pretrained_merged(a.out + "-merged", tok, save_method="merged_16bit")                      # full model for GGUF conversion
print("saved:", a.out + "-lora", a.out + "-merged", "\nnext: see dev/finetune/README.md, step 5")
