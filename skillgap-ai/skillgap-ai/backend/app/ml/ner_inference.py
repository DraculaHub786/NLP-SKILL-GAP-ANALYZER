"""Loads the fine-tuned skill-NER model once (module-level singleton) and
exposes extract_skills_ner() for use by skill_extractor.py.

Falls back gracefully (returns []) if no trained model has been saved yet to
app/ml/model_artifacts, so the rest of the app keeps working with the
taxonomy matcher alone until you've trained one (see docs/NER_MODEL_GUIDE.md).
"""
from dataclasses import dataclass
from pathlib import Path

import torch

_MODEL_DIR = Path(__file__).parent / "model_artifacts"

_tokenizer = None
_model = None


def _lazy_load():
    global _tokenizer, _model
    if _model is not None:
        return
    if not (_MODEL_DIR / "config.json").exists():
        return  # no trained model yet — caller should treat NER as unavailable

    from transformers import AutoModelForTokenClassification, AutoTokenizer

    _tokenizer = AutoTokenizer.from_pretrained(str(_MODEL_DIR))
    _model = AutoModelForTokenClassification.from_pretrained(str(_MODEL_DIR))
    _model.eval()


@dataclass
class NerSkillSpan:
    text: str
    confidence: float


def extract_skills_ner(text: str, min_confidence: float = 0.6) -> list[NerSkillSpan]:
    """Runs the fine-tuned model over `text`, returns SKILL spans with confidence.

    Confidence = mean softmax probability of the predicted label across the
    span's tokens — a simple but effective proxy for "how sure was the model".
    """
    _lazy_load()
    if _model is None:
        return []

    tokens = text.split()
    if not tokens:
        return []

    encoding = _tokenizer(tokens, is_split_into_words=True, return_tensors="pt", truncation=True)
    with torch.no_grad():
        logits = _model(**encoding).logits[0]
    probs = torch.softmax(logits, dim=-1)
    pred_ids = torch.argmax(probs, dim=-1).tolist()

    word_ids = encoding.word_ids(batch_index=0)
    id2label = _model.config.id2label

    spans: list[NerSkillSpan] = []
    current_tokens: list[str] = []
    current_confs: list[float] = []
    seen_words: set[int] = set()

    def flush():
        if current_tokens:
            avg_conf = sum(current_confs) / len(current_confs)
            if avg_conf >= min_confidence:
                spans.append(NerSkillSpan(text=" ".join(current_tokens), confidence=round(avg_conf, 3)))

    for pred_id, word_id in zip(pred_ids, word_ids):
        if word_id is None or word_id in seen_words:
            continue
        seen_words.add(word_id)
        label = id2label[pred_id]
        confidence = float(probs[word_ids.index(word_id)][pred_id])

        if label == "B-SKILL":
            flush()
            current_tokens, current_confs = [tokens[word_id]], [confidence]
        elif label == "I-SKILL" and current_tokens:
            current_tokens.append(tokens[word_id])
            current_confs.append(confidence)
        else:
            flush()
            current_tokens, current_confs = [], []

    flush()
    return spans
