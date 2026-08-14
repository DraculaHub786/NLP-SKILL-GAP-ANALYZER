"""Phase 3 tests for the NER inference wrapper.

The load-bearing property: with no trained model artifact present (the
default state of a fresh checkout), extract_skills_ner() must return []
without raising — the rest of the app keeps working on taxonomy matching.
"""
from pathlib import Path

import pytest

import app.ml.ner_inference as ner_inference


@pytest.fixture()
def no_model(monkeypatch):
    """Point the loader at a directory that can never contain a trained model."""
    monkeypatch.setattr(ner_inference, "_MODEL_DIR", Path("/nonexistent/model/dir"))
    ner_inference._model = None
    ner_inference._tokenizer = None
    yield
    ner_inference._model = None
    ner_inference._tokenizer = None


def test_no_trained_model_returns_empty(no_model):
    assert ner_inference.extract_skills_ner("Built data pipelines with Apache Airflow.") == []


def test_no_trained_model_empty_text(no_model):
    assert ner_inference.extract_skills_ner("") == []


def test_no_trained_model_low_confidence_rejected(no_model):
    assert ner_inference.extract_skills_ner("x", min_confidence=0.9) == []


def test_confidence_threshold_gating_defaults(no_model):
    """Sanity: default call path produces a list (empty here)."""
    result = ner_inference.extract_skills_ner("some text", min_confidence=0.6)
    assert isinstance(result, list)


def test_model_dir_clean_after_degradation(no_model):
    ner_inference.extract_skills_ner("whatever")
    assert ner_inference._model is None
