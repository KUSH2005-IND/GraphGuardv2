"""
GraphGuard v2 — FastAPI Application
Real-time fraud intelligence platform backend with WebSocket streaming.
"""

import os, sys, json, asyncio, random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import pandas as pd
import numpy as np

import config

class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/") and request.url.path != "/api/status":
            api_key = request.headers.get("X-API-Key")
            if api_key != config.API_KEY:
                return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"error": "Unauthorized API Key"})
        return await call_next(request)
from data.generator import BankingEcosystemGenerator
from data.fraud_injector import FraudCampaignInjector
from engine.features import FeatureExtractor
from engine.edge_model import EdgeRiskEngine
from engine.graph_engine import GraphIntelligenceEngine
from engine.temporal_engine import TemporalIntelligenceEngine
from engine.risk_fusion import RiskFusionEngine
from engine.investigation import InvestigationEngine

# ── Initialize app ───────────────────────────────────────────────────────
app = FastAPI(title="GraphGuard v2", description="Fraud Intelligence Platform")
app.add_middleware(APIKeyMiddleware)

# Global state
state = {
    "ready": False,
    "accounts_df": None,
    "transactions_df": None,
    "features_df": None,
    "feature_extractor": None,
    "edge_engine": None,
    "graph_engine": None,
    "temporal_engine": None,
    "fusion_engine": None,
    "investigation_engine": None,
    "edge_scores_per_account": {},
    "tx_index": 0,
}


class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket) -> bool:
        origin = ws.headers.get("origin")
        if origin and origin not in config.ALLOWED_ORIGINS:
            await ws.close(code=1008, reason="Origin not allowed")
            return False

        client_ip = ws.client.host if ws.client else "unknown"
        ip_connections = sum(1 for active_ws in self.active if active_ws.client and active_ws.client.host == client_ip)
        if ip_connections >= config.MAX_WS_CONNECTIONS_PER_IP:
            await ws.close(code=1008, reason="Too many connections")
            return False

        await ws.accept()
        self.active.append(ws)
        return True

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


# ── Startup: build entire pipeline ──────────────────────────────────────
@app.on_event("startup")
async def startup():
    print("\n" + "="*60)
    print("  GraphGuard v2 - Fraud Intelligence Platform")
    print("="*60 + "\n")

    # Phase 1: Data
    gen = BankingEcosystemGenerator()
    clean = gen.generate()
    injector = FraudCampaignInjector()
    data = injector.inject(clean["accounts"], clean["transactions"])

    state["accounts_df"] = data["accounts"]
    state["transactions_df"] = data["transactions"]

    # Phase 2: Features + Edge Model
    fe = FeatureExtractor()
    fe.fit(data["accounts"], data["transactions"])
    features_df = fe.extract(data["transactions"])
    state["features_df"] = features_df
    state["feature_extractor"] = fe

    edge_engine = EdgeRiskEngine()
    labels = data["transactions"]["is_fraud"].astype(int)
    edge_engine.train(features_df, labels)
    state["edge_engine"] = edge_engine

    # Score all transactions and aggregate per account
    edge_scores_raw = edge_engine.score_batch(features_df)
    txns = data["transactions"].copy()
    txns["edge_score"] = edge_scores_raw
    acct_edge = txns.groupby("sender_id")["edge_score"].mean().to_dict()
    recv_edge = txns.groupby("receiver_id")["edge_score"].mean().to_dict()
    combined = defaultdict(list)
    for aid, s in acct_edge.items():
        combined[aid].append(s)
    for aid, s in recv_edge.items():
        combined[aid].append(s)
    state["edge_scores_per_account"] = {
        aid: round(np.mean(scores), 4) for aid, scores in combined.items()
    }

    # Phase 3: Graph
    graph_engine = GraphIntelligenceEngine()
    graph_engine.build_graph(data["transactions"], data["accounts"])
    graph_engine.analyze()
    state["graph_engine"] = graph_engine

    # Phase 4: Temporal
    temporal_engine = TemporalIntelligenceEngine()
    temporal_engine.analyze(data["transactions"], data["accounts"])
    state["temporal_engine"] = temporal_engine

    # Phase 5: Risk Fusion
    fusion = RiskFusionEngine()
    
    # Build graph patterns dict for all accounts
    graph_patterns = {
        acc: graph_engine.get_patterns_for_account(acc)
        for acc in data["accounts"]["account_id"]
    }
    
    fusion.fuse(
        state["edge_scores_per_account"],
        graph_engine.account_graph_scores,
        temporal_engine.account_temporal_scores,
        graph_patterns=graph_patterns,
    )
    state["fusion_engine"] = fusion

    # Phase 6: Investigation
    state["investigation_engine"] = InvestigationEngine()

    state["ready"] = True
    print("\n" + "="*60)
    print("  [OK] Pipeline ready - open http://localhost:8000")
    print("="*60 + "\n")


# ── Static files ─────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(config.FRONTEND_DIR)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(config.FRONTEND_DIR / "index.html"))


# ── API Endpoints ────────────────────────────────────────────────────────
@app.get("/api/status")
async def status():
    return {"ready": state["ready"]}


