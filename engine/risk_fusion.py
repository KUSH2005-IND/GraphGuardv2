"""
GraphGuard v2 — Risk Fusion Engine
Combines edge, graph, and temporal scores into a single risk signal.
"""

import os, sys
import numpy as np
from typing import Dict, List, Optional
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class RiskFusionEngine:
    """
    Weighted fusion of edge, graph, and temporal intelligence signals.
    Generates alerts with severity levels and evidence aggregation.
    """

    def __init__(self):
        self.fused_scores: Dict[str, float] = {}
        self.alerts: List[Dict] = []
        self.score_breakdown: Dict[str, Dict] = {}

    def fuse(self, edge_scores: Dict[str, float],
             graph_scores: Dict[str, float],
             temporal_scores: Dict[str, float],
             graph_patterns: Dict[str, Dict] = None) -> Dict[str, float]:
        """
        Compute final risk = 0.4 * edge + 0.4 * graph + 0.2 * temporal.
        """
        self.graph_patterns = graph_patterns or {}
        print("[RiskFusion] Fusing intelligence signals...")

        all_accounts = set(edge_scores.keys()) | set(graph_scores.keys()) | set(temporal_scores.keys())

        w = config.FUSION_WEIGHTS
        for account_id in all_accounts:
            e = edge_scores.get(account_id, 0)
            g = graph_scores.get(account_id, 0)
            t = temporal_scores.get(account_id, 0)
            fused = w["edge"] * e + w["graph"] * g + w["temporal"] * t
            self.fused_scores[account_id] = round(min(fused, 1.0), 4)
            self.score_breakdown[account_id] = {
                "edge_score": round(e, 4),
                "graph_score": round(g, 4),
                "temporal_score": round(t, 4),
                "fused_score": self.fused_scores[account_id],
            }

        self._generate_alerts()
        print(f"[RiskFusion] Fusion complete. {len(self.alerts)} alerts generated.")
        return self.fused_scores

    def _generate_alerts(self):
        """Generate ranked alerts with severity levels."""
        self.alerts = []
        sorted_accounts = sorted(self.fused_scores.items(), key=lambda x: x[1], reverse=True)

        for account_id, score in sorted_accounts[:config.MAX_ALERTS]:
            severity = self._get_severity(score)
            if severity is None:
                continue
            breakdown = self.score_breakdown.get(account_id, {})
            self.alerts.append({
                "account_id": account_id,
                "fused_score": score,
                "severity": severity,
                "edge_score": breakdown.get("edge_score", 0),
                "graph_score": breakdown.get("graph_score", 0),
                "temporal_score": breakdown.get("temporal_score", 0),
                "pattern": self._classify_pattern(account_id),
            })

    def _classify_pattern(self, account_id: str) -> str:
        patterns = self.graph_patterns.get(account_id, {})
        if patterns.get("cycles"):        return "Circular Flow"
        if patterns.get("is_mule_hub"):   return "Mule Network"
        if patterns.get("dormant"):       return "Dormant Activation"
        if patterns.get("layering_chains"): return "Layering Chain"
        return "Anomalous Transfer"

    def _get_severity(self, score: float) -> Optional[str]:
        for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            if score >= config.ALERT_THRESHOLDS[level]:
                return level
        return None

    def get_alerts(self) -> List[Dict]:
        return self.alerts

    def get_score(self, account_id: str) -> Optional[Dict]:
        return self.score_breakdown.get(account_id)

    def get_top_accounts(self, n: int = 20) -> List[Dict]:
        sorted_accs = sorted(self.fused_scores.items(), key=lambda x: x[1], reverse=True)
        return [
            {"account_id": aid, **self.score_breakdown.get(aid, {})}
            for aid, _ in sorted_accs[:n]
        ]

    def get_stats(self) -> Dict:
        scores = list(self.fused_scores.values())
        if not scores:
            return {}
        severity_counts = defaultdict(int)
        for a in self.alerts:
            severity_counts[a["severity"]] += 1
        return {
            "total_accounts": len(scores),
            "mean_risk": round(np.mean(scores), 4),
            "max_risk": round(max(scores), 4),
            "alerts_by_severity": dict(severity_counts),
            "total_alerts": len(self.alerts),
        }
