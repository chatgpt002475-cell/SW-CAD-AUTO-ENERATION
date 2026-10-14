"""
Uncertainty Quantification and Assumption Reporting
Tracks confidence scores, distinguishes visible evidence from geometric inferences,
and flags missing dimensions or single-view perspective ambiguities.
"""

from typing import Dict, Any, List

class UncertaintyReporter:
    def __init__(self):
        self.assumptions: List[Dict[str, Any]] = []
        self.missing_inputs: List[Dict[str, Any]] = []
        self.confidence_scores: Dict[str, float] = {}

    def log_assumption(self, feature_name: str, parameter: str, assumed_val: Any, reason: str, confidence: float = 0.7):
        self.assumptions.append({
            "feature": feature_name,
            "parameter": parameter,
            "assumed_value": assumed_val,
            "reason": reason,
            "confidence": confidence
        })
        self.confidence_scores[f"{feature_name}.{parameter}"] = confidence

    def log_missing_input(self, parameter: str, suggested_default: Any, impact: str):
        self.missing_inputs.append({
            "parameter": parameter,
            "suggested_default": suggested_default,
            "impact": impact
        })

    def get_report(self) -> Dict[str, Any]:
        overall_conf = 1.0
        if self.confidence_scores:
            overall_conf = round(sum(self.confidence_scores.values()) / len(self.confidence_scores), 2)

        return {
            "overall_confidence": overall_conf,
            "assumptions_count": len(self.assumptions),
            "assumptions": self.assumptions,
            "missing_inputs": self.missing_inputs,
            "is_single_view": any("single 2D view" in a["reason"] for a in self.assumptions)
        }
