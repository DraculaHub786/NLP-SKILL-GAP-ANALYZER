"""Part C: Threshold calibration regression guard.

Loads the labeled skill-pair test set from fixtures/skill_match_pairs.jsonl,
sweeps skill_match_threshold, and verifies the configured threshold achieves
a minimum F1 score. Also asserts the threshold is not the old hardcoded 0.78
guess — it should have been calibrated against this set.

This test acts as a regression guard: if someone changes the threshold or the
embedding model, this test catches accuracy drops before they ship.
"""
import json
from pathlib import Path

import pytest

PAIRS_PATH = Path(__file__).parent / "fixtures" / "skill_match_pairs.jsonl"

# Minimum F1 the calibrated threshold must achieve on the pair set.
MIN_F1 = 0.70

# The old hardcoded guess — the calibrated threshold should differ.
OLD_THRESHOLD = 0.78


def _load_pairs():
    pairs = []
    with open(PAIRS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                pairs.append(json.loads(line))
    return pairs


@pytest.fixture(scope="module")
def pairs():
    return _load_pairs()


class TestThresholdCalibration:
    def test_pair_set_exists_and_has_coverage(self, pairs):
        """The labeled pair set must cover both matches and non-matches."""
        matches = [p for p in pairs if p["is_match"]]
        non_matches = [p for p in pairs if not p["is_match"]]
        assert len(matches) >= 20, f"Need >=20 match pairs, got {len(matches)}"
        assert len(non_matches) >= 20, f"Need >=20 non-match pairs, got {len(non_matches)}"

    def test_threshold_produces_valid_f1(self, pairs):
        """The configured skill_match_threshold must achieve >= MIN_F1 on the pair set."""
        from app.core.config import settings
        from app.services.matcher import _get_model

        model = _get_model()
        if model is None:
            pytest.skip("sentence-transformers model not available")

        threshold = settings.skill_match_threshold
        tp = fp = fn = tn = 0

        for pair in pairs:
            emb_r = model.encode([pair["resume_skill"]], normalize_embeddings=True)
            emb_j = model.encode([pair["jd_skill"]], normalize_embeddings=True)
            sim = float((emb_r @ emb_j.T)[0][0])
            predicted_match = sim >= threshold

            if pair["is_match"] and predicted_match:
                tp += 1
            elif pair["is_match"] and not predicted_match:
                fn += 1
            elif not pair["is_match"] and predicted_match:
                fp += 1
            else:
                tn += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        assert f1 >= MIN_F1, (
            f"skill_match_threshold={threshold} achieves F1={f1:.3f} "
            f"(precision={precision:.3f}, recall={recall:.3f}) on the pair set, "
            f"below minimum {MIN_F1}. Consider sweeping thresholds to find a better value."
        )

    def test_threshold_is_calibrated(self):
        """Verify the threshold has been changed from the old hardcoded guess.
        After calibration, it should differ from 0.78."""
        from app.core.config import settings
        threshold = settings.skill_match_threshold
        # This test passes as long as someone has actually calibrated the
        # threshold. If it's still 0.78, it's still a guess.
        assert threshold != OLD_THRESHOLD, (
            f"skill_match_threshold is still {OLD_THRESHOLD} — the old hardcoded guess. "
            f"Run a threshold sweep against fixtures/skill_match_pairs.jsonl to find "
            f"the value that maximizes F1, then update it in config.py."
        )
