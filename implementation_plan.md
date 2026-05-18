# GraphGuard v2 — Fraud Intelligence Platform PoC

Build a **competition-ready Proof of Concept** for PS3: Tracking of Funds within Bank for Fraud Detection — a real-time temporal fund-flow intelligence platform detecting suspicious liquidity propagation across banking networks.

## User Review Required

> [!IMPORTANT]
> **Neo4j Dependency Decision**: The guide mentions Neo4j for the graph database. For a laptop-demo PoC, I recommend using **NetworkX only** (pure Python, zero infrastructure) for graph analytics and **vis.js** for frontend graph visualization. This eliminates the need to install/configure Neo4j. If you want Neo4j, please confirm you have it installed and provide connection details.

> [!IMPORTANT]
> **LLM for STR Narratives**: The investigation layer calls for LLM-generated STR summaries. I plan to use **structured Jinja2 templates** for deterministic output, with an *optional* OpenAI/Gemini API call if you provide a key. This keeps the demo stable without requiring an API key. Please confirm if you have an LLM API key you'd like to use.

> [!WARNING]
> **Estimated Build Size**: This is a ~3000-4000 line codebase across 7 phases. I'll build it module-by-module in order. Expect the full build to take significant time.

## Open Questions

1. **LLM API Key**: Do you have an OpenAI or Gemini API key for the STR narrative generation, or should I use template-only generation?
2. **Neo4j**: Should I stick with NetworkX-only (recommended for PoC simplicity) or do you have Neo4j installed?
3. **Demo Data Scale**: I plan for ~5,000 accounts and ~50,000 transactions with 5 fraud campaigns injected. Is this scale appropriate?

---

## Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Backend API** | FastAPI + WebSocket | Async, real-time streaming, Python-native |
| **Data Generator** | Python (Faker, NumPy, Pandas) | Synthetic banking ecosystem |
| **Edge Model** | XGBoost | Fast, interpretable tabular scoring |
| **Graph Engine** | NetworkX | Zero-infra, cycle/community detection |
| **Temporal Layer** | Custom Python module | Lightweight temporal feature scoring |
| **Frontend** | Vanilla HTML/CSS/JS + vis.js | Premium dashboard, graph visualization |
| **Investigation** | Jinja2 templates (+ optional LLM) | Deterministic STR narrative generation |

---

## Proposed Changes

### Phase 1 — Project Structure & Data Ecosystem

Set up the monorepo structure and build the synthetic financial ecosystem generator.

#### [NEW] [requirements.txt](file:///c:/Users/sriva/OneDrive/Documents/Desktop/GraphGuardv2/requirements.txt)
- All Python dependencies: `fastapi`, `uvicorn`, `xgboost`, `scikit-learn`, `networkx`, `pandas`, `numpy`, `faker`, `jinja2`, `websockets`, `python-multipart`

#### [NEW] [config.py](file:///c:/Users/sriva/OneDrive/Documents/Desktop/GraphGuardv2/config.py)
- Central configuration: paths, model params, thresholds, feature weights

#### [NEW] [data/generator.py](file:///c:/Users/sriva/OneDrive/Documents/Desktop/GraphGuardv2/data/generator.py)
- `BankingEcosystemGenerator` class:
  - Generate ~5,000 accounts with profiles (salary, merchant, household, dormant)
  - Simulate normal transaction patterns (salary flows, merchant payments, recurring transfers, household transfers)
  - Branch-local communities, geographic locality
  - ~45,000 legitimate transactions over a 90-day window

#### [NEW] [data/fraud_injector.py](file:///c:/Users/sriva/OneDrive/Documents/Desktop/GraphGuardv2/data/fraud_injector.py)
- `FraudCampaignInjector` class implementing 5 fraud campaigns:
  - **Circular Laundering** (A→B→C→A with temporal consistency)
  - **Layering** (multi-hop chains in short windows)
  - **Dormant Mule Activation** (dormant account receives & rapidly redistributes)
  - **Structuring** (repeated sub-threshold transfers)
  - **Hub-and-Spoke Mule Network** (central node → many recipients)
- Gradual fraud evolution, not sudden jumps
- Labels stored per-transaction and per-account

#### [NEW] [data/__init__.py](file:///c:/Users/sriva/OneDrive/Documents/Desktop/GraphGuardv2/data/__init__.py)

---

### Phase 2 — Feature Extraction & Edge Intelligence

Build the feature engineering pipeline and XGBoost edge risk scorer.

