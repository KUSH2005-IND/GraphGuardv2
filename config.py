"""
GraphGuard v2 — Central Configuration
All system parameters, thresholds, and weights in one place.
"""
import os
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "generated"
MODEL_DIR = BASE_DIR / "models"
TEMPLATE_DIR = BASE_DIR / "engine" / "templates"
FRONTEND_DIR = BASE_DIR / "frontend"

# Ensure dirs exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# ── Data Generation ──────────────────────────────────────────────────────────
NUM_ACCOUNTS = 500
NUM_LEGIT_TRANSACTIONS = 4500
SIMULATION_DAYS = 90
BRANCHES = ["Mumbai-HQ", "Delhi-North", "Bangalore-Tech", "Chennai-South",
            "Kolkata-East", "Hyderabad-Central", "Pune-West", "Ahmedabad-Gujarat"]

ACCOUNT_TYPES = {
    "salary": 0.35,       # Regular salary accounts
    "merchant": 0.15,     # Business/merchant accounts
    "household": 0.25,    # Household/personal accounts
    "savings": 0.15,      # Savings accounts
    "dormant": 0.10,      # Dormant/inactive accounts
}

# ── Fraud Campaigns ──────────────────────────────────────────────────────────
FRAUD_CONFIG = {
    "circular_laundering": {
        "num_campaigns": 3,
        "cycle_lengths": [3, 4, 5],
        "amount_range": (50000, 500000),
        "rounds": 4,
    },
    "layering": {
        "num_campaigns": 3,
        "chain_length_range": (4, 8),
        "amount_range": (100000, 1000000),
        "time_window_hours": 6,
    },
    "dormant_mule_activation": {
        "num_campaigns": 3,
        "inflow_amount_range": (500000, 2000000),
        "redistribution_count": (5, 12),
        "activation_window_hours": 24,
    },
    "structuring": {
        "num_campaigns": 4,
        "threshold": 50000,          # Reporting threshold
        "amount_range": (40000, 49999),
        "num_transactions": (8, 20),
        "time_window_days": 5,
    },
    "hub_and_spoke": {
        "num_campaigns": 3,
        "spoke_count_range": (6, 15),
        "amount_range": (20000, 100000),
        "time_window_hours": 48,
    },
}

# ── Feature Engineering ──────────────────────────────────────────────────────
RETENTION_TIME_WINDOW_HOURS = 24
BURST_BASELINE_DAYS = 14
VELOCITY_WINDOW_HOURS = 6
EXPANSION_WINDOW_DAYS = 7
CASCADE_MAX_HOPS = 3

# ── Edge Model (XGBoost) ────────────────────────────────────────────────────
XGBOOST_PARAMS = {
    "objective": "binary:logistic",
    "eval_metric": "aucpr",
    "max_depth": 6,
    "learning_rate": 0.1,
    "n_estimators": 200,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "scale_pos_weight": 10,     # Handle class imbalance
    "random_state": 42,
    "use_label_encoder": False,
}

EDGE_FEATURES = [
    "amount_log", "amount_deviation", "hour_of_day", "day_of_week",
    "is_weekend", "retention_time", "propagation_velocity", "burst_ratio",
    "temporal_hop_density", "beneficiary_expansion_rate", "cascade_score",
    "dormant_activation", "beneficiary_novelty", "transaction_velocity",
    "time_anomaly", "structuring_indicator", "sender_avg_amount",
    "sender_tx_count", "receiver_tx_count", "amount_to_avg_ratio",
]

# ── Graph Intelligence ───────────────────────────────────────────────────────
MAX_CYCLE_LENGTH = 6
CENTRALITY_THRESHOLD = 0.7      # Top 30% by centrality flagged
HUB_DEGREE_THRESHOLD = 10       # Min outgoing edges to flag as hub
COMMUNITY_MIN_SIZE = 3
SUBGRAPH_HOPS = 2                # Default ego-graph radius(=2)

# ── Temporal Intelligence ────────────────────────────────────────────────────
TEMPORAL_WINDOW_HOURS = 48
PROPAGATION_SPEED_THRESHOLD = 0.5   # Hours — faster = more suspicious
RETENTION_THRESHOLD_HOURS = 2       # Very short retention = suspicious
BURST_MULTIPLIER_THRESHOLD = 3.0    # 3x normal activity = burst

# ── Risk Fusion ──────────────────────────────────────────────────────────────
FUSION_WEIGHTS = {
    "edge": 0.4,
    "graph": 0.4,
    "temporal": 0.2,
}

ALERT_THRESHOLDS = {
    "CRITICAL": 0.50,
    "HIGH":     0.35,
    "MEDIUM":   0.20,
    "LOW":      0.10,
}

MAX_ALERTS = 50    # Top N alerts to surface

# ── Server ───────────────────────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 8000))
STREAM_INTERVAL_MS = 500     # Transaction stream speed for demo
API_KEY = os.environ.get("GG_API_KEY", "GG-SECRET-KEY-2026")
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,ws://localhost:8000,ws://127.0.0.1:8000").split(",")
MAX_WS_CONNECTIONS_PER_IP = 5
