"""
GraphGuard v2 — Edge Risk Engine (XGBoost)
Transaction-level risk scoring with explainable feature importance.
"""

import os, sys, pickle
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score, average_precision_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class EdgeRiskEngine:
    """XGBoost-based transaction-level risk scorer with explainability."""

    def __init__(self):
        self.model: Optional[XGBClassifier] = None
        self.feature_names = config.EDGE_FEATURES
        self.feature_importance: Dict[str, float] = {}
        self.model_path = config.MODEL_DIR / "edge_model.pkl"
        self.metrics: Dict = {}

    def train(self, features_df: pd.DataFrame, labels: pd.Series):
        """Train the XGBoost edge risk model."""
        print("[EdgeModel] Training XGBoost edge risk model...")
        X = features_df[self.feature_names].values
        y = labels.values
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        self.model = XGBClassifier(**config.XGBOOST_PARAMS)
        self.model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

        y_pred_proba = self.model.predict_proba(X_test)[:, 1]
        y_pred = (y_pred_proba >= 0.5).astype(int)
        auc_roc = roc_auc_score(y_test, y_pred_proba)
        ap_score = average_precision_score(y_test, y_pred_proba)
        report = classification_report(y_test, y_pred, output_dict=True)
        self.metrics = {
            "auc_roc": round(auc_roc, 4), "avg_precision": round(ap_score, 4),
            "precision": round(report.get("1", {}).get("precision", 0), 4),
            "recall": round(report.get("1", {}).get("recall", 0), 4),
            "f1": round(report.get("1", {}).get("f1-score", 0), 4),
        }
        importances = self.model.feature_importances_
        self.feature_importance = {
            name: round(float(imp), 4)
            for name, imp in sorted(zip(self.feature_names, importances), key=lambda x: x[1], reverse=True)
        }
        print(f"[EdgeModel] AUC-ROC: {self.metrics['auc_roc']}, Recall: {self.metrics['recall']}")
        print(f"[EdgeModel] Top features: {list(self.feature_importance.keys())[:5]}")
        self.save()

    def score_batch(self, features_df: pd.DataFrame) -> np.ndarray:
        if self.model is None: self.load()
        X = features_df[self.feature_names].values
        return self.model.predict_proba(X)[:, 1]

    def score_single(self, features: Dict) -> float:
        if self.model is None: self.load()
        X = np.array([[features.get(f, 0) for f in self.feature_names]])
        return float(self.model.predict_proba(X)[0, 1])

    def explain(self, features: Dict) -> List[Tuple[str, float, float]]:
        """Return top contributing features for a prediction."""
        explanations = []
        for name in self.feature_names:
            val = features.get(name, 0)
            imp = self.feature_importance.get(name, 0)
            if imp > 0.01:
                explanations.append((name, val, imp))
        explanations.sort(key=lambda x: x[2], reverse=True)
        return explanations[:8]

    def save(self):
        config.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.model_path, "wb") as f:
            pickle.dump({"model": self.model, "feature_importance": self.feature_importance, "metrics": self.metrics}, f)
        print(f"[EdgeModel] Model saved to {self.model_path}")

    def load(self):
        if self.model_path.exists():
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
                self.model = data["model"]
                self.feature_importance = data["feature_importance"]
                self.metrics = data["metrics"]
            print(f"[EdgeModel] Model loaded")
        else:
            print(f"[EdgeModel] No saved model found")

    def get_metrics(self) -> Dict: return self.metrics
    def get_feature_importance(self) -> Dict[str, float]: return self.feature_importance
