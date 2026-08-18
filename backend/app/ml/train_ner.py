"""Fine-tunes a token-classification model to recognize SKILL spans (BIO tags).

Usage:
    python -m app.ml.train_ner --data app/ml/data/skill_ner_seed.jsonl \
        --epochs 8 --out app/ml/model_artifacts

See docs/NER_MODEL_GUIDE.md for the data strategy (distant supervision via
the taxonomy matcher, then public datasets, then active learning).
"""
import argparse
import json
import random

import numpy as np
from datasets import Dataset
from seqeval.metrics import classification_report, f1_score
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
    Trainer,
    TrainingArguments,
)

LABELS = ["O", "B-SKILL", "I-SKILL"]
LABEL2ID = {l: i for i, l in enumerate(LABELS)}
ID2LABEL = {i: l for i, l in enumerate(LABELS)}


def load_jsonl(path: str) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def build_dataset(records: list[dict]) -> Dataset:
    return Dataset.from_dict(
        {
            "tokens": [r["tokens"] for r in records],
            "ner_tags": [[LABEL2ID[t] for t in r["tags"]] for r in records],
        }
    )


def tokenize_and_align(examples, tokenizer):
    tokenized = tokenizer(examples["tokens"], truncation=True, is_split_into_words=True)
    all_labels = []
    for i, labels in enumerate(examples["ner_tags"]):
        word_ids = tokenized.word_ids(batch_index=i)
        prev_word = None
        label_ids = []
        for word_id in word_ids:
            if word_id is None:
                label_ids.append(-100)
            elif word_id != prev_word:
                label_ids.append(labels[word_id])
            else:
                # Continuation of a split word-piece: inherit I- version
                label = labels[word_id]
                label_ids.append(label if LABELS[label] == "O" else LABEL2ID["I-SKILL"])
            prev_word = word_id
        all_labels.append(label_ids)
    tokenized["labels"] = all_labels
    return tokenized


def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=2)

    true_labels, true_preds = [], []
    for pred_row, label_row in zip(predictions, labels):
        seq_labels, seq_preds = [], []
        for p, l in zip(pred_row, label_row):
            if l != -100:
                seq_labels.append(ID2LABEL[l])
                seq_preds.append(ID2LABEL[p])
        true_labels.append(seq_labels)
        true_preds.append(seq_preds)

    return {"f1": f1_score(true_labels, true_preds)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--base_model", default="distilbert-base-uncased")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=3e-5)
    parser.add_argument("--out", default="app/ml/model_artifacts")
    args = parser.parse_args()

    records = load_jsonl(args.data)
    random.seed(42)
    random.shuffle(records)
    split = max(1, int(len(records) * 0.9))
    train_records, val_records = records[:split], records[split:] or records[:1]

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    model = AutoModelForTokenClassification.from_pretrained(
        args.base_model, num_labels=len(LABELS), id2label=ID2LABEL, label2id=LABEL2ID
    )

    train_ds = build_dataset(train_records).map(
        lambda ex: tokenize_and_align(ex, tokenizer), batched=True
    )
    val_ds = build_dataset(val_records).map(
        lambda ex: tokenize_and_align(ex, tokenizer), batched=True
    )

    training_args = TrainingArguments(
        output_dir=f"{args.out}/checkpoints",
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        num_train_epochs=args.epochs,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_steps=10,
        report_to=[],
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=DataCollatorForTokenClassification(tokenizer),
        compute_metrics=compute_metrics,
    )

    trainer.train()
    metrics = trainer.evaluate()
    print("Final validation metrics:", metrics)

    trainer.save_model(args.out)
    tokenizer.save_pretrained(args.out)
    print(f"Model saved to {args.out}")


if __name__ == "__main__":
    main()