@app.get("/api/stats")
async def stats():
    if not state["ready"]:
        return {"error": "not ready"}
    fusion = state["fusion_engine"]
    edge = state["edge_engine"]
    return {
        "total_accounts": len(state["accounts_df"]),
        "total_transactions": len(state["transactions_df"]),
        "fraud_transactions": int(state["transactions_df"]["is_fraud"].sum()),
        "model_metrics": edge.get_metrics(),
        "risk_stats": fusion.get_stats(),
        "feature_importance": dict(list(edge.get_feature_importance().items())[:10]),
    }


@app.get("/api/alerts")
async def alerts():
    if not state["ready"]:
        return []
    fusion = state["fusion_engine"]
    alerts_list = fusion.get_alerts()
    # Enrich with account info
    acc_df = state["accounts_df"]
    for alert in alerts_list:
        acc = acc_df[acc_df["account_id"] == alert["account_id"]]
        if len(acc) > 0:
            acc = acc.iloc[0]
            alert["holder_name"] = acc["holder_name"]
            alert["account_type"] = acc["account_type"]
            alert["branch"] = acc["branch"]
    return alerts_list


@app.get("/api/accounts/{account_id}")
async def account_detail(account_id: str):
    if not state["ready"]:
        raise HTTPException(404, "Not ready")
    acc_df = state["accounts_df"]
    acc = acc_df[acc_df["account_id"] == account_id]
    if len(acc) == 0:
        raise HTTPException(404, "Account not found")
    acc = acc.iloc[0].to_dict()
    score = state["fusion_engine"].get_score(account_id)
    return {"account": acc, "scores": score}


@app.get("/api/graph/{account_id}")
async def account_graph(account_id: str):
    if not state["ready"]:
        raise HTTPException(404, "Not ready")
    graph = state["graph_engine"]
    subgraph = graph.get_suspicious_subgraph(account_id, hops=config.SUBGRAPH_HOPS)
    return subgraph


@app.get("/api/graph/{account_id}/investigation")
async def account_graph_investigation(account_id: str):
    """Focused investigation-mode subgraph with suspicious path highlighting."""
    if not state["ready"]:
        raise HTTPException(404, "Not ready")
    graph = state["graph_engine"]
    return graph.get_suspicious_path_subgraph(account_id)


@app.get("/api/investigation/{account_id}")
async def investigation(account_id: str):
    if not state["ready"]:
        raise HTTPException(404, "Not ready")
    acc_df = state["accounts_df"]
    acc = acc_df[acc_df["account_id"] == account_id]
    if len(acc) == 0:
        raise HTTPException(404, "Account not found")
    acc_info = acc.iloc[0].to_dict()

    score = state["fusion_engine"].get_score(account_id) or {}
    patterns = state["graph_engine"].get_patterns_for_account(account_id)
    temporal = state["temporal_engine"].get_temporal_profile(account_id) or {}
    timeline = state["temporal_engine"].get_timeline(account_id)

    inv = state["investigation_engine"].generate_investigation(
        account_id, score, patterns, temporal, timeline, acc_info
    )
    return inv


@app.get("/api/transactions/feed")
async def transaction_feed():
    if not state["ready"]:
        return []
    txns = state["transactions_df"]
    features = state["features_df"]
    edge_scores = state["edge_engine"].score_batch(features)

    # Return latest 100 transactions with scores
    txns_copy = txns.tail(100).copy()
    txns_copy["edge_score"] = edge_scores[-100:]
    records = txns_copy.to_dict("records")
    return records


@app.get("/api/transactions/recent")
async def recent_transactions(limit: int = 50):
    """Get recent transactions sorted by timestamp."""
    if not state["ready"]:
        return []
    txns = state["transactions_df"].tail(limit)
    return txns.to_dict("records")


# ── WebSocket: live stream ──────────────────────────────────────────────
@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    connected = await manager.connect(ws)
    if not connected:
        return
    try:
        txns = state["transactions_df"]
        features = state["features_df"]
        edge_scores = state["edge_engine"].score_batch(features)

        idx = state["tx_index"]
        total = len(txns)

        while True:
            if idx >= total:
                idx = 0  # Loop

            tx = txns.iloc[idx].to_dict()
            score = float(edge_scores[idx]) if idx < len(edge_scores) else 0.0
            tx["edge_score"] = round(score, 4)
            tx["risk_pct"] = round(score * 100, 1)
            tx["index"] = idx

            await ws.send_json({"type": "transaction", "data": tx})

            # Also send alert updates periodically
            if idx % 50 == 0:
                fusion = state["fusion_engine"]
                await ws.send_json({
                    "type": "stats",
                    "data": {
                        "processed": idx,
                        "total": total,
                        "alerts": len(fusion.get_alerts()),
                        "risk_stats": fusion.get_stats(),
                    }
                })

            idx += 1
            state["tx_index"] = idx
            await asyncio.sleep(config.STREAM_INTERVAL_MS / 1000)

    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception as e:
        print(f"[WS] Error: {e}")
        manager.disconnect(ws)


# ── Entry point ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=False)
