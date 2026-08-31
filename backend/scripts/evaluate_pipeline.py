"""Pipeline Evaluation Script (Part D).

Runs all three evaluation modules (skill extraction, matching, recommendation)
over available validation data and prints a unified report.

Usage:
    cd backend
    python -m scripts.evaluate_pipeline
"""
from __future__ import annotations

import json
from pathlib import Path

from app.eval import matching_eval, recommendation_eval, skill_extraction_eval
from app.services.matcher import _get_model

REPO_ROOT = Path(__file__).parent.parent


def main() -> None:
    print("=" * 60)
    print("SkillGap AI — Evaluation Report")
    print("=" * 60)

    # ── 1. Matching evaluation ───────────────────────────────────────────
    print("\n[1] Matching (Lexical vs Semantic vs Hybrid)")
    model = _get_model()
    if model is not None:
        pairs_path = REPO_ROOT / "tests" / "fixtures" / "skill_match_pairs.jsonl"
        pairs = matching_eval.load_pairs(pairs_path)
        lexical = matching_eval.evaluate_lexical(pairs)
        semantic = matching_eval.evaluate_semantic(pairs, model)
        hybrid = matching_eval.evaluate_hybrid(pairs, model)
        print(f"  Lexical:   P={lexical['precision']:.3f} R={lexical['recall']:.3f} F1={lexical['f1']:.3f}")
        print(f"  Semantic:  P={semantic['precision']:.3f} R={semantic['recall']:.3f} F1={semantic['f1']:.3f}")
        print(f"  Hybrid:    P={hybrid['precision']:.3f} R={hybrid['recall']:.3f} F1={hybrid['f1']:.3f}")
    else:
        print("  Embedding model unavailable — skipping.")

    # ── 2. Recommendation metrics (synthetic demo) ───────────────────────
    print("\n[2] Recommendation (synthetic demo)")
    queries = [
        {"recommended": ["Backend Developer", "Fullstack", "DevOps"], "relevant": {"Backend Developer"}},
        {"recommended": ["Data Scientist", "ML Engineer", "Backend"], "relevant": {"ML Engineer"}},
        {"recommended": ["Frontend", "Designer", "Backend"], "relevant": {"Frontend"}},
    ]
    rec_metrics = recommendation_eval.evaluate_recommendations(queries, k=3)
    for k, v in rec_metrics.items():
        print(f"  {k}: {v}")

    # ── 3. Skill extraction (if a validation file exists) ────────────────
    validation_path = REPO_ROOT / "tests" / "fixtures" / "skill_extraction_val.jsonl"
    if validation_path.exists():
        print("\n[3] Skill Extraction")
        examples = skill_extraction_eval.load_examples(validation_path)
        metrics = skill_extraction_eval.evaluate_extraction(examples)
        print(f"  Examples: {metrics['tp'] + metrics['fn']} (TP={metrics['tp']} FP={metrics['fp']} FN={metrics['fn']})")
        print(f"  Precision: {metrics['precision']}  Recall: {metrics['recall']}  F1: {metrics['f1']}")
    else:
        print("\n[3] Skill Extraction — validation file not present, skipping.")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
