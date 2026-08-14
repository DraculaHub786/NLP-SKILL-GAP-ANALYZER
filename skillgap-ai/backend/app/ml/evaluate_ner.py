"""Entity-level precision/recall/F1 for a trained skill-NER model.

Usage:
    python -m app.ml.evaluate_ner --model app/ml/model_artifacts \
        --data app/ml/data/skill_ner_seed.jsonl
"""
import argparse
import json

import torch
from seqeval.metrics import classification_report
from transformers import AutoModelForTokenClassification, AutoTokenizer


def load_jsonl(path: str) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def predict_tags(tokens: list[str], tokenizer, model) -> list[str]:
    encoding = tokenizer(tokens, is_split_into_words=True, return_tensors="pt", truncation=True)
    with torch.no_grad():
        logits = model(**encoding).logits
    pred_ids = torch.argmax(logits, dim=2)[0].tolist()

    word_ids = encoding.word_ids(batch_index=0)
    tags, seen = [], set()
    for idx, word_id in zip(pred_ids, word_ids):
        if word_id is None or word_id in seen:
            continue
        seen.add(word_id)
        tags.append(model.config.id2label[idx])
    return tags


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--data", required=True)
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForTokenClassification.from_pretrained(args.model)
    model.eval()

    records = load_jsonl(args.data)
    y_true, y_pred = [], []
    for r in records:
        y_true.append(r["tags"])
        y_pred.append(predict_tags(r["tokens"], tokenizer, model))

    print(classification_report(y_true, y_pred))


if __name__ == "__main__":
    main()
