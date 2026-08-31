"""Phase 1.5 tests: Semantic Matching Layer.

Verifies:
- A mock-embedding model makes synonym pairs score above threshold
- Disjoint terms score near zero
- Changing weights measurably shifts the combined score
- Ontology boost works without embeddings (React => JavaScript)
"""
import pytest

from app.nlp import semantic_matcher


class FakeModel:
    """A stub embedding model with handcrafted similarity behavior."""

    def encode(self, texts, normalize_embeddings=True):
        import numpy as np

        # A tiny vector space: each text gets a deterministic pseudo-vector.
        # "Data Visualization" and "Dashboarding" are made similar; unrelated
        # terms are made orthogonal.
        vectors = []
        for t in texts:
            vectors.append(self._vector(t))
        return np.array(vectors, dtype=float)

    @staticmethod
    def _vector(text: str):
        import numpy as np

        t = text.lower()
        # Synonym group: Data Visualization == Dashboarding
        if "data visualization" in t or "dashboarding" in t:
            return np.array([1.0, 0.0, 0.0])
        # Synonym group: ML == Machine Learning
        if t == "ml" or t == "machine learning":
            return np.array([0.9, 0.0, 0.1])
        # Synonym group: React == React.js
        if "react" in t:
            return np.array([0.8, 0.2, 0.0])
        # Default: orthogonal-ish
        return np.array([0.1, 0.9, 0.3])


@pytest.fixture()
def fake_model():
    return FakeModel()


class TestSemanticScore:
    def test_synonym_pairs_score_high(self, fake_model):
        score = semantic_matcher.semantic_score("Data Visualization", "Dashboarding", model=fake_model)
        assert score > 0.8, f"Expected high score, got {score}"

    def test_disjoint_pairs_score_low(self, fake_model):
        score = semantic_matcher.semantic_score("Python", "Data Visualization", model=fake_model)
        assert score < 0.4, f"Expected low score, got {score}"


class TestOntologyScore:
    def test_prerequisite_boost(self):
        # Resume has React, JD wants JavaScript (a prerequisite)
        score = semantic_matcher.ontology_score("React", "JavaScript")
        assert score >= 0.6, f"Expected prerequisite boost, got {score}"

    def test_related_boost(self):
        score = semantic_matcher.ontology_score("Machine Learning", "Statistics")
        assert score >= 0.5

    def test_no_relationship(self):
        score = semantic_matcher.ontology_score("Python", "Docker")
        assert score == 0.0


class TestCombinedScore:
    def test_weight_changes_shift_score(self):
        """Same pair, different weights changes the combined score."""
        # Make the semantic weight 0 so only lexical+ontology matter.
        weights_lexical_only = {"lexical": 1.0, "semantic": 0.0, "ontology": 0.0}
        weights_semantic_only = {"lexical": 0.0, "semantic": 1.0, "ontology": 0.0}

        score_lex = semantic_matcher.combined_score("Machine Learning", "ML", weights=weights_lexical_only)
        score_sem = semantic_matcher.combined_score("Machine Learning", "ML", weights=weights_semantic_only)

        assert score_lex != score_sem, "Weights must measurably shift the score"

    def test_exact_match(self):
        score = semantic_matcher.combined_score("Python", "Python")
        assert score == 1.0

    def test_zero_for_empty(self):
        assert semantic_matcher.combined_score("", "Python") == 0.0


class TestMatchMatrix:
    def test_matrix_basic(self, fake_model):
        """Monkeypatch the module's embedding-getter to use the fake."""
        import app.nlp.semantic_matcher as sm

        original = sm._get_embedding_model
        sm._get_embedding_model = lambda: fake_model
        try:
            results = sm.match_matrix(["Python", "React"], ["Python", "JavaScript"], threshold=0.7)
        finally:
            sm._get_embedding_model = original

        assert len(results) == 4  # 2x2
        matched_pairs = [r for r in results if r["matched"]]
        assert any(r["resume_skill"] == "Python" and r["jd_skill"] == "Python" for r in matched_pairs)
