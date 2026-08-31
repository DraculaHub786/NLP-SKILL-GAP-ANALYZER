"""Threshold Calibration Script (Part C).

Sweeps skill_match_threshold over the labeled skill-pair set and finds the
value that maximizes F1 (and reports precision/recall at each point).

Usage:
    cd backend
    python -m scripts.calibrate_threshold

The best threshold is printed at the end. Update config.py's
skill_match_threshold with the recommended value.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from app.core.config import settings
from app.services.matcher import _get_model

PAIRS_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "skill_match_pairs.jsonl"

# Sweep range.
START = 0.50
END = 0.95
STEP = 0.01


def load_pairs(path: Path = PAIRS_PATH) -> list[dict]:
    pairs: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                pairs.append(json.loads(line))
    return pairs


def evaluate_pair_set(pairs: list[dict], model, threshold: float) -> dict[str, float]:
    """Returns precision/recall/F1 for a given threshold."""
    tp = fp = fn = tn = 0
    for pair in pairs:
        emb_r = model.encode([pair["resume_skill"]], normalize_embeddings=True)
        emb_j = model.encode([pair["jd_skill"]], normalize_embeddings=True)
        sim = float((emb_r @ emb_j.T)[0][0])
        predicted = sim >= threshold
        if pair["is_match"] and predicted:
            tp += 1
        elif pair["is_match"] and not predicted:
            fn += 1
        elif not pair["is_match"] and predicted:
            fp += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def main() -> None:
    model = _get_model()
    if model is None:
        print("Error: sentence-transformers model not available.")
        return

    pairs = load_pairs()
    print(f"Loaded {len(pairs)} labeled pairs "
          f"({sum(1 for p in pairs if p['is_match'])} matches, "
          f"{sum(1 for p in pairs if not p['is_match'])} non-matches)")

    best = {"f1": -1.0, "threshold": None}
    results: list[dict] = []
    import numpy as np

    # Pre-encode all skills once for speed.
    all_skills = set()
    for p in pairs:
        all_skills.add(p["resume_skill"])
        all_skills.add(p["jd_skill"])
    skill_list = sorted(all_skills)
    emb = model.encode(skill_list, normalize_embeddings=True)
    idx = {s: i for i, s in enumerate(skill_list)}

    for t in [round(START + i * STEP, 2) for i in range(int((END - START) / STEP) + 1)]:
        tp = fp = fn = tn = 0
        for p in pairs:
            sim = float(np.dot(emb[idx[p["resume_skill"]]], emb[idx[p["jd_skill"]]]))
            predicted = sim >= t
            if p["is_match"] and predicted:
                tp += 1
            elif p["is_match"] and not predicted:
                fn += 1
            elif not p["is_match"] and predicted:
                fp += 1
            else:
                tn += 1
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        results.append({
            "threshold": t,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
        })
        if f1 > best["f1"]:
            best = {"f1": f1, "threshold": t}

    print("\nThreshold sweep (best F1 highlighted):")
    print(f"{'Threshold':<10} {'Precision':<10} {'Recall':<10} {'F1':<10}")
    for r in results:
        marker = " *" if r["threshold"] == best["threshold"] else ""
        print(f"{r['threshold']:<10.2f} {r['precision']:<10.3f} {r['recall']:<10.3f} {r['f1']:<10.3f}{marker}")

    print(f"\nBest threshold: {best['threshold']} (F1={best['f1']:.3f})")
    print(f"Current config value: {settings.skill_match_threshold}")
    if best["threshold"] is not None and best["threshold"] != settings.skill_match_threshold:
        print(f"=> Update settings.skill_match_threshold to {best['threshold']}")


if __name__ == "__main__":
    main()
