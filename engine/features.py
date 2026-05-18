"""
GraphGuard v2 — Feature Extraction Engine
Computes temporal, behavioral, and structural features per transaction
for the XGBoost edge risk scorer.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class FeatureExtractor:
    """
    Extracts rich temporal and behavioral features from transaction data.
    Features focus on liquidity propagation behavior, not just raw amounts.
    """

    def __init__(self):
        self.account_profiles = {}
        self.account_history = defaultdict(list)
        self.account_beneficiaries = defaultdict(set)

    def fit(self, accounts_df: pd.DataFrame, transactions_df: pd.DataFrame):
        """Build account profiles from historical data."""
        print("[Features] Building account profiles...")

        # Build per-account profiles
        for _, acc in accounts_df.iterrows():
            aid = acc["account_id"]
            self.account_profiles[aid] = {
                "avg_tx_amount": acc["avg_tx_amount"],
                "avg_tx_frequency": acc["avg_tx_frequency"],
                "account_type": acc["account_type"],
                "is_dormant": acc["is_dormant"],
                "branch": acc["branch"],
            }

        # Build transaction history index
        txns = transactions_df.copy()
        txns["timestamp_dt"] = pd.to_datetime(txns["timestamp"], format="ISO8601")
        txns = txns.sort_values("timestamp_dt")

        for _, tx in txns.iterrows():
            sid = tx["sender_id"]
            rid = tx["receiver_id"]
            ts = tx["timestamp_dt"]
            amt = tx["amount"]

            self.account_history[sid].append({
                "direction": "out", "amount": amt,
                "timestamp": ts, "counterparty": rid, "tx_id": tx["tx_id"]
            })
            self.account_history[rid].append({
                "direction": "in", "amount": amt,
                "timestamp": ts, "counterparty": sid, "tx_id": tx["tx_id"]
            })
            self.account_beneficiaries[sid].add(rid)

        print(f"[Features] Profiles built for {len(self.account_profiles)} accounts")

    def extract(self, transactions_df: pd.DataFrame) -> pd.DataFrame:
        """Extract all features for each transaction."""
        print("[Features] Extracting features...")
        txns = transactions_df.copy()
        txns["timestamp_dt"] = pd.to_datetime(txns["timestamp"], format="ISO8601")
        txns = txns.sort_values("timestamp_dt").reset_index(drop=True)

        features = []
        for idx, tx in txns.iterrows():
            feat = self._extract_single(tx, txns, idx)
            features.append(feat)

        feature_df = pd.DataFrame(features)
        print(f"[Features] Extracted {len(config.EDGE_FEATURES)} features for {len(feature_df)} transactions")
        return feature_df

    def _extract_single(self, tx: pd.Series, all_txns: pd.DataFrame, idx: int) -> Dict:
        """Extract features for a single transaction."""
        sid = tx["sender_id"]
        rid = tx["receiver_id"]
        amt = tx["amount"]
        ts = tx["timestamp_dt"]

        sender_profile = self.account_profiles.get(sid, {})
        receiver_profile = self.account_profiles.get(rid, {})
        sender_hist = self.account_history.get(sid, [])

        # ── Amount features ──────────────────────────────────────────
        amount_log = np.log1p(amt)
        sender_avg = sender_profile.get("avg_tx_amount", amt)
        amount_deviation = (amt - sender_avg) / max(sender_avg, 1)
        amount_to_avg_ratio = amt / max(sender_avg, 1)

        # ── Time features ────────────────────────────────────────────
        hour_of_day = ts.hour
        day_of_week = ts.dayofweek
        is_weekend = 1 if day_of_week >= 5 else 0

        # Time anomaly: unusual hours (before 6am, after 11pm)
        time_anomaly = 1.0 if (hour_of_day < 6 or hour_of_day > 23) else 0.0

        # ── Retention time ───────────────────────────────────────────
        # How quickly did the sender forward funds after last inflow?
        retention_time = self._compute_retention_time(sid, ts)

        # ── Propagation velocity ─────────────────────────────────────
        propagation_velocity = self._compute_propagation_velocity(sid, rid, ts, all_txns, idx)

        # ── Burst ratio ──────────────────────────────────────────────
        burst_ratio = self._compute_burst_ratio(sid, ts)

        # ── Temporal hop density ─────────────────────────────────────
        temporal_hop_density = self._compute_temporal_hop_density(sid, ts, all_txns, idx)

        # ── Beneficiary expansion rate ───────────────────────────────
        beneficiary_expansion_rate = self._compute_beneficiary_expansion(sid, rid, ts)

        # ── Cascade score ────────────────────────────────────────────
        cascade_score = self._compute_cascade_score(rid, ts, all_txns, idx)

        # ── Dormant activation ───────────────────────────────────────
        sender_dormant = 1.0 if sender_profile.get("is_dormant", False) else 0.0
        receiver_dormant = 1.0 if receiver_profile.get("is_dormant", False) else 0.0
        dormant_activation = max(sender_dormant, receiver_dormant)

        # ── Beneficiary novelty ──────────────────────────────────────
        known_beneficiaries = self.account_beneficiaries.get(sid, set())
        beneficiary_novelty = 0.0 if rid in known_beneficiaries else 1.0

        # ── Transaction velocity ─────────────────────────────────────
        transaction_velocity = self._compute_tx_velocity(sid, ts)

        # ── Structuring indicator ────────────────────────────────────
        structuring_indicator = self._compute_structuring_indicator(sid, amt, ts)

        # ── Sender/receiver stats ────────────────────────────────────
        sender_avg_amount = sender_avg
        sender_tx_count = len([h for h in sender_hist if h["direction"] == "out"])
        receiver_hist = self.account_history.get(rid, [])
        receiver_tx_count = len([h for h in receiver_hist if h["direction"] == "in"])

        return {
            "tx_id": tx["tx_id"],
            "amount_log": round(amount_log, 4),
            "amount_deviation": round(min(amount_deviation, 10), 4),
            "hour_of_day": hour_of_day,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "retention_time": round(retention_time, 4),
            "propagation_velocity": round(propagation_velocity, 4),
            "burst_ratio": round(min(burst_ratio, 20), 4),
            "temporal_hop_density": round(temporal_hop_density, 4),
            "beneficiary_expansion_rate": round(min(beneficiary_expansion_rate, 10), 4),
            "cascade_score": round(cascade_score, 4),
            "dormant_activation": dormant_activation,
            "beneficiary_novelty": beneficiary_novelty,
            "transaction_velocity": round(min(transaction_velocity, 50), 4),
            "time_anomaly": time_anomaly,
            "structuring_indicator": round(structuring_indicator, 4),
            "sender_avg_amount": round(sender_avg_amount, 2),
            "sender_tx_count": sender_tx_count,
            "receiver_tx_count": receiver_tx_count,
            "amount_to_avg_ratio": round(min(amount_to_avg_ratio, 20), 4),
        }

    # ── Feature computation helpers ──────────────────────────────────────

    def _compute_retention_time(self, account_id: str, current_ts: datetime) -> float:
        """Time between last inflow and current outflow (hours). Low = suspicious."""
        hist = self.account_history.get(account_id, [])
        inflows = [h for h in hist if h["direction"] == "in" and h["timestamp"] < current_ts]
        if not inflows:
            return 999.0  # No prior inflow — high retention (normal)

        last_inflow_ts = max(h["timestamp"] for h in inflows)
        delta_hours = (current_ts - last_inflow_ts).total_seconds() / 3600
        return min(delta_hours, 999.0)

    def _compute_propagation_velocity(self, sender: str, receiver: str,
                                       ts: datetime, all_txns: pd.DataFrame, idx: int) -> float:
        """Speed of fund movement — low retention + immediate forwarding = high velocity."""
        retention = self._compute_retention_time(sender, ts)
        if retention > 100:
            return 0.0
        # Velocity is inverse of retention (capped)
        return min(1.0 / max(retention, 0.01), 100.0)

    def _compute_burst_ratio(self, account_id: str, current_ts: datetime) -> float:
        """Ratio of recent activity to baseline."""
        hist = self.account_history.get(account_id, [])
        if not hist:
            return 0.0

        window = timedelta(hours=config.VELOCITY_WINDOW_HOURS)
        baseline_window = timedelta(days=config.BURST_BASELINE_DAYS)

        recent = len([h for h in hist
                      if h["direction"] == "out"
                      and current_ts - window <= h["timestamp"] <= current_ts])
        baseline_start = current_ts - baseline_window
        baseline = len([h for h in hist
                        if h["direction"] == "out"
                        and baseline_start <= h["timestamp"] < current_ts - window])

        baseline_rate = baseline / max(config.BURST_BASELINE_DAYS * 24 / config.VELOCITY_WINDOW_HOURS, 1)
        if baseline_rate < 0.1:
            return recent * 2  # Account was quiet, any activity is a burst
        return recent / baseline_rate

    def _compute_temporal_hop_density(self, account_id: str, current_ts: datetime,
                                      all_txns: pd.DataFrame, idx: int) -> float:
        """Number of downstream hops within a time window."""
        window = timedelta(hours=config.VELOCITY_WINDOW_HOURS)
        start_ts = current_ts
        end_ts = current_ts + window

        # Look at transactions from this account in the window
        hist = self.account_history.get(account_id, [])
        outflows = [h for h in hist
                    if h["direction"] == "out"
                    and start_ts <= h["timestamp"] <= end_ts]
        return float(len(outflows))

    def _compute_beneficiary_expansion(self, sender: str, receiver: str,
                                        current_ts: datetime) -> float:
        """Rate of new unique beneficiaries in recent window."""
        hist = self.account_history.get(sender, [])
        window = timedelta(days=config.EXPANSION_WINDOW_DAYS)
        recent_recipients = set()
        older_recipients = set()

        for h in hist:
            if h["direction"] == "out":
                if current_ts - window <= h["timestamp"] <= current_ts:
                    recent_recipients.add(h["counterparty"])
                elif h["timestamp"] < current_ts - window:
                    older_recipients.add(h["counterparty"])

        if not older_recipients:
            return len(recent_recipients)
        new_count = len(recent_recipients - older_recipients)
        return new_count / max(len(older_recipients), 1)

    def _compute_cascade_score(self, receiver: str, current_ts: datetime,
                                all_txns: pd.DataFrame, idx: int) -> float:
        """How quickly does the receiver redistribute after receiving?"""
        hist = self.account_history.get(receiver, [])
        window = timedelta(hours=config.RETENTION_TIME_WINDOW_HOURS)

        outflows_after = [h for h in hist
                          if h["direction"] == "out"
                          and current_ts <= h["timestamp"] <= current_ts + window]
        return min(float(len(outflows_after)), 20.0)

    def _compute_tx_velocity(self, account_id: str, current_ts: datetime) -> float:
        """Transactions per hour in recent window."""
        hist = self.account_history.get(account_id, [])
        window = timedelta(hours=config.VELOCITY_WINDOW_HOURS)

        recent = len([h for h in hist
                      if h["direction"] == "out"
                      and current_ts - window <= h["timestamp"] <= current_ts])
        return recent / max(config.VELOCITY_WINDOW_HOURS, 1)

    def _compute_structuring_indicator(self, sender: str, amount: float,
                                        current_ts: datetime) -> float:
        """Detect repeated near-threshold amounts."""
        threshold = config.FRAUD_CONFIG["structuring"]["threshold"]
        margin = threshold * 0.2  # Within 20% of threshold

        if amount < threshold - margin or amount > threshold:
            return 0.0

        # Check if sender has other near-threshold txns recently
        hist = self.account_history.get(sender, [])
        window = timedelta(days=7)
        near_threshold = [h for h in hist
                          if h["direction"] == "out"
                          and current_ts - window <= h["timestamp"] <= current_ts
                          and threshold - margin <= h["amount"] < threshold]
        return min(float(len(near_threshold)), 10.0)
