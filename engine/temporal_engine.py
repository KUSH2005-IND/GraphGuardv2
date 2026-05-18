"""
GraphGuard v2 — Temporal Intelligence Engine
Lightweight temporal reasoning over evolving transaction subgraphs.
"""

import os, sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class TemporalIntelligenceEngine:
    """
    Temporal reasoning layer analyzing how suspicious behavior
    evolves over time through propagation patterns.
    """

    def __init__(self):
        self.account_temporal_scores: Dict[str, float] = {}
        self.account_temporal_profiles: Dict[str, Dict] = {}
        self.temporal_timelines: Dict[str, List] = {}

    def analyze(self, transactions_df: pd.DataFrame, accounts_df: pd.DataFrame) -> Dict[str, float]:
        """Run temporal analysis and compute per-account temporal risk scores."""
        print("[TemporalEngine] Running temporal intelligence analysis...")

        txns = transactions_df.copy()
        txns["timestamp_dt"] = pd.to_datetime(txns["timestamp"], format="ISO8601")
        txns = txns.sort_values("timestamp_dt")

        account_txns = defaultdict(list)
        for _, tx in txns.iterrows():
            rec = {
                "tx_id": tx["tx_id"], "amount": tx["amount"],
                "timestamp": tx["timestamp_dt"], "counterparty": tx["receiver_id"],
                "direction": "out", "sender": tx["sender_id"], "receiver": tx["receiver_id"],
            }
            account_txns[tx["sender_id"]].append(rec)
            rec_in = rec.copy()
            rec_in["direction"] = "in"
            rec_in["counterparty"] = tx["sender_id"]
            account_txns[tx["receiver_id"]].append(rec_in)

        dormant_ids = set(accounts_df[accounts_df["account_type"] == "dormant"]["account_id"])

        for account_id, txn_list in account_txns.items():
            txn_list.sort(key=lambda x: x["timestamp"])
            profile = self._build_temporal_profile(account_id, txn_list, dormant_ids)
            self.account_temporal_profiles[account_id] = profile
            self.account_temporal_scores[account_id] = profile["temporal_risk_score"]
            self.temporal_timelines[account_id] = self._build_timeline(account_id, txn_list)

        flagged = sum(1 for s in self.account_temporal_scores.values() if s > 0.3)
        print(f"[TemporalEngine] Analysis complete. {flagged} accounts with elevated temporal risk.")
        return self.account_temporal_scores

    def _build_temporal_profile(self, account_id: str, txns: List[Dict],
                                 dormant_ids: set) -> Dict:
        """Build temporal behavioral profile for an account."""
        outflows = [t for t in txns if t["direction"] == "out"]
        inflows = [t for t in txns if t["direction"] == "in"]

        # Propagation speed: avg time between inflow and subsequent outflow
        prop_speeds = []
        for outflow in outflows:
            prior_inflows = [i for i in inflows if i["timestamp"] < outflow["timestamp"]]
            if prior_inflows:
                last_in = max(prior_inflows, key=lambda x: x["timestamp"])
                delta = (outflow["timestamp"] - last_in["timestamp"]).total_seconds() / 3600
                prop_speeds.append(delta)
        avg_prop_speed = np.mean(prop_speeds) if prop_speeds else 999
        min_prop_speed = min(prop_speeds) if prop_speeds else 999

        # Retention time analysis
        retention_times = prop_speeds  # Same as propagation
        avg_retention = avg_prop_speed
        min_retention = min_prop_speed

        # Temporal hop density: outflows per hour in peak window
        peak_density = 0
        if outflows:
            window = timedelta(hours=config.VELOCITY_WINDOW_HOURS)
            for i, tx in enumerate(outflows):
                count = sum(1 for t in outflows if tx["timestamp"] <= t["timestamp"] <= tx["timestamp"] + window)
                hourly_rate = count / config.VELOCITY_WINDOW_HOURS
                peak_density = max(peak_density, hourly_rate)

        # Beneficiary expansion: unique recipients over time windows
        weekly_beneficiaries = defaultdict(set)
        for tx in outflows:
            week = tx["timestamp"].isocalendar()[1]
            weekly_beneficiaries[week].add(tx["counterparty"])
        expansion_rates = []
        weeks = sorted(weekly_beneficiaries.keys())
        cumulative = set()
        for w in weeks:
            new_this_week = weekly_beneficiaries[w] - cumulative
            expansion_rates.append(len(new_this_week))
            cumulative.update(weekly_beneficiaries[w])
        avg_expansion = np.mean(expansion_rates) if expansion_rates else 0
        max_expansion = max(expansion_rates) if expansion_rates else 0

        # Burst redistribution: max outflows in a short window after inflow
        burst_score = 0
        for inflow in inflows:
            window = timedelta(hours=config.RETENTION_THRESHOLD_HOURS * 2)
            rapid_outs = [o for o in outflows
                          if inflow["timestamp"] <= o["timestamp"] <= inflow["timestamp"] + window]
            if len(rapid_outs) > burst_score:
                burst_score = len(rapid_outs)

        # Dormant activation score
        dormant_score = 0
        if account_id in dormant_ids and len(txns) > 2:
            dormant_score = 1.0

        # ── Compute composite temporal risk score ────────────────────
        score = 0.0
        # Fast propagation
        if min_prop_speed < config.PROPAGATION_SPEED_THRESHOLD:
            score += 0.25
        elif avg_prop_speed < 2:
            score += 0.15

        # Short retention
        if min_retention < config.RETENTION_THRESHOLD_HOURS:
            score += 0.2
        elif avg_retention < 6:
            score += 0.1

        # High hop density
        if peak_density > 2:
            score += 0.2
        elif peak_density > 0.5:
            score += 0.1

        # Rapid beneficiary expansion
        if max_expansion > 5:
            score += 0.15
        elif max_expansion > 3:
            score += 0.08

        # Burst redistribution
        if burst_score >= 5:
            score += 0.2
        elif burst_score >= 3:
            score += 0.1

        # Dormant activation
        score += dormant_score * 0.2

        return {
            "avg_propagation_speed_hrs": round(avg_prop_speed, 2),
            "min_propagation_speed_hrs": round(min_prop_speed, 2),
            "avg_retention_hrs": round(avg_retention, 2),
            "min_retention_hrs": round(min_retention, 2),
            "peak_hop_density_per_hr": round(peak_density, 3),
            "avg_beneficiary_expansion": round(avg_expansion, 2),
            "max_beneficiary_expansion": max_expansion,
            "burst_redistribution_count": burst_score,
            "dormant_activation": dormant_score,
            "total_outflows": len(outflows),
            "total_inflows": len(inflows),
            "unique_beneficiaries": len(set(t["counterparty"] for t in outflows)),
            "temporal_risk_score": round(min(score, 1.0), 4),
        }

    def _build_timeline(self, account_id: str, txns: List[Dict]) -> List[Dict]:
        """Build temporal event timeline for investigation display."""
        events = []
        for tx in txns[-20:]:  # Last 20 events
            events.append({
                "timestamp": tx["timestamp"].isoformat(),
                "direction": tx["direction"],
                "amount": tx["amount"],
                "counterparty": tx["counterparty"],
                "tx_id": tx["tx_id"],
            })
        return events

    def get_temporal_profile(self, account_id: str) -> Optional[Dict]:
        return self.account_temporal_profiles.get(account_id)

    def get_timeline(self, account_id: str) -> List[Dict]:
        return self.temporal_timelines.get(account_id, [])
