"""
DISE GL Mapping Agent — classifies GL accounts into ASU 2024-03 natural expense categories.
Uses SAP Cortex data + Claude AI + similarity matching against approved mappings.
"""

from __future__ import annotations

import json
import logging
import time

from gl_intelligence.config import cfg
from gl_intelligence.cortex.client import CortexClient
from gl_intelligence.cortex.sap import SAPConnector
from gl_intelligence.agents.base import BaseAgent, AgentResult

log = logging.getLogger("agents.mapping")

VALID_CATEGORIES = [
    "Purchases of inventory", "Employee compensation",
    "Depreciation", "Intangible asset amortization", "Other expenses",
]
VALID_CAPTIONS = ["COGS", "SG&A", "R&D", "Other income/expense"]

SYSTEM_PROMPT = """You are the GL Mapping Agent for BE Technology's GL Intelligence Platform.

Classify GL accounts into the five ASU 2024-03 (DISE) natural expense categories under ASC 220-40.
Your decisions will be reviewed by a Controller before use in SEC filings.

CATEGORIES:
1. Purchases of inventory — ASC 220-40-50-6(b) — raw materials, direct materials, freight-in. Caption: COGS.
2. Employee compensation — ASC 220-40-50-6(a) — salaries, wages, benefits, pension, stock comp. Caption: COGS/SG&A/R&D by function.
3. Depreciation — ASC 220-40-50-6(c) — tangible assets (PP&E, ROU assets). HARDWARE = depreciation. Caption: COGS/SG&A.
4. Intangible asset amortization — ASC 220-40-50-6(d) — patents, software, customer lists. SOFTWARE = amortization. Caption: SG&A.
5. Other expenses — ASC 220-40-50-6(e) — rent, utilities, insurance, professional fees, marketing, contractors. Caption: varies.

EDGE CASES: Operating leases → Other. ROU depreciation → Depreciation. Contractor services → Other. Employee software dev → Compensation.

CONFIDENCE: HIGH (0.85-1.0) = certain. MEDIUM (0.60-0.84) = some ambiguity. LOW (0.0-0.59) = needs human investigation.

Respond ONLY with valid JSON:
{"suggested_category":"...","suggested_caption":"...","suggested_citation":"...","confidence_score":0.0,"confidence_label":"...","draft_reasoning":"..."}"""


