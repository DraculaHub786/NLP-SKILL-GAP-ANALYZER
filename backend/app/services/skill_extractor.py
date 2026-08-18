"""Hybrid skill extraction: taxonomy phrase-matching + fine-tuned NER model.

Fusion rule (docs/NER_MODEL_GUIDE.md §5):
- Taxonomy hit  -> always kept, canonical name from the taxonomy.
- NER hit with no taxonomy overlap -> kept as a novel skill candidate,
  gated by min_ner_confidence.

The spaCy pipeline is loaded lazily (first extraction request, not at import
time) so the API can boot and tests can run without the model downloaded and
installed; NER is always best-effort and degrades to taxonomy-only matching.
"""
import json
import threading
from functools import lru_cache
from pathlib import Path

from dataclasses import dataclass, field

from app.core.config import settings
from app.ml.ner_inference import NerSkillSpan, extract_skills_ner
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractionResult:
    """Skills plus extraction-mode metadata for transparency."""
    skills: list[str] = field(default_factory=list)
    ner_active: bool = False
    mode: str = "taxonomy_only"

_TAXONOMY_PATH = Path(__file__).parent.parent / "ml" / "skills_taxonomy.json"

_nlp = None
_nlp_lock = threading.Lock()
_matcher = None
_alias_to_canonical: dict[str, str] = {}


@lru_cache(maxsize=1)
def _load_taxonomy() -> dict[str, list[str]]:
    try:
        return json.loads(_TAXONOMY_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.error("taxonomy_missing", path=str(_TAXONOMY_PATH))
        return {}
    except json.JSONDecodeError as exc:
        logger.error("taxonomy_invalid_json", path=str(_TAXONOMY_PATH), error=str(exc))
        return {}


def _get_nlp():
    """Lazily loads the spaCy pipeline once; returns None if unavailable."""
    global _nlp
    if _nlp is not None:
        return _nlp
    with _nlp_lock:
        if _nlp is not None:
            return _nlp
        try:
            import spacy

            _nlp = spacy.load(settings.spacy_model)
        except Exception as exc:  # model not installed, OSError, etc.
            logger.error("spacy_load_failed", error=str(exc))
            _nlp = False  # sentinel: don't retry on every request
        return _nlp or None


def _get_matcher():
    """Builds the PhraseMatcher from the taxonomy once; None if no taxonomy
    or spaCy is unavailable."""
    global _matcher
    if _matcher is not None:
        return _matcher
    nlp = _get_nlp()
    if nlp is None:
        return None
    with _nlp_lock:
        if _matcher is not None:
            return _matcher
        try:
            from spacy.matcher import PhraseMatcher

            taxonomy = _load_taxonomy()
            _matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
            for canonical, aliases in taxonomy.items():
                all_terms = [canonical] + aliases
                _matcher.add(canonical, [nlp.make_doc(term) for term in all_terms])
                for term in all_terms:
                    _alias_to_canonical[term.lower()] = canonical
        except Exception as exc:
            logger.error("matcher_build_failed", error=str(exc))
            _matcher = False
        return _matcher or None


def _taxonomy_matches_noun_chunks(nlp, doc) -> set[str]:
    """Noun-chunk pass catches multi-word aliases (e.g. 'Data Visualization')
    not tokenized as a single phrase by the PhraseMatcher."""
    found: set[str] = set()
    for chunk in doc.noun_chunks:
        key = chunk.text.strip().lower()
        canonical = _alias_to_canonical.get(key)
        if canonical:
            found.add(canonical)
    return found


def match_taxonomy(text: str) -> set[str]:
    """Pure taxonomy matching — no NER. Extracted into its own function so it
    can be tested in isolation and reused by the distant-supervision tier
    (docs/NER_MODEL_GUIDE.md §2 Tier 1)."""
    nlp = _get_nlp()
    matcher = _get_matcher()
    if nlp is None or matcher is None:
        return set()

    doc = nlp(text)
    found: set[str] = set()
    for match_id, _start, _end in matcher(doc):
        canonical = nlp.vocab.strings[match_id]
        if canonical:
            found.add(canonical)
    found |= _taxonomy_matches_noun_chunks(nlp, doc)
    return found


def _ner_model_loaded() -> bool:
    """Checks whether the NER model is available without triggering a load."""
    from app.ml.ner_inference import _lazy_load, _model as ner_model
    _lazy_load()
    from app.ml import ner_inference
    return ner_inference._model is not None


def extract_skills(text: str, min_ner_confidence: float = 0.6) -> list[str]:
    """Fuses taxonomy matches with NER predictions. Returns a sorted,
    de-duplicated list of canonical (or novel) skill names.

    Never raises: an NER inference failure degrades to taxonomy-only results
    (with a warning log) rather than breaking the request.
    """
    result = extract_skills_with_meta(text, min_ner_confidence=min_ner_confidence)
    return result.skills


def extract_skills_with_meta(
    text: str, min_ner_confidence: float = 0.6
) -> "ExtractionResult":
    """Returns skills plus extraction metadata (mode, ner_active flag).

    The `mode` field tells the caller whether the full hybrid pipeline ran
    or only the taxonomy fallback — so the API can surface this as a
    warning when the user gets a degraded scan.
    """
    if not text or not text.strip():
        return ExtractionResult(skills=[], ner_active=False, mode="taxonomy_only")

    taxonomy_found = match_taxonomy(text)

    ner_available = _ner_model_loaded()
    ner_spans: list[NerSkillSpan] = []
    if ner_available:
        try:
            ner_spans = extract_skills_ner(text, min_confidence=min_ner_confidence)
        except Exception as exc:
            # NER is best-effort; a model-inference hiccup must never 500 the API.
            logger.warning("ner_inference_failed_degrading_to_taxonomy", error=str(exc))
            ner_available = False

    taxonomy_lower = {s.lower() for s in taxonomy_found}
    novel = {span.text for span in ner_spans if span.text.lower() not in taxonomy_lower}

    return ExtractionResult(
        skills=sorted(taxonomy_found | novel),
        ner_active=ner_available,
        mode="hybrid" if ner_available else "taxonomy_only",
    )
