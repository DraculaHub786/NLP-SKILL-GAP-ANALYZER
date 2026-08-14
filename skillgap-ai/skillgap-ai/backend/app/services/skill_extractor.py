"""Hybrid skill extraction: taxonomy phrase-matching + fine-tuned NER model.

This is the "high accuracy" core:
- Taxonomy matching gives reliable, high-precision recall on known skills
  (with alias handling, e.g. 'JS' -> 'JavaScript').
- The fine-tuned NER model (see app/ml/ner_inference.py, trained via
  app/ml/train_ner.py) catches novel skills not yet in the taxonomy.
Both signals are fused in extract_skills(); see docs/NER_MODEL_GUIDE.md §5.
"""
import json
from pathlib import Path

import spacy
from spacy.matcher import PhraseMatcher

from app.ml.ner_inference import extract_skills_ner

_TAXONOMY_PATH = Path(__file__).parent.parent / "ml" / "skills_taxonomy.json"

_nlp = spacy.load("en_core_web_sm")


def _load_taxonomy() -> dict[str, list[str]]:
    if _TAXONOMY_PATH.exists():
        return json.loads(_TAXONOMY_PATH.read_text())
    return {}


_TAXONOMY = _load_taxonomy()  # canonical_skill -> [aliases]

_matcher = PhraseMatcher(_nlp.vocab, attr="LOWER")
_alias_to_canonical: dict[str, str] = {}
for canonical, aliases in _TAXONOMY.items():
    all_terms = [canonical] + aliases
    patterns = [_nlp.make_doc(term) for term in all_terms]
    _matcher.add(canonical, patterns)
    for term in all_terms:
        _alias_to_canonical[term.lower()] = canonical


def extract_skills(text: str, min_ner_confidence: float = 0.6) -> list[str]:
    """Fuses taxonomy matches (precise, known terms) with NER predictions
    (recall on novel/out-of-taxonomy terms).

    Fusion rule (docs/NER_MODEL_GUIDE.md §5):
    - Taxonomy hit -> always kept, using the canonical name.
    - NER hit with no taxonomy overlap -> kept as a novel skill candidate,
      gated by min_ner_confidence, tagged so callers can distinguish
      "known" vs "newly discovered" skills if desired.
    """
    doc = _nlp(text)

    taxonomy_found: set[str] = set()

    # 1. Taxonomy phrase matching (exact + alias) — noun-chunk heuristic
    #    catches multi-word aliases the PhraseMatcher's tokenization might miss.
    for match_id, start, end in _matcher(doc):
        canonical = _nlp.vocab.strings[match_id]
        taxonomy_found.add(canonical)
    for chunk in doc.noun_chunks:
        key = chunk.text.strip().lower()
        if key in _alias_to_canonical:
            taxonomy_found.add(_alias_to_canonical[key])

    # 2. Fine-tuned NER pass — novel skills not in the taxonomy.
    #    No-ops gracefully (returns []) until a model has been trained
    #    (see app/ml/train_ner.py); taxonomy-only extraction still works.
    ner_spans = extract_skills_ner(text, min_confidence=min_ner_confidence)
    taxonomy_lower = {s.lower() for s in taxonomy_found}
    novel_found = {
        span.text for span in ner_spans if span.text.lower() not in taxonomy_lower
    }

    return sorted(taxonomy_found | novel_found)
