"""
GraphGuard v2 — Fraud Campaign Injector
Injects 5 types of realistic fraud campaigns into the synthetic ecosystem.
Fraud evolves gradually with temporal consistency.
"""

import uuid
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

random.seed(42)
np.random.seed(42)


class FraudCampaignInjector:
    """
    Injects fraud campaigns into a clean banking ecosystem.
    Each campaign evolves gradually with temporal consistency.
    """

    def __init__(self):
        self.campaign_counter = 0
        self.fraud_accounts = set()
        self.fraud_transactions = []

    def inject(self, accounts_df: pd.DataFrame, transactions_df: pd.DataFrame) -> Dict:
        """Inject all fraud campaigns and return augmented data."""
        print("[FraudInjector] Injecting fraud campaigns...")

        accounts = accounts_df.copy()
        all_txns = list(transactions_df.to_dict("records"))

        # Get dormant accounts for mule activation
        dormant_ids = accounts[accounts["account_type"] == "dormant"]["account_id"].tolist()
        non_dormant_ids = accounts[accounts["account_type"] != "dormant"]["account_id"].tolist()
        all_ids = accounts["account_id"].tolist()

        start_date = datetime(2025, 1, 15)  # Fraud starts after 2 weeks of normal

        # ── Campaign A: Circular Laundering ──────────────────────────────
        cfg = config.FRAUD_CONFIG["circular_laundering"]
        for i in range(cfg["num_campaigns"]):
            cycle_len = cfg["cycle_lengths"][i % len(cfg["cycle_lengths"])]
            ring = random.sample(non_dormant_ids, cycle_len)
            campaign_id = self._next_campaign_id("CIRCULAR")
            campaign_start = start_date + timedelta(days=random.randint(5, 60))

            for round_num in range(cfg["rounds"]):
                round_start = campaign_start + timedelta(days=round_num * random.randint(3, 7))
                base_amount = random.uniform(*cfg["amount_range"])
                # Amount varies slightly each hop to simulate fees/splitting
                for hop in range(cycle_len):
                    sender = ring[hop]
                    receiver = ring[(hop + 1) % cycle_len]
                    amount = base_amount * random.uniform(0.92, 1.0)
                    ts = round_start + timedelta(hours=hop * random.uniform(1, 8))

                    txn = self._make_fraud_txn(
                        sender, receiver, amount, ts,
                        "circular_laundering", campaign_id
                    )
                    all_txns.append(txn)
                    self.fraud_accounts.update([sender, receiver])

            self._mark_accounts(accounts, ring, "circular_laundering", campaign_id)
            print(f"  [CIRCULAR] Campaign {campaign_id}: {cycle_len}-node ring, {cfg['rounds']} rounds")

        # ── Campaign B: Layering ─────────────────────────────────────────
        cfg = config.FRAUD_CONFIG["layering"]
        for i in range(cfg["num_campaigns"]):
            chain_len = random.randint(*cfg["chain_length_range"])
            chain = random.sample(non_dormant_ids, chain_len)
            campaign_id = self._next_campaign_id("LAYERING")
            campaign_start = start_date + timedelta(days=random.randint(10, 70))

            # Multiple waves
            for wave in range(3):
                wave_start = campaign_start + timedelta(days=wave * random.randint(5, 14))
                initial_amount = random.uniform(*cfg["amount_range"])
                current_amount = initial_amount

                for hop in range(chain_len - 1):
                    sender = chain[hop]
                    receiver = chain[hop + 1]
                    # Amount decreases through layers (skimming)
                    skim = random.uniform(0.02, 0.08)
                    current_amount *= (1 - skim)
                    ts = wave_start + timedelta(
                        hours=hop * random.uniform(0.5, cfg["time_window_hours"] / chain_len)
                    )

                    txn = self._make_fraud_txn(
                        sender, receiver, current_amount, ts,
                        "layering", campaign_id
                    )
                    all_txns.append(txn)
                    self.fraud_accounts.update([sender, receiver])

            self._mark_accounts(accounts, chain, "layering", campaign_id)
            print(f"  [LAYERING] Campaign {campaign_id}: {chain_len}-hop chain, 3 waves")

        # ── Campaign C: Dormant Mule Activation ──────────────────────────
        cfg = config.FRAUD_CONFIG["dormant_mule_activation"]
        for i in range(min(cfg["num_campaigns"], len(dormant_ids))):
            mule_id = dormant_ids[i]
            campaign_id = self._next_campaign_id("DORMANT_MULE")
            campaign_start = start_date + timedelta(days=random.randint(20, 70))

            # Large inflow from a "source" account
            source = random.choice(non_dormant_ids)
            inflow_amount = random.uniform(*cfg["inflow_amount_range"])

            txn = self._make_fraud_txn(
                source, mule_id, inflow_amount,
                campaign_start, "dormant_mule_activation", campaign_id
            )
            all_txns.append(txn)

            # Rapid redistribution to multiple accounts
            redist_count = random.randint(*cfg["redistribution_count"])
            recipients = random.sample(
                [a for a in non_dormant_ids if a != source], redist_count
            )
            remaining = inflow_amount
            for j, recipient in enumerate(recipients):
                if j == len(recipients) - 1:
                    amount = remaining  # Last one gets the rest
                else:
                    amount = inflow_amount / redist_count * random.uniform(0.7, 1.3)
                    remaining -= amount

                ts = campaign_start + timedelta(
                    hours=random.uniform(1, cfg["activation_window_hours"])
                )
                txn = self._make_fraud_txn(
                    mule_id, recipient, max(amount, 1000), ts,
                    "dormant_mule_activation", campaign_id
                )
                all_txns.append(txn)
                self.fraud_accounts.add(recipient)

            self.fraud_accounts.update([source, mule_id])
            self._mark_accounts(accounts, [mule_id, source] + recipients,
                              "dormant_mule_activation", campaign_id)
            print(f"  [DORMANT_MULE] Campaign {campaign_id}: mule={mule_id}, "
                  f"{redist_count} redistributions")

        # ── Campaign D: Structuring ──────────────────────────────────────
        cfg = config.FRAUD_CONFIG["structuring"]
        for i in range(cfg["num_campaigns"]):
            sender = random.choice(non_dormant_ids)
            receiver = random.choice([a for a in non_dormant_ids if a != sender])
            campaign_id = self._next_campaign_id("STRUCTURING")
            campaign_start = start_date + timedelta(days=random.randint(10, 75))

            num_txns = random.randint(*cfg["num_transactions"])
            for j in range(num_txns):
                amount = random.uniform(*cfg["amount_range"])
                ts = campaign_start + timedelta(
                    days=j * (cfg["time_window_days"] / num_txns),
                    hours=random.uniform(0, 12)
                )
                txn = self._make_fraud_txn(
                    sender, receiver, amount, ts,
                    "structuring", campaign_id
                )
                all_txns.append(txn)

            self.fraud_accounts.update([sender, receiver])
            self._mark_accounts(accounts, [sender, receiver], "structuring", campaign_id)
            print(f"  [STRUCTURING] Campaign {campaign_id}: {num_txns} sub-threshold txns")

        # ── Campaign E: Hub-and-Spoke Mule Network ───────────────────────
        cfg = config.FRAUD_CONFIG["hub_and_spoke"]
        for i in range(cfg["num_campaigns"]):
            hub = random.choice(non_dormant_ids)
            spoke_count = random.randint(*cfg["spoke_count_range"])
            spokes = random.sample(
                [a for a in all_ids if a != hub], spoke_count
            )
            campaign_id = self._next_campaign_id("HUB_SPOKE")
            campaign_start = start_date + timedelta(days=random.randint(15, 65))

            # First: multiple inflows to hub
            sources = random.sample(
                [a for a in non_dormant_ids if a != hub and a not in spokes], 
                min(3, len(non_dormant_ids) - spoke_count - 1)
            )
            for source in sources:
                amount = random.uniform(100000, 500000)
                ts = campaign_start + timedelta(hours=random.uniform(0, 12))
                txn = self._make_fraud_txn(
                    source, hub, amount, ts,
                    "hub_and_spoke", campaign_id
                )
                all_txns.append(txn)
                self.fraud_accounts.add(source)

            # Then: hub distributes to all spokes
            for spoke in spokes:
                amount = random.uniform(*cfg["amount_range"])
                ts = campaign_start + timedelta(
                    hours=random.uniform(12, cfg["time_window_hours"])
                )
                txn = self._make_fraud_txn(
                    hub, spoke, amount, ts,
                    "hub_and_spoke", campaign_id
                )
                all_txns.append(txn)

            self.fraud_accounts.update([hub] + spokes + sources)
            self._mark_accounts(accounts, [hub] + spokes, "hub_and_spoke", campaign_id)
            print(f"  [HUB_SPOKE] Campaign {campaign_id}: hub={hub}, {spoke_count} spokes")

        # ── Finalize ─────────────────────────────────────────────────────
        transactions = pd.DataFrame(all_txns)
        transactions = transactions.sort_values("timestamp").reset_index(drop=True)

        fraud_count = transactions["is_fraud"].sum()
        total = len(transactions)
        print(f"[FraudInjector] Done. {fraud_count} fraud txns / {total} total "
              f"({fraud_count/total*100:.1f}%)")
        print(f"[FraudInjector] {len(self.fraud_accounts)} accounts involved in fraud")

        return {
            "accounts": accounts,
            "transactions": transactions,
        }

    # ── Helpers ───────────────────────────────────────────────────────────

    def _next_campaign_id(self, prefix: str) -> str:
        self.campaign_counter += 1
        return f"{prefix}_{self.campaign_counter:03d}"

    def _make_fraud_txn(
        self, sender: str, receiver: str, amount: float,
        timestamp: datetime, fraud_type: str, campaign_id: str
    ) -> Dict:
        return {
            "tx_id": f"TX{uuid.uuid4().hex[:12].upper()}",
            "sender_id": sender,
            "receiver_id": receiver,
            "amount": round(amount, 2),
            "currency": "INR",
            "timestamp": timestamp.isoformat(),
            "tx_type": "transfer",
            "channel": random.choice(["NEFT", "RTGS", "IMPS"]),
            "is_fraud": True,
            "fraud_type": fraud_type,
            "fraud_campaign_id": campaign_id,
        }

    def _mark_accounts(self, accounts_df: pd.DataFrame, account_ids: List[str],
                       fraud_type: str, campaign_id: str):
        """Mark accounts as fraud-involved."""
        mask = accounts_df["account_id"].isin(account_ids)
        accounts_df.loc[mask, "is_fraud"] = True
        accounts_df.loc[mask, "fraud_campaign"] = campaign_id
        accounts_df.loc[mask, "risk_label"] = 1


if __name__ == "__main__":
    from generator import BankingEcosystemGenerator

    gen = BankingEcosystemGenerator()
    clean_data = gen.generate()

    injector = FraudCampaignInjector()
    data = injector.inject(clean_data["accounts"], clean_data["transactions"])

    print(f"\nFinal accounts: {len(data['accounts'])}")
    print(f"Final transactions: {len(data['transactions'])}")
    print(f"\nFraud types:\n{data['transactions'][data['transactions']['is_fraud']]['fraud_type'].value_counts()}")
