"""
Deterministic eval metrics — no LLM, no MLflow spans, fast.

Use these where exact or semantic-match assertions suffice.
Reserve judges.py for genuinely fuzzy outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TraitMatch:
    trait_key: str          # e.g. "instruction_modality"
    ground_truth: str       # ground-truth value from persona
    inferred_text: str | None   # best-matching MemoryItem.text, or None
    matched: bool


@dataclass
class InferenceReport:
    operator_id: str
    matched: list[TraitMatch] = field(default_factory=list)
    missed: list[TraitMatch] = field(default_factory=list)
    spurious: list[str] = field(default_factory=list)   # inferred but not in ground truth

    @property
    def precision(self) -> float:
        total = len(self.matched) + len(self.spurious)
        return len(self.matched) / total if total else 0.0

    @property
    def recall(self) -> float:
        total = len(self.matched) + len(self.missed)
        return len(self.matched) / total if total else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def as_dict(self) -> dict:
        return {
            "operator_id": self.operator_id,
            "precision": round(self.precision, 3),
            "recall": round(self.recall, 3),
            "f1": round(self.f1, 3),
            "matched": len(self.matched),
            "missed": len(self.missed),
            "spurious": len(self.spurious),
        }


def _keyword_overlap(ground_truth: str, candidate: str) -> bool:
    """Simple semantic match: significant keywords from ground truth appear in candidate."""
    gt_words = {w.lower() for w in ground_truth.split() if len(w) > 4}
    cand_lower = candidate.lower()
    return bool(gt_words) and any(w in cand_lower for w in gt_words)


def compute_inference_report(
    operator_id: str,
    ground_truth_traits: dict[str, str],
    inferred_items: list,           # list[MemoryItem]
) -> InferenceReport:
    """
    Compare inferred MemoryItems against persona ground-truth traits.
    Uses keyword overlap — deterministic, no LLM needed.
    Reserve LLM judge for qualitative/fuzzy comparisons.
    """
    report = InferenceReport(operator_id=operator_id)
    inferred_texts = [item.text for item in inferred_items]

    for trait_key, gt_value in ground_truth_traits.items():
        match_text = next(
            (t for t in inferred_texts if _keyword_overlap(gt_value, t)),
            None,
        )
        tm = TraitMatch(
            trait_key=trait_key,
            ground_truth=gt_value,
            inferred_text=match_text,
            matched=match_text is not None,
        )
        (report.matched if tm.matched else report.missed).append(tm)

    gt_keywords = {
        w.lower()
        for v in ground_truth_traits.values()
        for w in v.split() if len(w) > 4
    }
    for item in inferred_items:
        if not any(_keyword_overlap(gt, item.text) for gt in ground_truth_traits.values()):
            report.spurious.append(item.text)

    return report
