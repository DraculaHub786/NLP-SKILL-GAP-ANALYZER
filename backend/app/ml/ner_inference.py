"""Loads the fine-tuned skill-NER model once (module-level singleton) and
exposes extract_skills_ner() for use by skill_extractor.py.

Falls back gracefully (returns []) if no trained model has been saved yet to
app/ml/model_artifacts, so the rest of the app keeps working with the
taxonomy matcher alone until you've trained one (see docs/NER_MODEL_GUIDE.md §3).

Heavy deps (torch, transformers) are imported lazily inside _lazy_load so this
module — and therefore the whole API — can boot and be tested without the
model stack installed.
"""
import re
from dataclasses import dataclass
from pathlib import Path

_MODEL_DIR = Path(__file__).parent / "model_artifacts"

# Tokenize to match training data style: words vs. punctuation as separate tokens.
# Training data splits "React, TypeScript" into ["React", ",", "TypeScript"].
_TOKEN_RE = re.compile(r"\w+|[^\w\s]")

_tokenizer = None
_model = None


def _lazy_load() -> None:
    global _tokenizer, _model
    if _model is not None:
        return
    if not (_MODEL_DIR / "config.json").exists():
        return  # no trained model yet — caller should treat NER as unavailable

    try:
        import torch  # noqa: F401
        from transformers import AutoModelForTokenClassification, AutoTokenizer
    except ImportError:
        return  # model stack not installed — degrade to taxonomy-only

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

    import torch

    # Fix #3: Use punctuation-aware tokenization matching training data style,
    # not plain whitespace split. Training data has punctuation as separate tokens.
    tokens = _TOKEN_RE.findall(text)
    if not tokens:
        return []

    encoding = _tokenizer(
        tokens, is_split_into_words=True, return_tensors="pt", truncation=True
    )
    with torch.no_grad():
        logits = _model(**encoding).logits[0]
    probs = torch.softmax(logits, dim=-1)
    pred_ids = torch.argmax(probs, dim=-1).tolist()

    word_ids = encoding.word_ids(batch_index=0)
    id2label = _model.config.id2label

    # Map the first sub-token of each original word -> its position in `tokens`
    # so we can recover confidence directly by index (avoids O(n²) lookups).
    word_to_sub_index: list[int] = []
    sub_word_index = -1
    for wid in word_ids:
        if wid is None:
            continue
        sub_word_index += 1
        word_to_sub_index.append(sub_word_index)

    spans: list[NerSkillSpan] = []
    current_tokens: list[str] = []
    current_confs: list[float] = []
    seen_words: set[int] = set()

    def flush() -> None:
        if current_tokens:
            avg_conf = sum(current_confs) / len(current_confs)
            if avg_conf >= min_confidence:
                spans.append(
                    NerSkillSpan(text=" ".join(current_tokens), confidence=round(avg_conf, 3))
                )

    sub_idx_iter = iter(word_to_sub_index)
    for wid in word_ids:
        if wid is None:
            continue
        sub_idx = next(sub_idx_iter)
        if wid in seen_words:
            continue
        seen_words.add(wid)

        label = id2label[pred_ids[sub_idx]]
        confidence = float(probs[sub_idx][pred_ids[sub_idx]])

        if label == "B-SKILL":
            flush()
            current_tokens, current_confs = [tokens[wid]], [confidence]
        elif label == "I-SKILL" and current_tokens:
            current_tokens.append(tokens[wid])
            current_confs.append(confidence)
        else:
            flush()
            current_tokens, current_confs = [], []

    flush()
    return spans