#### [NEW] [engine/features.py](file:///c:/Users/sriva/OneDrive/Documents/Desktop/GraphGuardv2/engine/features.py)
- `FeatureExtractor` class computing per-transaction features:
  - `retention_time` — how long funds sit before outflow
  - `propagation_velocity` — speed of fund movement through chains
  - `burst_ratio` — ratio of current activity to historical baseline
  - `temporal_hop_density` — number of hops within a time window
  - `beneficiary_expansion_rate` — rate of new unique recipients
  - `cascade_score` — downstream redistribution intensity
  - `dormant_activation` — flag for reactivated dormant accounts
  - `beneficiary_novelty` — fraction of first-time recipients
  - `transaction_velocity` — transactions per unit time
  - `amount_deviation` — deviation from sender's normal behavior
  - `time_anomaly` — unusual hour/day patterns
  - `structuring_indicator` — repeated near-threshold amounts

#### [NEW] [engine/edge_model.py](file:///c:/Users/sriva/OneDrive/Documents/Desktop/GraphGuardv2/engine/edge_model.py)
- `EdgeRiskEngine` class:
  - Train XGBoost on labeled synthetic data
  - Output per-transaction risk score [0, 1]
  - Feature importance extraction for explainability
  - `score_transaction()` method for real-time inference
  - Model save/load for demo stability

#### [NEW] [engine/__init__.py](file:///c:/Users/sriva/OneDrive/Documents/Desktop/GraphGuardv2/engine/__init__.py)

---

### Phase 3 — Graph Intelligence

Build the transaction graph and suspicious pattern detection.

#### [NEW] [engine/graph_engine.py](file:///c:/Users/sriva/OneDrive/Documents/Desktop/GraphGuardv2/engine/graph_engine.py)
- `GraphIntelligenceEngine` class using NetworkX:
  - Build directed multi-graph from transactions
  - **Circular flow detection**: `nx.simple_cycles()` with temporal consistency filtering
  - **Layering detection**: multi-hop path analysis within short time windows
  - **Mule hub detection**: degree centrality + betweenness centrality analysis
  - **Temporal burst path detection**: rapid sequential transfers through paths
  - **Community detection**: Louvain-style community identification
  - Per-account graph risk score combining all signals
  - `get_suspicious_subgraph(account_id, hops=2)` for ego-graph extraction
  - Subgraph serialization for frontend vis.js rendering

---

### Phase 4 — Temporal Intelligence Layer

Lightweight temporal reasoning module.

#### [NEW] [engine/temporal_engine.py](file:///c:/Users/sriva/OneDrive/Documents/Desktop/GraphGuardv2/engine/temporal_engine.py)
- `TemporalIntelligenceEngine` class:
  - Propagation speed analysis across transaction chains
  - Retention time profiling per account
  - Temporal hop density computation (hops per hour in a path)
  - Beneficiary expansion rate over sliding windows
  - Burst redistribution detection
  - Per-account temporal risk score
  - Temporal evolution timeline for investigation display

---

### Phase 5 — Risk Fusion

Combine all intelligence signals.

#### [NEW] [engine/risk_fusion.py](file:///c:/Users/sriva/OneDrive/Documents/Desktop/GraphGuardv2/engine/risk_fusion.py)
- `RiskFusionEngine` class:
  - `final_risk = 0.4 * edge_score + 0.4 * graph_score + 0.2 * temporal_score`
  - Alert generation with severity levels (LOW, MEDIUM, HIGH, CRITICAL)
  - Top-N suspicious accounts ranking
  - Evidence aggregation per alert (which patterns triggered, scores, key transactions)
  - Deterministic and explainable output

---

### Phase 6 — Investigation & STR Output

Generate human-readable investigation intelligence.

#### [NEW] [engine/investigation.py](file:///c:/Users/sriva/OneDrive/Documents/Desktop/GraphGuardv2/engine/investigation.py)
- `InvestigationEngine` class:
  - Structured evidence formatting (detected patterns, scores, paths, timelines)
  - Jinja2 template-based STR narrative generation
  - Investigation summary with:
    - Subject account details
    - Detected fraud patterns
    - Risk score breakdown
    - Key suspicious transactions
    - Temporal behavior analysis
    - Recommended actions
  - Optional LLM-enhanced narrative (if API key provided)

#### [NEW] [engine/templates/str_report.j2](file:///c:/Users/sriva/OneDrive/Documents/Desktop/GraphGuardv2/engine/templates/str_report.j2)
- STR-style narrative template

#### [NEW] [engine/templates/investigation_summary.j2](file:///c:/Users/sriva/OneDrive/Documents/Desktop/GraphGuardv2/engine/templates/investigation_summary.j2)
- Investigation panel summary template

---

