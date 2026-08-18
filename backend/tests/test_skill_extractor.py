"""Phase 1 & 3 tests for the hybrid skill extractor.

These exercise the taxonomy matcher against the real skills_taxonomy.json.
When spaCy isn't installed/available the matcher degrades to returning
empty sets — the degradation itself is asserted in test_no_spacy_degrades_gracefully.
"""
import json
from pathlib import Path

import pytest

from app.services import skill_extractor

TAXONOMY_PATH = Path(__file__).parent.parent / "app" / "ml" / "skills_taxonomy.json"


@pytest.fixture()
def reset_matcher_cache():
    """Forces a fresh matcher build per test so alias maps stay clean."""
    skill_extractor._matcher = None
    skill_extractor._alias_to_canonical = {}
    yield
    skill_extractor._matcher = None
    skill_extractor._alias_to_canonical = {}


def test_taxonomy_has_reasonable_coverage():
    taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    assert len(taxonomy) >= 200, "taxonomy should be a real working set, not a stub"


@pytest.mark.skipif(skill_extractor._get_nlp() is None, reason="spaCy model not installed")
def test_alias_resolution_js_to_javascript():
    skills = skill_extractor.match_taxonomy("Fluent in JS and building React apps.")
    assert "JavaScript" in skills
    assert "React" in skills


@pytest.mark.skipif(skill_extractor._get_nlp() is None, reason="spaCy model not installed")
def test_no_match_returns_empty():
    assert skill_extractor.match_taxonomy("I enjoy gardening and hiking.") == set()


@pytest.mark.skipif(skill_extractor._get_nlp() is None, reason="spaCy model not installed")
def test_case_insensitivity():
    assert "python" in {s.lower() for s in skill_extractor.match_taxonomy("PYTHON")}
    assert "Python" in skill_extractor.match_taxonomy("python")


@pytest.mark.skipif(skill_extractor._get_nlp() is None, reason="spaCy model not installed")
def test_multi_word_skill_phrase():
    skills = skill_extractor.match_taxonomy("Deep experience with natural language processing.")
    assert "Natural Language Processing" in skills


@pytest.mark.skipif(skill_extractor._get_nlp() is None, reason="spaCy model not installed")
def test_empty_and_whitespace_input():
    assert skill_extractor.extract_skills("") == []
    assert skill_extractor.extract_skills("   \n  ") == []


@pytest.mark.skipif(skill_extractor._get_nlp() is None, reason="spaCy model not installed")
def test_extract_skills_dedupes_and_sorts():
    skills = skill_extractor.extract_skills("Python, python, and more Python with SQL.")
    # canonical name appears once
    assert skills.count("Python") == 1
    assert skills == sorted(skills)


def test_no_spacy_degrades_gracefully():
    """If spaCy can't be loaded, extraction must return [] — never raise."""
    original = skill_extractor._nlp
    skill_extractor._nlp = None  # force reload attempt
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(skill_extractor, "_get_nlp", lambda: None)
            assert skill_extractor.match_taxonomy("Python and React") == set()
            assert skill_extractor.extract_skills("Python and React") == []
    finally:
        skill_extractor._nlp = original
