"""
GraphGuard v2 — Investigation Intelligence Engine
Generates human-readable investigation summaries and STR-style narratives.
"""

import os, sys
from datetime import datetime
from typing import Dict, List, Optional
from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class InvestigationEngine:
    """
    Generates structured investigation summaries and STR narratives
    using Jinja2 templates with deterministic evidence formatting.
    """

    def __init__(self):
        template_dir = str(config.TEMPLATE_DIR)
        if os.path.exists(template_dir):
            self.env = Environment(loader=FileSystemLoader(template_dir))
        else:
            self.env = None

    def generate_investigation(self, account_id: str,
                                score_breakdown: Dict,
                                graph_patterns: Dict,
                                temporal_profile: Dict,
                                timeline: List[Dict],
                                account_info: Dict,
                                edge_explanations: List = None) -> Dict:
        """Generate complete investigation package for an account."""
        evidence = self._compile_evidence(
            account_id, score_breakdown, graph_patterns,
            temporal_profile, timeline, account_info, edge_explanations
        )

        summary = self._generate_summary(evidence)
        str_narrative = self._generate_str(evidence)

        return {
            "account_id": account_id,
            "generated_at": datetime.now().isoformat(),
            "summary": summary,
            "str_narrative": str_narrative,
            "evidence": evidence,
            "recommended_actions": self._get_recommendations(evidence),
        }

    def _compile_evidence(self, account_id, score_breakdown, graph_patterns,
                          temporal_profile, timeline, account_info, edge_explanations):
        """Compile all evidence into a structured format."""
        detected = []
        if graph_patterns.get("cycles"):
            detected.append("Circular Laundering")
        if graph_patterns.get("layering_chains"):
            detected.append("Layering")
        if graph_patterns.get("is_mule_hub"):
            detected.append("Hub-and-Spoke Mule Network")
        if graph_patterns.get("temporal_burst"):
            detected.append("Temporal Burst Activity")
        if temporal_profile and temporal_profile.get("dormant_activation", 0) > 0:
            detected.append("Dormant Account Activation")
        if temporal_profile and temporal_profile.get("burst_redistribution_count", 0) >= 3:
            detected.append("Rapid Fund Redistribution")

        return {
            "account_id": account_id,
            "account_info": account_info or {},
            "scores": score_breakdown or {},
            "detected_patterns": detected,
            "graph_patterns": graph_patterns or {},
            "temporal_profile": temporal_profile or {},
            "timeline": timeline or [],
            "edge_explanations": edge_explanations or [],
            "severity": self._score_to_severity(score_breakdown.get("fused_score", 0)),
        }

    def _score_to_severity(self, score: float) -> str:
        for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            if score >= config.ALERT_THRESHOLDS[level]:
                return level
        return "NONE"

    def _generate_summary(self, evidence: Dict) -> str:
        """Generate investigation summary."""
        if self.env and "investigation_summary.j2" in self.env.list_templates():
            try:
                template = self.env.get_template("investigation_summary.j2")
                return template.render(**evidence)
            except Exception:
                pass
        return self._fallback_summary(evidence)

    def _generate_str(self, evidence: Dict) -> str:
        """Generate STR-style narrative."""
        if self.env and "str_report.j2" in self.env.list_templates():
            try:
                template = self.env.get_template("str_report.j2")
                return template.render(**evidence)
            except Exception:
                pass
        return self._fallback_str(evidence)

    def _fallback_summary(self, e: Dict) -> str:
        """Deterministic fallback summary when template is unavailable."""
        acc = e["account_id"]
        severity = e["severity"]
        score = e["scores"].get("fused_score", 0)
        patterns = ", ".join(e["detected_patterns"]) or "No specific patterns"
        tp = e.get("temporal_profile", {})

        lines = [
            f"═══ INVESTIGATION SUMMARY ═══",
            f"Subject: {acc}",
            f"Severity: {severity} | Risk Score: {score:.2%}",
            f"Detected Patterns: {patterns}",
            f"",
            f"SCORE BREAKDOWN:",
            f"  Edge Intelligence:     {e['scores'].get('edge_score', 0):.2%}",
            f"  Graph Intelligence:    {e['scores'].get('graph_score', 0):.2%}",
            f"  Temporal Intelligence: {e['scores'].get('temporal_score', 0):.2%}",
        ]
        if tp:
            lines.extend([
                f"",
                f"TEMPORAL BEHAVIOR:",
                f"  Avg Propagation Speed: {tp.get('avg_propagation_speed_hrs', 'N/A')} hrs",
                f"  Min Retention Time:    {tp.get('min_retention_hrs', 'N/A')} hrs",
                f"  Peak Hop Density:      {tp.get('peak_hop_density_per_hr', 'N/A')}/hr",
                f"  Burst Redistributions: {tp.get('burst_redistribution_count', 0)}",
                f"  Unique Beneficiaries:  {tp.get('unique_beneficiaries', 0)}",
            ])
        return "\n".join(lines)

    def _fallback_str(self, e: Dict) -> str:
        """Deterministic fallback STR narrative."""
        acc = e["account_id"]
        info = e.get("account_info", {})
        score = e["scores"].get("fused_score", 0)
        patterns = e["detected_patterns"]
        tp = e.get("temporal_profile", {})

        narrative = f"""SUSPICIOUS TRANSACTION REPORT (STR)
Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Reference: STR-{acc[-6:]}-{datetime.now().strftime('%Y%m%d')}

SUBJECT INFORMATION:
  Account Number: {acc}
  Account Holder: {info.get('holder_name', 'Under Investigation')}
  Account Type:   {info.get('account_type', 'N/A')}
  Branch:         {info.get('branch', 'N/A')}

SUSPICIOUS ACTIVITY SUMMARY:
  The account {acc} has been flagged with a composite risk score of {score:.2%}
  based on multi-dimensional intelligence analysis.

DETECTED PATTERNS:
"""
        for p in patterns:
            narrative += f"  • {p}\n"

        if not patterns:
            narrative += "  • Elevated risk indicators across multiple dimensions\n"

        gp = e.get("graph_patterns", {})
        if gp.get("cycles"):
            cycle = gp["cycles"][0]
            narrative += f"\nCIRCULAR FLOW EVIDENCE:\n"
            narrative += f"  Fund circulation detected: {' → '.join(c[-6:] for c in cycle)} → {cycle[0][-6:]}\n"

        if gp.get("layering_chains"):
            chain = gp["layering_chains"][0]
            narrative += f"\nLAYERING EVIDENCE:\n"
            narrative += f"  Multi-hop chain: {' → '.join(c[-6:] for c in chain)}\n"

        if tp:
            narrative += f"\nTEMPORAL BEHAVIOR ANALYSIS:\n"
            narrative += f"  Funds are retained for an average of {tp.get('avg_retention_hrs', 'N/A')} hours\n"
            narrative += f"  before redistribution, with peak activity of {tp.get('peak_hop_density_per_hr', 'N/A')}\n"
            narrative += f"  outgoing transfers per hour. {tp.get('unique_beneficiaries', 0)} unique\n"
            narrative += f"  beneficiaries received funds from this account.\n"

        narrative += f"\nRISK ASSESSMENT:\n"
        narrative += f"  This activity is consistent with {'money laundering' if score > 0.7 else 'suspicious fund movement'}.\n"
        narrative += f"  Further investigation and potential escalation recommended.\n"

        return narrative

    def _get_recommendations(self, evidence: Dict) -> List[str]:
        """Generate recommended investigation actions."""
        actions = []
        severity = evidence["severity"]
        patterns = evidence["detected_patterns"]

        if severity in ("CRITICAL", "HIGH"):
            actions.append("Immediately escalate to AML compliance team")
            actions.append("Freeze outgoing transactions pending review")

        if "Circular Laundering" in patterns:
            actions.append("Investigate all accounts in the circular flow for coordinated activity")

        if "Layering" in patterns:
            actions.append("Trace complete fund flow chain and identify ultimate beneficiary")

        if "Hub-and-Spoke Mule Network" in patterns:
            actions.append("Profile all spoke accounts for potential mule recruitment")

        if "Dormant Account Activation" in patterns:
            actions.append("Verify account holder identity and recent KYC status")

        if "Rapid Fund Redistribution" in patterns:
            actions.append("Review redistribution recipients for common ownership patterns")

        if severity in ("MEDIUM",):
            actions.append("Schedule enhanced monitoring for the next 30 days")

        actions.append("Document findings for regulatory filing consideration")
        return actions