### Phase 7 — Backend API & Frontend Dashboard

#### [NEW] [main.py](file:///c:/Users/sriva/OneDrive/Documents/Desktop/GraphGuardv2/main.py)
- FastAPI application with:
  - `GET /` — Serve dashboard
  - `GET /api/alerts` — Current risk alerts
  - `GET /api/accounts/{id}` — Account details + risk breakdown
  - `GET /api/graph/{account_id}` — Suspicious subgraph (2-hop ego-graph)
  - `GET /api/investigation/{account_id}` — Investigation summary + STR
  - `GET /api/transactions/feed` — Recent transaction feed
  - `GET /api/stats` — Dashboard statistics
  - `WebSocket /ws/live` — Real-time transaction stream + alerts
  - `POST /api/demo/scenario/{name}` — Trigger demo scenario replay

#### [NEW] [frontend/index.html](file:///c:/Users/sriva/OneDrive/Documents/Desktop/GraphGuardv2/frontend/index.html)
- Single-page dashboard with:
  - **Header**: GraphGuard branding, system status, live stats
  - **Left Panel**: Live transaction feed (scrolling, color-coded by risk)
  - **Center Panel**: Suspicious subgraph visualization (vis.js)
  - **Right Panel**: Risk alerts list (sortable, clickable)
  - **Bottom Panel**: Investigation panel (slides up on alert click)
  - Dark theme, glassmorphism, micro-animations
  - WebSocket connection for real-time updates

#### [NEW] [frontend/styles.css](file:///c:/Users/sriva/OneDrive/Documents/Desktop/GraphGuardv2/frontend/styles.css)
- Premium dark theme with:
  - CSS custom properties design system
  - Glassmorphism cards
  - Gradient accents (teal/cyan/violet palette)
  - Smooth transitions and micro-animations
  - Responsive grid layout
  - Pulsing alert indicators
  - Risk-level color coding

#### [NEW] [frontend/app.js](file:///c:/Users/sriva/OneDrive/Documents/Desktop/GraphGuardv2/frontend/app.js)
- Dashboard logic:
  - WebSocket connection management
  - vis.js graph rendering with force-directed layout
  - Alert list with click-to-investigate
  - Transaction feed auto-scroll
  - Investigation panel with STR display
  - Demo scenario buttons
  - Stats counters with animation

---

## Project Structure

```
GraphGuardv2/
├── config.py                    # Central configuration
├── main.py                      # FastAPI application entry
├── requirements.txt             # Python dependencies
├── data/
│   ├── __init__.py
│   ├── generator.py             # Synthetic banking ecosystem
│   └── fraud_injector.py        # Fraud campaign injection
├── engine/
│   ├── __init__.py
│   ├── features.py              # Feature extraction
│   ├── edge_model.py            # XGBoost edge risk scoring
│   ├── graph_engine.py          # NetworkX graph analytics
│   ├── temporal_engine.py       # Temporal intelligence
│   ├── risk_fusion.py           # Score fusion + alerts
│   ├── investigation.py         # STR + investigation output
│   └── templates/
│       ├── str_report.j2        # STR narrative template
│       └── investigation_summary.j2
└── frontend/
    ├── index.html               # Dashboard SPA
    ├── styles.css               # Premium dark theme
    └── app.js                   # Dashboard logic + vis.js
```

---

## Verification Plan

### Automated Tests
1. Run `python -c "from data.generator import BankingEcosystemGenerator; g = BankingEcosystemGenerator(); data = g.generate(); print(f'Accounts: {len(data[\"accounts\"])}, Txns: {len(data[\"transactions\"])}')"` — verify data generation
2. Run `python -c "from engine.edge_model import EdgeRiskEngine; print('Edge model OK')"` — verify model loads
3. Start server with `uvicorn main:app --reload` and verify all API endpoints return valid JSON
4. Open dashboard in browser and verify:
   - Transaction feed populates
   - Alerts appear with risk scores
   - Clicking an alert shows suspicious subgraph
   - Investigation panel displays STR narrative

### Demo Scenario Verification
- **Scenario 1 — Dormant Mule Activation**: Trigger via API, verify dormant account alert with rapid redistribution visible in graph
- **Scenario 2 — Circular Laundering**: Verify A→B→C→A cycle highlighted in graph with timestamps
- **Scenario 3 — Layering Cascade**: Verify multi-hop chain visible with temporal propagation

### Manual Verification
- Dashboard aesthetics check: dark theme, animations, glassmorphism
- Graph interaction: zoom, pan, node hover showing details
- End-to-end flow: transaction → scoring → alert → graph → investigation → STR
