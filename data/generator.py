"""
GraphGuard v2 — Synthetic Banking Ecosystem Generator
Generates realistic banking transaction data with account profiles,
branch communities, and normal behavioral patterns.
"""

import uuid
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from faker import Faker
from typing import Dict, List, Tuple

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

fake = Faker("en_IN")
Faker.seed(42)
random.seed(42)
np.random.seed(42)


class BankingEcosystemGenerator:
    """
    Generates a synthetic banking ecosystem with realistic account profiles,
    branch-local communities, and normal transaction patterns.
    """

    def __init__(self):
        self.accounts: List[Dict] = []
        self.transactions: List[Dict] = []
        self.start_date = datetime(2025, 1, 1)
        self.end_date = self.start_date + timedelta(days=config.SIMULATION_DAYS)

    def generate(self) -> Dict:
        """Generate complete banking ecosystem."""
        print("[DataGen] Generating banking ecosystem...")
        self._generate_accounts()
        self._generate_transactions()
        accounts_df = pd.DataFrame(self.accounts)
        transactions_df = pd.DataFrame(self.transactions)
        print(f"[DataGen] Created {len(accounts_df)} accounts, {len(transactions_df)} transactions")
        return {
            "accounts": accounts_df,
            "transactions": transactions_df,
        }

    # ── Account Generation ───────────────────────────────────────────────

    def _generate_accounts(self):
        """Generate accounts with realistic profiles across branches."""
        print(f"[DataGen] Generating {config.NUM_ACCOUNTS} accounts...")
        account_id = 1000000

        for acc_type, fraction in config.ACCOUNT_TYPES.items():
            count = int(config.NUM_ACCOUNTS * fraction)
            for _ in range(count):
                account_id += 1
                branch = random.choice(config.BRANCHES)
                profile = self._build_account_profile(account_id, acc_type, branch)
                self.accounts.append(profile)

        # Fill remaining to reach exact count
        while len(self.accounts) < config.NUM_ACCOUNTS:
            account_id += 1
            acc_type = random.choice(list(config.ACCOUNT_TYPES.keys()))
            branch = random.choice(config.BRANCHES)
            self.accounts.append(self._build_account_profile(account_id, acc_type, branch))

        random.shuffle(self.accounts)

    def _build_account_profile(self, account_id: int, acc_type: str, branch: str) -> Dict:
        """Build a single account profile with behavioral baselines."""
        if acc_type == "salary":
            avg_balance = random.uniform(20000, 200000)
            monthly_income = random.uniform(25000, 150000)
            tx_frequency = random.uniform(8, 25)  # txns per month
            avg_tx_amount = random.uniform(1000, 15000)
        elif acc_type == "merchant":
            avg_balance = random.uniform(100000, 2000000)
            monthly_income = random.uniform(50000, 500000)
            tx_frequency = random.uniform(30, 200)
            avg_tx_amount = random.uniform(500, 50000)
        elif acc_type == "household":
            avg_balance = random.uniform(10000, 100000)
            monthly_income = random.uniform(15000, 80000)
            tx_frequency = random.uniform(5, 15)
            avg_tx_amount = random.uniform(500, 10000)
        elif acc_type == "savings":
            avg_balance = random.uniform(50000, 500000)
            monthly_income = random.uniform(5000, 30000)
            tx_frequency = random.uniform(2, 8)
            avg_tx_amount = random.uniform(5000, 50000)
        else:  # dormant
            avg_balance = random.uniform(1000, 50000)
            monthly_income = 0
            tx_frequency = random.uniform(0, 1)
            avg_tx_amount = random.uniform(100, 5000)

        # Opening date — older accounts are more common
        days_ago = random.randint(180, 3650)
        open_date = self.start_date - timedelta(days=days_ago)

        return {
            "account_id": f"ACC{account_id}",
            "holder_name": fake.name(),
            "account_type": acc_type,
            "branch": branch,
            "city": branch.split("-")[0],
            "open_date": open_date.isoformat(),
            "avg_balance": round(avg_balance, 2),
            "monthly_income": round(monthly_income, 2),
            "avg_tx_frequency": round(tx_frequency, 1),
            "avg_tx_amount": round(avg_tx_amount, 2),
            "is_dormant": acc_type == "dormant",
            "is_fraud": False,             # Will be set by fraud injector
            "fraud_campaign": None,
            "risk_label": 0,
        }

    # ── Transaction Generation ───────────────────────────────────────────

    def _generate_transactions(self):
        """Generate normal transaction patterns."""
        print(f"[DataGen] Generating ~{config.NUM_LEGIT_TRANSACTIONS} legitimate transactions...")
        acc_df = pd.DataFrame(self.accounts)

        # Build branch-local communities (accounts prefer same-branch transfers)
        branch_accounts = {}
        for branch in config.BRANCHES:
            branch_accounts[branch] = acc_df[acc_df["branch"] == branch]["account_id"].tolist()

        non_dormant = acc_df[acc_df["account_type"] != "dormant"]["account_id"].tolist()
        all_ids = acc_df["account_id"].tolist()

        txn_count = 0
        target = config.NUM_LEGIT_TRANSACTIONS

        # Distribute across simulation days
        for day_offset in range(config.SIMULATION_DAYS):
            current_date = self.start_date + timedelta(days=day_offset)
            is_weekend = current_date.weekday() >= 5
            daily_target = int(target / config.SIMULATION_DAYS)
            if is_weekend:
                daily_target = int(daily_target * 0.4)  # Less activity on weekends

            for _ in range(daily_target):
                if txn_count >= target:
                    break

                sender_id = random.choice(non_dormant)
                sender = acc_df[acc_df["account_id"] == sender_id].iloc[0]
                txn = self._generate_single_transaction(
                    sender, current_date, branch_accounts, all_ids, acc_df
                )
                if txn:
                    self.transactions.append(txn)
                    txn_count += 1

        print(f"[DataGen] Generated {txn_count} legitimate transactions")

    def _generate_single_transaction(
        self, sender: pd.Series, base_date: datetime,
        branch_accounts: Dict, all_ids: List[str], acc_df: pd.DataFrame
    ) -> Dict:
        """Generate a single realistic transaction."""
        sender_id = sender["account_id"]
        acc_type = sender["account_type"]

        # Choose receiver — 70% same branch, 30% cross-branch
        sender_branch = sender["branch"]
        if random.random() < 0.7 and len(branch_accounts.get(sender_branch, [])) > 1:
            candidates = [a for a in branch_accounts[sender_branch] if a != sender_id]
            if not candidates:
                candidates = [a for a in all_ids if a != sender_id]
        else:
            candidates = [a for a in all_ids if a != sender_id]

        receiver_id = random.choice(candidates)

        # Amount based on account type behavior
        avg = sender["avg_tx_amount"]
        std = avg * 0.4
        amount = max(100, np.random.normal(avg, std))

        # Transaction type
        if acc_type == "salary" and base_date.day <= 5:
            tx_type = "salary_credit"
            amount = sender["monthly_income"] * random.uniform(0.95, 1.05)
        elif acc_type == "merchant":
            tx_type = random.choice(["payment", "settlement", "refund"])
        elif acc_type == "household":
            tx_type = random.choice(["utility", "transfer", "purchase"])
        else:
            tx_type = random.choice(["transfer", "payment", "withdrawal"])

        # Time of day — business hours weighted
        if random.random() < 0.75:
            hour = random.randint(9, 18)
        else:
            hour = random.randint(0, 23)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)

        timestamp = base_date.replace(hour=hour, minute=minute, second=second)

        return {
            "tx_id": f"TX{uuid.uuid4().hex[:12].upper()}",
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "amount": round(amount, 2),
            "currency": "INR",
            "timestamp": timestamp.isoformat(),
            "tx_type": tx_type,
            "channel": random.choice(["NEFT", "RTGS", "UPI", "IMPS"]),
            "is_fraud": False,
            "fraud_type": None,
            "fraud_campaign_id": None,
        }


if __name__ == "__main__":
    gen = BankingEcosystemGenerator()
    data = gen.generate()
    print(f"\nAccounts shape: {data['accounts'].shape}")
    print(f"Transactions shape: {data['transactions'].shape}")
    print(f"\nAccount types:\n{data['accounts']['account_type'].value_counts()}")
    print(f"\nBranches:\n{data['accounts']['branch'].value_counts()}")
    print(f"\nTransaction types:\n{data['transactions']['tx_type'].value_counts()}")