class MappingAgent(BaseAgent):
    AGENT_ID = "GL_MAPPING_AGENT_v1"
    DESCRIPTION = "Classifies unmapped GL accounts into DISE categories"

    def __init__(self, cortex: CortexClient | None = None):
        super().__init__(cortex)
        self.sap = SAPConnector(self.cx)

    def run(self, batch_size: int = 20, dry_run: bool = False,
            source: str = "auto", **kwargs) -> AgentResult:
        """
        Main agent loop.
        source: "auto" tries BigQuery first, falls back to offline.
                "bigquery" forces live SAP data. "offline" uses classified JSON.
        """
        start = time.time()
        result = AgentResult(agent_id=self.AGENT_ID, status="success", started_at=self.now_iso())

        # Get accounts to process
        import random
        use_offline = source == "offline" or (source == "auto" and not self.cx.available)
        if use_offline:
            all_classified = self.get_classified_accounts()
            low_med = [a for a in all_classified if a.get("confidence_label", "").upper() in ("LOW", "MEDIUM")]
            accounts = low_med if low_med else random.sample(all_classified, min(batch_size, len(all_classified)))
            dry_run = True
            log.info(f"Offline mode: {len(accounts)} accounts selected for validation")
        elif source in ("bigquery", "auto"):
            accounts = self.sap.get_unmapped_accounts()
            # If BQ has no unmapped accounts, fall back to validating a sample from offline data
            if not accounts:
                log.info("No unmapped accounts in BQ — running validation sample from offline data")
                all_classified = self.get_classified_accounts()
                accounts = random.sample(all_classified, min(batch_size, len(all_classified)))
                dry_run = True
        else:
            raise ValueError(f"Unknown source: {source}")

        if not accounts:
            log.info("No accounts to process.")
            result.completed_at = self.now_iso()
            result.elapsed_seconds = time.time() - start
            result.summary = {"message": "No accounts available"}
            return result

        # Get reference library
        reference = self.get_approved_mappings()
        log.info(f"Processing {min(len(accounts), batch_size)} of {len(accounts)} unmapped accounts "
                 f"({len(reference)} approved references)")

        for i, account in enumerate(accounts[:batch_size], 1):
            log.info(f"[{i}/{min(len(accounts), batch_size)}] {account['gl_account']} — "
                     f"{(account.get('description') or '')[:50]}")

            # Find similar approved accounts
            similar = self._find_similar(account.get("description", ""), reference)

            # Call Claude
            decision = self._classify(account, similar)
            if not decision:
                result.errors += 1
                continue

            log.info(f"  -> {decision['suggested_category']} | {decision['suggested_caption']} | "
                     f"{decision['confidence_label']} ({decision['confidence_score']:.0%})")

            if dry_run:
                result.results.append({**account, **decision})
                result.processed += 1
                continue

            # Write to BigQuery
            try:
                self._write_pending(account, decision, similar)
                self.write_audit_event("AGENT_DRAFT", account["gl_account"], {
                    "description": account.get("description", ""),
                    "fiscal_year": cfg.FISCAL_YEAR,
                    "company_code": cfg.COMPANY_CODE,
                    "posting_amount": float(account.get("posting_amount", 0)),
                    "agent_category": decision["suggested_category"],
                    "agent_caption": decision["suggested_caption"],
                    "agent_citation": decision["suggested_citation"],
                    "agent_confidence": decision["confidence_score"],
                    "agent_reasoning": decision["draft_reasoning"][:5000],
                    "prompt_version": "v1.1",
                })
                result.results.append({**account, **decision})
                result.processed += 1
            except Exception as e:
                log.error(f"  Write error: {e}")
                result.errors += 1

            time.sleep(cfg.API_DELAY)

        result.completed_at = self.now_iso()
        result.elapsed_seconds = time.time() - start
        result.summary = {
            "total_unmapped": len(accounts),
            "batch_processed": result.processed,
            "errors": result.errors,
        }
        return result

    def run_accuracy_test(self, sample_size: int = 20) -> AgentResult:
        """Blind accuracy test against existing approved mappings."""
        start = time.time()
        result = AgentResult(agent_id=self.AGENT_ID, status="success", started_at=self.now_iso())

        sql = f"""
        SELECT gl_account, description, dise_category, expense_caption, asc_citation
        FROM `{cfg.PROJECT}.{cfg.DISE_DATASET}.gl_dise_mapping`
        WHERE status = 'mapped' ORDER BY RAND() LIMIT @n
        """
        approved = self.cx.query(sql, [self.cx.param("n", "INT64", sample_size)])
        reference = self.get_approved_mappings()

        correct = 0
        for acc in approved:
            test_account = {"gl_account": acc["gl_account"], "description": acc["description"], "posting_amount": 100000}
            similar = [s for s in self._find_similar(acc["description"] or "", reference)
                       if s["gl_account"] != acc["gl_account"]]

            decision = self._classify(test_account, similar)
            if not decision:
                result.errors += 1
                continue

            match = decision["suggested_category"] == acc["dise_category"]
            if match:
                correct += 1
            result.results.append({
                "gl_account": acc["gl_account"], "approved": acc["dise_category"],
                "predicted": decision["suggested_category"], "match": match,
                "confidence": decision["confidence_label"],
            })
            result.processed += 1
            time.sleep(cfg.API_DELAY)

        accuracy = correct / result.processed if result.processed else 0
        result.completed_at = self.now_iso()
        result.elapsed_seconds = time.time() - start
        result.summary = {"accuracy": round(accuracy, 3), "correct": correct, "total": result.processed}
        result.status = "success" if accuracy >= 0.85 else "warning"
        return result

    # ── Private methods ─────────────────────────────────────

    def _classify(self, account: dict, similar: list[dict]) -> dict | None:
        """Call Claude to classify one account."""
        sim_text = ""
        if similar:
            sim_text = "\n\nSIMILAR APPROVED ACCOUNTS:\n"
            for i, s in enumerate(similar[:5], 1):
                sim_text += f"{i}. {s['gl_account']} — \"{s['description']}\" → {s['dise_category']} ({s['expense_caption']})\n"
        else:
            sim_text = "\n\nNo similar approved accounts. Classify from first principles.\n"

        prompt = f"""Classify this GL account:
  GL: {account['gl_account']}
  Description: {(account.get('description') or '')[:500]}
  FY Amount: ${float(account.get('posting_amount', 0)):,.0f}
{sim_text}
Respond with JSON only."""

        decision = self.call_claude(SYSTEM_PROMPT, prompt, max_tokens=800)
        if not decision or not isinstance(decision, dict):
            return None

        # Validate
        if decision.get("suggested_category") not in VALID_CATEGORIES:
            return None
        if decision.get("suggested_caption") not in VALID_CAPTIONS:
            return None
        score = float(decision.get("confidence_score", 0))
        if not 0.0 <= score <= 1.0:
            return None
        decision["confidence_score"] = score
        return decision

    def _find_similar(self, description: str, reference: list[dict], top_n: int = 5) -> list[dict]:
        """Local Jaccard similarity against approved mappings."""
        if not description:
            return []
        import re
        q_tokens = set(w for w in re.split(r"[-/&,.\s]+", description.lower()) if len(w) > 2)
        if not q_tokens:
            return []

        scored = []
        for ref in reference:
            r_tokens = set(w for w in re.split(r"[-/&,.\s]+", (ref.get("description") or "").lower()) if len(w) > 2)
            if not r_tokens:
                continue
            inter = len(q_tokens & r_tokens)
            union = len(q_tokens | r_tokens)
            if inter > 0:
                scored.append({**ref, "similarity_score": round(inter / union, 3)})

        scored.sort(key=lambda x: x["similarity_score"], reverse=True)
        return scored[:top_n]

    def _write_pending(self, account: dict, decision: dict, similar: list[dict]) -> None:
        """Write draft mapping to pending_mappings table."""
        posting = float(account.get("posting_amount", 0))
        materiality = "HIGH" if posting >= 500000 else "MEDIUM" if posting >= 100000 else "LOW"

        row = {
            "gl_account": account["gl_account"],
            "description": (account.get("description") or "")[:500],
            "posting_amount": posting,
            "fiscal_year": cfg.FISCAL_YEAR,
            "company_code": cfg.COMPANY_CODE,
            "suggested_category": decision["suggested_category"],
            "suggested_caption": decision["suggested_caption"],
            "suggested_citation": decision["suggested_citation"],
            "draft_reasoning": decision["draft_reasoning"][:5000],
            "confidence_score": decision["confidence_score"],
            "confidence_label": decision["confidence_label"],
            "similar_accounts": json.dumps(similar[:5], default=str),
            "materiality_flag": materiality,
            "status": "PENDING",
            "drafted_by": self.AGENT_ID,
            "drafted_at": self.now_iso(),
            "model_version": self.model,
            "prompt_version": "v1.1",
        }
        errors = self.cx.insert_rows(f"{cfg.PROJECT}.{cfg.DISE_DATASET}.pending_mappings", [row])
        if errors:
            raise RuntimeError(f"Insert error: {errors}")
