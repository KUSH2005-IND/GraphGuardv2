"""
GraphGuard v2 — Graph Intelligence Engine (NetworkX)
Suspicious pattern detection: cycles, layering, mule hubs, temporal bursts.
"""

import os, sys
import numpy as np
import pandas as pd
import networkx as nx
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

try:
    # pyrefly: ignore [missing-import]
    import community as community_louvain
    HAS_LOUVAIN = True
except ImportError:
    HAS_LOUVAIN = False


class GraphIntelligenceEngine:
    """NetworkX-based graph analytics for fraud pattern detection."""

    def __init__(self):
        self.G = nx.MultiDiGraph()
        self.account_graph_scores: Dict[str, float] = {}
        self.detected_patterns: Dict[str, List] = {
            "cycles": [], "layering_chains": [],
            "mule_hubs": [], "temporal_bursts": [], "communities": [],
        }

    def build_graph(self, transactions_df: pd.DataFrame, accounts_df: pd.DataFrame):
        """Build transaction graph from data."""
        print("[GraphEngine] Building transaction graph...")
        self.G.clear()

        for _, acc in accounts_df.iterrows():
            self.G.add_node(acc["account_id"], **{
                "name": acc["holder_name"], "type": acc["account_type"],
                "branch": acc["branch"], "is_dormant": acc["is_dormant"],
            })

        txns = transactions_df.copy()
        txns["timestamp_dt"] = pd.to_datetime(txns["timestamp"], format="ISO8601")
        for _, tx in txns.iterrows():
            self.G.add_edge(tx["sender_id"], tx["receiver_id"],
                key=tx["tx_id"], amount=tx["amount"],
                timestamp=tx["timestamp_dt"], tx_id=tx["tx_id"],
                tx_type=tx.get("tx_type", "transfer"),
                is_fraud=tx.get("is_fraud", False),
            )
        print(f"[GraphEngine] Graph: {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges")

    def analyze(self) -> Dict[str, float]:
        """Run all graph analytics and compute per-account graph risk scores."""
        print("[GraphEngine] Running graph analytics...")
        simple_G = nx.DiGraph(self.G)

        self._detect_cycles(simple_G)
        self._detect_layering(simple_G)
        self._detect_mule_hubs(simple_G)
        self._detect_temporal_bursts()
        self._detect_communities(simple_G)
        self._compute_graph_scores(simple_G)

        flagged = sum(1 for s in self.account_graph_scores.values() if s > 0.3)
        print(f"[GraphEngine] Analysis complete. {flagged} accounts with elevated graph risk.")
        return self.account_graph_scores

    def _detect_cycles(self, G: nx.DiGraph):
        """Detect circular money flows with temporal consistency."""
        print("[GraphEngine]   Detecting cycles...")
        cycles = []
        try:
            for cycle in nx.simple_cycles(G, length_bound=config.MAX_CYCLE_LENGTH):
                if len(cycle) >= 3:
                    if self._is_temporally_consistent_cycle(cycle):
                        cycles.append(cycle)
                if len(cycles) >= 50:
                    break
        except Exception:
            pass
        self.detected_patterns["cycles"] = cycles
        print(f"[GraphEngine]   Found {len(cycles)} temporally-consistent cycles")

    def _is_temporally_consistent_cycle(self, cycle: List[str]) -> bool:
        """Check if cycle edges have increasing timestamps."""
        timestamps = []
        for i in range(len(cycle)):
            src, dst = cycle[i], cycle[(i + 1) % len(cycle)]
            edges = self.G.get_edge_data(src, dst)
            if not edges:
                return False
            latest = max(edges.values(), key=lambda e: e.get("timestamp", datetime.min))
            timestamps.append(latest.get("timestamp", datetime.min))
        for i in range(len(timestamps) - 1):
            if timestamps[i + 1] <= timestamps[i]:
                return False
        return True

    def _detect_layering(self, G: nx.DiGraph):
        """Detect multi-hop chains within short time windows — fast DFS version."""
        print("[GraphEngine]   Detecting layering chains...")
        chains = []

        # Only check top 30 nodes by out-degree — most likely layering sources
        high_out = sorted(
            G.nodes(), key=lambda n: G.out_degree(n), reverse=True
        )[:30]

        for source in high_out:
            if len(chains) >= 50:
                break

        # Bounded DFS — strict limits prevent combinatorial explosion
        stack = [[source]]
        paths_explored = 0

        while stack and len(chains) < 50 and paths_explored < 300:
            path = stack.pop()
            paths_explored += 1
            current = path[-1]

            # Chain is long enough to be suspicious
            if len(path) >= 4:
                if self._is_rapid_chain(path):
                    chains.append(list(path))
                continue  # Don't extend further

            # Hard depth limit
            if len(path) >= config.MAX_CYCLE_LENGTH:
                continue

            # Only check first 5 successors to bound branching factor
            for neighbor in list(G.successors(current))[:5]:
                if neighbor not in path:  # No revisiting nodes
                    stack.append(path + [neighbor])

        self.detected_patterns["layering_chains"] = chains
        print(f"[GraphEngine]   Found {len(chains)} layering chains")

    # def _detect_layering(self, G: nx.DiGraph):
    #     """Detect multi-hop chains within short time windows."""
    #     print("[GraphEngine]   Detecting layering chains...")
    #     chains = []
    #     high_out = [n for n, d in G.out_degree() if d >= 3]

    #     for source in high_out[:200]:
    #         for target in G.successors(source):
    #             try:
    #                 for path in nx.all_simple_paths(G, source, target, cutoff=config.MAX_CYCLE_LENGTH):
    #                     if len(path) >= 4:
    #                         if self._is_rapid_chain(path):
    #                             chains.append(path)
    #                     if len(chains) >= 50:
    #                         break
    #             except (nx.NetworkXError, nx.NodeNotFound):
    #                 pass
    #             if len(chains) >= 50:
    #                 break
    #         if len(chains) >= 50:
    #             break

    #     self.detected_patterns["layering_chains"] = chains
    #     print(f"[GraphEngine]   Found {len(chains)} layering chains")

    def _is_rapid_chain(self, path: List[str]) -> bool:
        """Check if a chain completes within a short window."""
        timestamps = []
        for i in range(len(path) - 1):
            edges = self.G.get_edge_data(path[i], path[i + 1])
            if not edges:
                return False
            latest = max(edges.values(), key=lambda e: e.get("timestamp", datetime.min))
            timestamps.append(latest.get("timestamp", datetime.min))
        if not timestamps:
            return False
        span = (max(timestamps) - min(timestamps)).total_seconds() / 3600
        return span < config.FRAUD_CONFIG["layering"]["time_window_hours"]

    def _detect_mule_hubs(self, G: nx.DiGraph):
        """Detect high-fanout nodes (hub-and-spoke pattern)."""
        print("[GraphEngine]   Detecting mule hubs...")
        hubs = []
        for node in G.nodes():
            out_deg = G.out_degree(node)
            in_deg = G.in_degree(node)
            if out_deg >= config.HUB_DEGREE_THRESHOLD:
                node_data = G.nodes[node]
                hubs.append({
                    "account_id": node, "out_degree": out_deg,
                    "in_degree": in_deg, "is_dormant": node_data.get("is_dormant", False),
                    "fan_out_ratio": out_deg / max(in_deg, 1),
                })
        hubs.sort(key=lambda x: x["out_degree"], reverse=True)
        self.detected_patterns["mule_hubs"] = hubs[:20]
        print(f"[GraphEngine]   Found {len(hubs)} potential mule hubs")

    def _detect_temporal_bursts(self):
        """Detect rapid sequential transfers through paths."""
        print("[GraphEngine]   Detecting temporal bursts...")
        bursts = []
        node_txns = defaultdict(list)

        for u, v, data in self.G.edges(data=True):
            ts = data.get("timestamp")
            if ts:
                node_txns[u].append({"to": v, "ts": ts, "amount": data.get("amount", 0)})

        for node, txns in node_txns.items():
            txns.sort(key=lambda x: x["ts"])
            window = timedelta(hours=config.TEMPORAL_WINDOW_HOURS)
            for i, tx in enumerate(txns):
                window_txns = [t for t in txns if tx["ts"] <= t["ts"] <= tx["ts"] + window]
                if len(window_txns) >= 5:
                    unique_targets = len(set(t["to"] for t in window_txns))
                    total_amount = sum(t["amount"] for t in window_txns)
                    bursts.append({
                        "account_id": node, "txn_count": len(window_txns),
                        "unique_targets": unique_targets, "total_amount": total_amount,
                        "window_start": tx["ts"].isoformat(),
                    })
                    break

        bursts.sort(key=lambda x: x["txn_count"], reverse=True)
        self.detected_patterns["temporal_bursts"] = bursts[:30]
        print(f"[GraphEngine]   Found {len(bursts)} temporal burst nodes")

    def _detect_communities(self, G: nx.DiGraph):
        """Detect suspicious tight-knit communities."""
        print("[GraphEngine]   Detecting communities...")
        undirected = G.to_undirected()
        if HAS_LOUVAIN:
            partition = community_louvain.best_partition(undirected)
            communities = defaultdict(list)
            for node, comm_id in partition.items():
                communities[comm_id].append(node)
            suspicious = [
                {"community_id": cid, "members": members, "size": len(members)}
                for cid, members in communities.items()
                if config.COMMUNITY_MIN_SIZE <= len(members) <= 30
            ]
            suspicious.sort(key=lambda x: x["size"], reverse=True)
            self.detected_patterns["communities"] = suspicious[:20]
        else:
            components = list(nx.connected_components(undirected))
            suspicious = [
                {"community_id": i, "members": list(c), "size": len(c)}
                for i, c in enumerate(components)
                if config.COMMUNITY_MIN_SIZE <= len(c) <= 30
            ]
            self.detected_patterns["communities"] = suspicious[:20]
        print(f"[GraphEngine]   Found {len(self.detected_patterns['communities'])} communities")

    def _compute_graph_scores(self, G: nx.DiGraph):
        """Compute per-account graph risk score from all detected patterns."""
        scores = defaultdict(float)

        # Cycle membership
        for cycle in self.detected_patterns["cycles"]:
            for node in cycle:
                scores[node] += 0.4

        # Layering chain membership
        for chain in self.detected_patterns["layering_chains"]:
            for node in chain:
                scores[node] += 0.3

        # Mule hub score
        for hub in self.detected_patterns["mule_hubs"]:
            scores[hub["account_id"]] += 0.6 * min(hub["fan_out_ratio"] / 5, 1.0)

        # Temporal burst score
        for burst in self.detected_patterns["temporal_bursts"]:
            scores[burst["account_id"]] += 0.25 * min(burst["txn_count"] / 10, 1.0)

        # Centrality boost
        try:
            bc = nx.betweenness_centrality(G, k=min(100, len(G)))
            threshold = np.percentile(list(bc.values()), 100 * config.CENTRALITY_THRESHOLD) if bc else 0
            for node, cent in bc.items():
                if cent > threshold:
                    scores[node] += 0.15
        except Exception:
            pass

        # Normalize to [0, 1]
        max_score = max(scores.values()) if scores else 1
        self.account_graph_scores = {
            node: min(round(score / max(max_score, 1), 4), 1.0)
            for node, score in scores.items()
        }
        # Fill zeros for accounts not in any pattern
        for node in G.nodes():
            if node not in self.account_graph_scores:
                self.account_graph_scores[node] = 0.0


    def get_suspicious_subgraph(self, account_id: str, hops: int = 2) -> Dict:
        """Extract ego-subgraph for investigation visualization."""
        if account_id not in self.G:
            return {"nodes": [], "edges": []}

        ego = nx.ego_graph(self.G.to_undirected(), account_id, radius=hops)
        ego_directed = self.G.subgraph(ego.nodes())

        # ── Cap at 60 nodes for vis.js performance ──────────────────
        if len(ego_directed.nodes()) > 60:
            degrees = dict(self.G.degree())
            degrees[account_id] = 999999  # always keep center node
            top_nodes = sorted(
                ego_directed.nodes(),
                key=lambda n: degrees.get(n, 0),
                reverse=True
            )[:60]
            ego_directed = self.G.subgraph(top_nodes)
        # ────────────────────────────────────────────────────────────

        nodes = []
        for n in ego_directed.nodes():
            nd = self.G.nodes[n]
            gs = self.account_graph_scores.get(n, 0)
            in_cycle = any(n in c for c in self.detected_patterns["cycles"])
            in_chain = any(n in c for c in self.detected_patterns["layering_chains"])
            is_hub = any(h["account_id"] == n for h in self.detected_patterns["mule_hubs"])

            nodes.append({
                "id": n, "label": n[-6:],
                "name": nd.get("name", "Unknown"),
                "type": nd.get("type", "unknown"),
                "branch": nd.get("branch", ""),
                "is_dormant": nd.get("is_dormant", False),
                "graph_score": gs, "is_center": n == account_id,
                "in_cycle": in_cycle, "in_chain": in_chain, "is_hub": is_hub,
            })

        edges = []
        for u, v, key, data in ego_directed.edges(data=True, keys=True):
            edges.append({
                "from": u, "to": v, "tx_id": data.get("tx_id", key),
                "amount": data.get("amount", 0),
                "timestamp": data.get("timestamp", datetime.min).isoformat()
                             if data.get("timestamp") else "",
                "is_fraud": data.get("is_fraud", False),
            })

        return {"nodes": nodes, "edges": edges}

    # def get_suspicious_subgraph(self, account_id: str, hops: int = 2) -> Dict:
    #     """Extract ego-subgraph for investigation visualization."""
    #     if account_id not in self.G:
    #         return {"nodes": [], "edges": []}

    #     ego = nx.ego_graph(self.G.to_undirected(), account_id, radius=hops)
    #     ego_directed = self.G.subgraph(ego.nodes())

    #     nodes = []
    #     for n in ego_directed.nodes():
    #         nd = self.G.nodes[n]
    #         gs = self.account_graph_scores.get(n, 0)
    #         in_cycle = any(n in c for c in self.detected_patterns["cycles"])
    #         in_chain = any(n in c for c in self.detected_patterns["layering_chains"])
    #         is_hub = any(h["account_id"] == n for h in self.detected_patterns["mule_hubs"])

    #         nodes.append({
    #             "id": n, "label": n[-6:],
    #             "name": nd.get("name", "Unknown"),
    #             "type": nd.get("type", "unknown"),
    #             "branch": nd.get("branch", ""),
    #             "is_dormant": nd.get("is_dormant", False),
    #             "graph_score": gs, "is_center": n == account_id,
    #             "in_cycle": in_cycle, "in_chain": in_chain, "is_hub": is_hub,
    #         })

    #     edges = []
    #     for u, v, key, data in ego_directed.edges(data=True, keys=True):
    #         edges.append({
    #             "from": u, "to": v, "tx_id": data.get("tx_id", key),
    #             "amount": data.get("amount", 0),
    #             "timestamp": data.get("timestamp", datetime.min).isoformat() if data.get("timestamp") else "",
    #             "is_fraud": data.get("is_fraud", False),
    #         })

    #     return {"nodes": nodes, "edges": edges}

    def get_patterns_for_account(self, account_id: str) -> Dict:
        """Get all detected patterns involving this account."""
        return {
            "cycles": [c for c in self.detected_patterns["cycles"] if account_id in c],
            "layering_chains": [c for c in self.detected_patterns["layering_chains"] if account_id in c],
            "is_mule_hub": any(h["account_id"] == account_id for h in self.detected_patterns["mule_hubs"]),
            "temporal_burst": next(
                (b for b in self.detected_patterns["temporal_bursts"] if b["account_id"] == account_id), None
            ),
        }

    def get_suspicious_path_subgraph(self, account_id: str) -> Dict:
        """
        Extract a focused investigation subgraph (5-15 nodes) showing only
        the suspicious fund flow path involving the account.
        Returns the suspicious path, fraud classifications, and a minimal graph.
        """
        if account_id not in self.G:
            return {"nodes": [], "edges": [], "suspicious_path": [],
                    "fraud_classifications": [], "pattern_type": "unknown"}

        patterns = self.get_patterns_for_account(account_id)
        classifications = self.get_fraud_classifications(account_id)

        # ── Determine the primary suspicious path ────────────────────────
        path_nodes = set()
        path_edges = set()  # (from, to) pairs
        pattern_type = "unknown"

        # Priority 1: Circular flow
        if patterns["cycles"]:
            cycle = max(patterns["cycles"], key=len)
            path_nodes.update(cycle)
            for i in range(len(cycle)):
                path_edges.add((cycle[i], cycle[(i + 1) % len(cycle)]))
            pattern_type = "circular_flow"

        # Priority 2: Layering chains
        elif patterns["layering_chains"]:
            chain = max(patterns["layering_chains"], key=len)
            path_nodes.update(chain)
            for i in range(len(chain) - 1):
                path_edges.add((chain[i], chain[i + 1]))
            pattern_type = "layering"

        # Priority 3: Mule hub
        elif patterns["is_mule_hub"]:
            path_nodes.add(account_id)
            # Add spokes (immediate successors/predecessors)
            for pred in list(self.G.predecessors(account_id))[:5]:
                path_nodes.add(pred)
                path_edges.add((pred, account_id))
            for succ in list(self.G.successors(account_id))[:8]:
                path_nodes.add(succ)
                path_edges.add((account_id, succ))
            pattern_type = "mule_network"

        # Priority 4: Temporal burst / dormant activation
        elif patterns["temporal_burst"]:
            path_nodes.add(account_id)
            node_data = self.G.nodes.get(account_id, {})
            if node_data.get("is_dormant", False):
                pattern_type = "dormant_activation"
            else:
                pattern_type = "temporal_burst"
            # Add immediate neighbors with fraud edges
            for pred in self.G.predecessors(account_id):
                edges = self.G.get_edge_data(pred, account_id)
                if edges and any(e.get("is_fraud", False) for e in edges.values()):
                    path_nodes.add(pred)
                    path_edges.add((pred, account_id))
            for succ in self.G.successors(account_id):
                edges = self.G.get_edge_data(account_id, succ)
                if edges and any(e.get("is_fraud", False) for e in edges.values()):
                    path_nodes.add(succ)
                    path_edges.add((account_id, succ))

        # Fallback: if no specific pattern, get 1-hop fraud neighbors
        if not path_nodes:
            path_nodes.add(account_id)
            for pred in self.G.predecessors(account_id):
                edges = self.G.get_edge_data(pred, account_id)
                if edges:
                    for e in edges.values():
                        if e.get("is_fraud", False):
                            path_nodes.add(pred)
                            path_edges.add((pred, account_id))
                            break
            for succ in self.G.successors(account_id):
                edges = self.G.get_edge_data(account_id, succ)
                if edges:
                    for e in edges.values():
                        if e.get("is_fraud", False):
                            path_nodes.add(succ)
                            path_edges.add((account_id, succ))
                            break
            pattern_type = "suspicious_activity"

        # ── Add 1-hop context neighbors (non-path) for visual context ────
        context_nodes = set()
        for n in list(path_nodes):
            for neighbor in list(self.G.predecessors(n))[:2]:
                if neighbor not in path_nodes:
                    context_nodes.add(neighbor)
            for neighbor in list(self.G.successors(n))[:2]:
                if neighbor not in path_nodes:
                    context_nodes.add(neighbor)

        # Limit total to 15 nodes
        all_nodes = path_nodes | context_nodes
        if len(all_nodes) > 15:
            # Keep all path nodes, trim context
            max_context = 15 - len(path_nodes)
            context_nodes = set(list(context_nodes)[:max(max_context, 0)])
            all_nodes = path_nodes | context_nodes

        # ── Build the subgraph ───────────────────────────────────────────
        subgraph = self.G.subgraph(all_nodes)

        # Build ordered suspicious path for display
        suspicious_path_ordered = []
        if patterns["cycles"]:
            cycle = max(patterns["cycles"], key=len)
            suspicious_path_ordered = list(cycle) + [cycle[0]]  # close the loop
        elif patterns["layering_chains"]:
            chain = max(patterns["layering_chains"], key=len)
            suspicious_path_ordered = list(chain)

        nodes = []
        for n in subgraph.nodes():
            nd = self.G.nodes[n]
            gs = self.account_graph_scores.get(n, 0)
            on_path = n in path_nodes
            in_cycle = any(n in c for c in self.detected_patterns["cycles"])
            in_chain = any(n in c for c in self.detected_patterns["layering_chains"])
            is_hub = any(h["account_id"] == n for h in self.detected_patterns["mule_hubs"])

            nodes.append({
                "id": n, "label": n[-6:],
                "name": nd.get("name", "Unknown"),
                "type": nd.get("type", "unknown"),
                "branch": nd.get("branch", ""),
                "is_dormant": nd.get("is_dormant", False),
                "graph_score": gs, "is_center": n == account_id,
                "in_cycle": in_cycle, "in_chain": in_chain, "is_hub": is_hub,
                "on_suspicious_path": on_path,
            })

        edges = []
        for u, v, key, data in subgraph.edges(data=True, keys=True):
            on_path = (u, v) in path_edges
            edges.append({
                "from": u, "to": v, "tx_id": data.get("tx_id", key),
                "amount": data.get("amount", 0),
                "timestamp": data.get("timestamp", datetime.min).isoformat()
                             if data.get("timestamp") else "",
                "is_fraud": data.get("is_fraud", False),
                "on_suspicious_path": on_path,
            })

        # Limit edges to 25
        if len(edges) > 25:
            # Keep path edges, trim non-path
            path_e = [e for e in edges if e["on_suspicious_path"]]
            non_path_e = [e for e in edges if not e["on_suspicious_path"]]
            edges = path_e + non_path_e[:max(25 - len(path_e), 0)]

        return {
            "nodes": nodes,
            "edges": edges,
            "suspicious_path": suspicious_path_ordered,
            "fraud_classifications": classifications,
            "pattern_type": pattern_type,
        }

    def get_fraud_classifications(self, account_id: str) -> List[Dict]:
        """
        Classify fraud patterns for an account with confidence scores.
        Returns list of {name, confidence, evidence} dicts.
        """
        patterns = self.get_patterns_for_account(account_id)
        classifications = []

        # ── Circular Flow ────────────────────────────────────────────────
        if patterns["cycles"]:
            best_cycle = max(patterns["cycles"], key=len)
            cycle_len = len(best_cycle)
            # Confidence based on cycle length and temporal consistency
            base_conf = 0.7
            if cycle_len >= 4:
                base_conf += 0.1
            if cycle_len >= 5:
                base_conf += 0.05
            # Check if multiple rounds exist
            multi_round = self._count_cycle_rounds(best_cycle)
            if multi_round > 1:
                base_conf += min(multi_round * 0.05, 0.15)
            conf = min(round(base_conf, 2), 0.98)
            path_str = " → ".join(n[-6:] for n in best_cycle) + " → " + best_cycle[0][-6:]
            classifications.append({
                "name": "Circular Flow",
                "confidence": conf,
                "evidence": f"{cycle_len}-node cycle detected: {path_str}. "
                           f"{multi_round} round(s) of fund circulation identified.",
            })

        # ── Layering ─────────────────────────────────────────────────────
        if patterns["layering_chains"]:
            best_chain = max(patterns["layering_chains"], key=len)
            chain_len = len(best_chain)
            base_conf = 0.6
            if chain_len >= 5:
                base_conf += 0.1
            if chain_len >= 7:
                base_conf += 0.06
            # Check if rapid
            if self._is_rapid_chain(best_chain):
                base_conf += 0.1
            conf = min(round(base_conf, 2), 0.98)
            path_str = " → ".join(n[-6:] for n in best_chain)
            classifications.append({
                "name": "Layering",
                "confidence": conf,
                "evidence": f"{chain_len}-hop chain: {path_str}. "
                           f"Funds layered through multiple intermediaries.",
            })

        # ── Mule Network ─────────────────────────────────────────────────
        if patterns["is_mule_hub"]:
            hub_info = next(
                (h for h in self.detected_patterns["mule_hubs"]
                 if h["account_id"] == account_id), None
            )
            if hub_info:
                out_deg = hub_info["out_degree"]
                fan_ratio = hub_info["fan_out_ratio"]
                base_conf = 0.65
                if out_deg >= 15:
                    base_conf += 0.15
                elif out_deg >= 10:
                    base_conf += 0.1
                if fan_ratio > 3:
                    base_conf += 0.08
                conf = min(round(base_conf, 2), 0.98)
                classifications.append({
                    "name": "Mule Network",
                    "confidence": conf,
                    "evidence": f"Hub-and-spoke pattern: {out_deg} outgoing transfers, "
                               f"fan-out ratio {fan_ratio:.1f}x. "
                               f"Consistent with mule account distribution.",
                })

        # ── Dormant Activation ───────────────────────────────────────────
        node_data = self.G.nodes.get(account_id, {})
        if node_data.get("is_dormant", False):
            in_edges = list(self.G.in_edges(account_id, data=True))
            out_edges = list(self.G.out_edges(account_id, data=True))
            if in_edges or out_edges:
                base_conf = 0.75
                total_inflow = sum(d.get("amount", 0) for _, _, d in in_edges)
                total_outflow = sum(d.get("amount", 0) for _, _, d in out_edges)
                if total_inflow > 500000:
                    base_conf += 0.1
                if len(out_edges) > 5:
                    base_conf += 0.08
                conf = min(round(base_conf, 2), 0.98)
                classifications.append({
                    "name": "Dormant Activation",
                    "confidence": conf,
                    "evidence": f"Previously dormant account activated with "
                               f"₹{total_inflow:,.0f} inflow and {len(out_edges)} "
                               f"outgoing transfers totaling ₹{total_outflow:,.0f}.",
                })

        # ── Temporal Burst ───────────────────────────────────────────────
        if patterns["temporal_burst"] and not node_data.get("is_dormant", False):
            burst = patterns["temporal_burst"]
            base_conf = 0.6
            if burst["txn_count"] >= 8:
                base_conf += 0.15
            elif burst["txn_count"] >= 5:
                base_conf += 0.1
            if burst["unique_targets"] >= 5:
                base_conf += 0.08
            conf = min(round(base_conf, 2), 0.98)
            classifications.append({
                "name": "Rapid Redistribution",
                "confidence": conf,
                "evidence": f"{burst['txn_count']} transfers to "
                           f"{burst['unique_targets']} unique recipients "
                           f"totaling ₹{burst['total_amount']:,.0f} in a single window.",
            })

        # Sort by confidence descending
        classifications.sort(key=lambda x: x["confidence"], reverse=True)
        return classifications

    def _count_cycle_rounds(self, cycle: List[str]) -> int:
        """Count how many complete rounds a cycle has been traversed."""
        rounds = 0
        for i in range(len(cycle)):
            src, dst = cycle[i], cycle[(i + 1) % len(cycle)]
            edges = self.G.get_edge_data(src, dst)
            if edges:
                rounds = max(rounds, len(edges))
        return rounds
