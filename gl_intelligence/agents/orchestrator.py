"""
Agent Orchestrator — runs all agents and returns unified results.
This is the main entry point for the agentic pipeline.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from gl_intelligence.config import cfg
from gl_intelligence.cortex.client import CortexClient
from gl_intelligence.agents.base import AgentResult
from gl_intelligence.agents.mapping_agent import MappingAgent
from gl_intelligence.agents.recon_agent import ReconciliationAgent
from gl_intelligence.agents.anomaly_agent import AnomalyAgent
from gl_intelligence.agents.disclosure_agent import DisclosureAgent
from gl_intelligence.agents.tax_agent import TaxReconciliationAgent
from gl_intelligence.agents.tax_classifier_agent import TaxClassifierAgent
from gl_intelligence.agents.etr_bridge_agent import ETRBridgeAgent

log = logging.getLogger("agents.orchestrator")


class AgentOrchestrator:
    """
    Runs the full agentic financial pipeline:
      1. Mapping Agent — classify unmapped GL accounts
      2. Reconciliation Agent — validate DISE vs IS face
      3. Anomaly Agent — detect YoY outliers
      4. Disclosure Agent — generate footnote text

    Can run all agents or individual ones.
    """

    def __init__(self, cortex: CortexClient | None = None):
        self.cx = cortex or CortexClient()
        self.agents = {
            "mapping":        MappingAgent(self.cx),
            "recon":          ReconciliationAgent(self.cx),
            "anomaly":        AnomalyAgent(self.cx),
            "disclosure":     DisclosureAgent(self.cx),
            "tax":            TaxReconciliationAgent(self.cx),
            "tax_classifier": TaxClassifierAgent(self.cx),
            "etr_bridge":     ETRBridgeAgent(self.cx),
        }
        log.info(f"Orchestrator initialized with {len(self.agents)} agents — project={cfg.PROJECT}")

    def run_all(self, dry_run: bool = False) -> dict[str, AgentResult]:
        """Run the full pipeline in sequence."""
        log.info("=" * 60)
        log.info("  GL INTELLIGENCE PLATFORM — FULL AGENT PIPELINE")
        log.info("=" * 60)
        start = time.time()
        results = {}

        # 1. Mapping
        log.info("\n--- STAGE 1: GL Mapping Agent ---")
        results["mapping"] = self.agents["mapping"].run(dry_run=dry_run)
        log.info(f"  Result: {results['mapping'].summary}")

        # 2. Reconciliation
        log.info("\n--- STAGE 2: Reconciliation Agent ---")
        results["recon"] = self.agents["recon"].run()
        log.info(f"  Result: {results['recon'].summary}")

        # 3. Anomaly detection
        log.info("\n--- STAGE 3: Anomaly Detection Agent ---")
        results["anomaly"] = self.agents["anomaly"].run()
        log.info(f"  Result: {results['anomaly'].summary}")

        # 4. Disclosure generation
        log.info("\n--- STAGE 4: Disclosure Agent ---")
        results["disclosure"] = self.agents["disclosure"].run()
        log.info(f"  Result: {results['disclosure'].summary}")

        elapsed = time.time() - start
        log.info(f"\n{'=' * 60}")
        log.info(f"  PIPELINE COMPLETE — {elapsed:.1f}s")
        log.info(f"{'=' * 60}")

        return results

    def run_agent(self, agent_name: str, **kwargs) -> AgentResult:
        """Run a single agent by name."""
        agent = self.agents.get(agent_name)
        if not agent:
            raise ValueError(f"Unknown agent: {agent_name}. Available: {list(self.agents.keys())}")
        return agent.run(**kwargs)

    def get_platform_status(self) -> dict:
        """Returns current platform status without running agents."""
        mapping_agent = self.agents["mapping"]

        # Offline classified data stats
        classified = mapping_agent.get_classified_accounts()
        cats = {}
        for d in classified:
            c = d.get("suggested_category", "?")
            cats[c] = cats.get(c, 0) + 1

        return {
            "project": cfg.PROJECT,
            "config": cfg.summary(),
            # BigQuery (Max's demo)
            "bq_approved_mappings": len(mapping_agent.get_approved_mappings()),
            "bq_pending_mappings": len(mapping_agent.get_pending_mappings()),
            "bq_dise_pivot": mapping_agent.get_dise_pivot(),
            "bq_close_tracker": mapping_agent.get_close_tracker(),
            "bq_anomaly_alerts": mapping_agent.get_anomaly_alerts(),
            # Offline classified (Excel pipeline)
            "classified_accounts": len(classified),
            "classified_categories": cats,
            "classified_total": sum(float(d.get("posting_amount", 0)) for d in classified),
        }
