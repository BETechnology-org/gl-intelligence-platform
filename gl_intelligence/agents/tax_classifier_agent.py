"""
Tax GL Classifier Agent — classifies SAP GL accounts into ASC 740 income tax categories.
Uses Claude AI + similarity matching against approved tax mappings.
Mirrors the DISE MappingAgent pattern but for ASC 740 / ASU 2023-09 compliance.

Pipeline position: Step 2 of 5
  SAP GL Extract → [Claude Classify] → Human Review → ETR Bridge → 10-K Disclosure
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from gl_intelligence.config import cfg
from gl_intelligence.cortex.client import CortexClient
from gl_intelligence.agents.base import BaseAgent, AgentResult
from gl_intelligence.persistence import (
    supabase_available,
    write_audit_event,
)
from gl_intelligence.persistence import tax_store

log = logging.getLogger("agents.tax_classifier")

# ── ASC 740 Tax Categories ──────────────────────────────────────────────────

TAX_CATEGORIES = [
    "current_federal",     # Current income tax expense — US federal
    "current_state",       # Current income tax expense — state & local
    "current_foreign",     # Current income tax expense — foreign jurisdictions
    "deferred_federal",    # Deferred income tax expense — US federal
    "deferred_state",      # Deferred income tax expense — state & local
    "deferred_foreign",    # Deferred income tax expense — foreign jurisdictions
    "deferred_tax_asset",  # Balance sheet deferred tax asset (DTA)
    "deferred_tax_liab",   # Balance sheet deferred tax liability (DTL)
    "pretax_domestic",     # Pre-tax income — domestic operations
    "pretax_foreign",      # Pre-tax income — foreign operations
    "not_tax_account",     # Not an income-tax-related GL account
]

TAX_CATEGORY_LABELS = {
    "current_federal":    "Current Tax — Federal",
    "current_state":      "Current Tax — State/Local",
    "current_foreign":    "Current Tax — Foreign",
    "deferred_federal":   "Deferred Tax — Federal",
    "deferred_state":     "Deferred Tax — State/Local",
    "deferred_foreign":   "Deferred Tax — Foreign",
    "deferred_tax_asset": "Deferred Tax Asset (B/S)",
    "deferred_tax_liab":  "Deferred Tax Liability (B/S)",
    "pretax_domestic":    "Pre-tax Income — Domestic",
    "pretax_foreign":     "Pre-tax Income — Foreign",
    "not_tax_account":    "Not a Tax Account",
}

# ASU 2023-09 disclosure mapping: which ASC 740 table each category feeds
CATEGORY_TO_TABLE = {
    "current_federal":    "Table A — ETR Reconciliation / Table B — Cash Taxes",
    "current_state":      "Table A — ETR Reconciliation / Table B — Cash Taxes",
    "current_foreign":    "Table A — ETR Reconciliation / Table B — Cash Taxes",
    "deferred_federal":   "Table A — ETR Reconciliation",
    "deferred_state":     "Table A — ETR Reconciliation",
    "deferred_foreign":   "Table A — ETR Reconciliation",
    "deferred_tax_asset": "ASC 740-10-50-2 Deferred Schedule",
    "deferred_tax_liab":  "ASC 740-10-50-2 Deferred Schedule",
    "pretax_domestic":    "Table C — Pre-tax Income Split",
    "pretax_foreign":     "Table C — Pre-tax Income Split",
    "not_tax_account":    "Excluded",
}

# ── Offline GL Account Sample (diplomatic75 / C006 / FY2022 proof point) ──
# 18 accounts in SAP GL range 0000160000–0000199999 as specified in terraform tfvars
SAMPLE_TAX_GL_ACCOUNTS = [
    # Current Tax Expense Accounts
    {"gl_account": "0000160000", "description": "Federal Income Tax Expense - Current",
     "posting_amount": 38_400_000, "fiscal_year": "2022", "company_code": "C006",
     "account_type": "expense", "jurisdiction_hint": "federal"},
    {"gl_account": "0000160100", "description": "State and Local Income Tax Expense - Current",
     "posting_amount": 5_180_000, "fiscal_year": "2022", "company_code": "C006",
     "account_type": "expense", "jurisdiction_hint": "state"},
    {"gl_account": "0000160200", "description": "Foreign Income Tax Expense - Ireland (12.5%)",
     "posting_amount": 6_840_000, "fiscal_year": "2022", "company_code": "C006",
     "account_type": "expense", "jurisdiction_hint": "foreign"},
    {"gl_account": "0000160201", "description": "Foreign Income Tax Expense - Singapore (17%)",
     "posting_amount": 4_120_000, "fiscal_year": "2022", "company_code": "C006",
     "account_type": "expense", "jurisdiction_hint": "foreign"},
    {"gl_account": "0000160202", "description": "Foreign Income Tax Expense - Germany (30%)",
     "posting_amount": 3_940_000, "fiscal_year": "2022", "company_code": "C006",
     "account_type": "expense", "jurisdiction_hint": "foreign"},
    {"gl_account": "0000160203", "description": "Foreign Income Tax Expense - Other Jurisdictions",
     "posting_amount": 3_660_000, "fiscal_year": "2022", "company_code": "C006",
     "account_type": "expense", "jurisdiction_hint": "foreign"},
    # Deferred Tax Expense Accounts
    {"gl_account": "0000161000", "description": "Federal Deferred Income Tax Expense (Benefit)",
     "posting_amount": 5_730_000, "fiscal_year": "2022", "company_code": "C006",
     "account_type": "expense", "jurisdiction_hint": "federal"},
    {"gl_account": "0000161100", "description": "State Deferred Income Tax Expense",
     "posting_amount": 1_050_000, "fiscal_year": "2022", "company_code": "C006",
     "account_type": "expense", "jurisdiction_hint": "state"},
    {"gl_account": "0000161200", "description": "Foreign Deferred Income Tax Expense",
     "posting_amount": 5_720_000, "fiscal_year": "2022", "company_code": "C006",
     "account_type": "expense", "jurisdiction_hint": "foreign"},
    # Deferred Tax Asset Balance Sheet Accounts
    {"gl_account": "0000162000", "description": "Deferred Tax Asset - Employee Stock Compensation (ASC 718)",
     "posting_amount": 28_400_000, "fiscal_year": "2022", "company_code": "C006",
     "account_type": "balance_sheet", "jurisdiction_hint": ""},
    {"gl_account": "0000162100", "description": "Deferred Tax Asset - Accrued Compensation and Benefits",
     "posting_amount": 21_600_000, "fiscal_year": "2022", "company_code": "C006",
     "account_type": "balance_sheet", "jurisdiction_hint": ""},
    {"gl_account": "0000162200", "description": "Deferred Tax Asset - State Net Operating Loss Carryforward",
     "posting_amount": 12_600_000, "fiscal_year": "2022", "company_code": "C006",
     "account_type": "balance_sheet", "jurisdiction_hint": "state"},
    {"gl_account": "0000162300", "description": "Deferred Tax Asset - Federal Research and Development Credits",
     "posting_amount": 9_400_000, "fiscal_year": "2022", "company_code": "C006",
     "account_type": "balance_sheet", "jurisdiction_hint": "federal"},
    # Deferred Tax Liability Balance Sheet Accounts
    {"gl_account": "0000163000", "description": "Deferred Tax Liability - Accelerated Depreciation on PP&E",
     "posting_amount": -42_300_000, "fiscal_year": "2022", "company_code": "C006",
     "account_type": "balance_sheet", "jurisdiction_hint": ""},
    {"gl_account": "0000163100", "description": "Deferred Tax Liability - Acquired Intangibles (customer lists, patents)",
     "posting_amount": -18_600_000, "fiscal_year": "2022", "company_code": "C006",
     "account_type": "balance_sheet", "jurisdiction_hint": ""},
    # Pre-tax Income / Earnings Before Tax
    {"gl_account": "0000164000", "description": "Income Before Provision for Income Taxes - Domestic Operations",
     "posting_amount": 198_400_000, "fiscal_year": "2022", "company_code": "C006",
     "account_type": "income", "jurisdiction_hint": "domestic"},
    {"gl_account": "0000164100", "description": "Income Before Provision for Income Taxes - Foreign Operations",
     "posting_amount": 98_200_000, "fiscal_year": "2022", "company_code": "C006",
     "account_type": "income", "jurisdiction_hint": "foreign"},
    # Non-deductible / Special Items
    {"gl_account": "0000165000", "description": "Non-deductible Meals Entertainment and Executive Compensation §162(m)",
     "posting_amount": 744_167, "fiscal_year": "2022", "company_code": "C006",
     "account_type": "expense", "jurisdiction_hint": "federal"},
]

# ── Approved mappings cache (in-memory for offline mode) ────────────────────
_approved_tax_mappings: list[dict] = []
_pending_tax_mappings: list[dict] = []

SYSTEM_PROMPT = """You are the Tax GL Classifier for BE Technology's GL Intelligence Platform.

Classify SAP GL accounts into ASC 740 income tax categories for ASU 2023-09 disclosure.
Your decisions feed directly into the ETR bridge, which produces Tables A, B, and C of
the income tax footnote required in the 10-K filing.

ASC 740 TAX CATEGORIES (use exactly as written):
1. current_federal     — Current federal income tax expense (goes to Table A line 1 and Table B)
2. current_state       — Current state & local income tax expense (Table A and Table B)
3. current_foreign     — Current foreign income tax expense (Table A and Table B)
4. deferred_federal    — Deferred federal income tax expense (Table A deferred section)
5. deferred_state      — Deferred state income tax expense (Table A)
6. deferred_foreign    — Deferred foreign income tax expense (Table A)
7. deferred_tax_asset  — Balance sheet deferred tax asset (DTA schedule, not P&L)
8. deferred_tax_liab   — Balance sheet deferred tax liability (DTL schedule, not P&L)
9. pretax_domestic     — Pre-tax income from domestic operations (Table C)
10. pretax_foreign     — Pre-tax income from foreign operations (Table C)
11. not_tax_account    — Not an income-tax-related account (excluded from disclosure)

KEY RULES:
- Current tax accounts (160000-160299): expense entries for taxes currently due/paid
- Deferred tax expense accounts (161000-161299): timing difference adjustments
- Balance sheet DTA accounts (162000-162999): gross DTA balances before VA
- Balance sheet DTL accounts (163000-163999): gross DTL balances (negative amounts typical)
- Pretax income accounts (164000-164999): earnings before income tax provision
- Non-deductible/special accounts: classify as not_tax_account unless directly a tax account

CONFIDENCE THRESHOLDS:
- HIGH (0.85-1.0): Account description unambiguously maps to one category
- MEDIUM (0.60-0.84): Some interpretation required, likely correct
- LOW (0.0-0.59): Ambiguous — requires controller review before inclusion in filing

Respond ONLY with valid JSON:
{"tax_category":"...","tax_category_label":"...","asc_citation":"...","confidence_score":0.0,"confidence_label":"HIGH|MEDIUM|LOW","disclosure_table":"...","draft_reasoning":"..."}"""


class TaxClassifierAgent(BaseAgent):
    """
    Classifies SAP GL accounts from the tax account range (160000-199999)
    into ASC 740 income tax categories using Claude AI.

    Follows the same pending → approved review workflow as the DISE MappingAgent.
    High-confidence (≥0.80) results auto-approve; below threshold goes to
    pending_tax_mappings for controller review.
    """

    AGENT_ID = "TAX_CLASSIFIER_AGENT_v1"
    DESCRIPTION = "Classifies SAP GL tax accounts into ASC 740 categories for ASU 2023-09 disclosure"

    AUTO_APPROVE_THRESHOLD = 0.80  # matches terraform tax_confidence_threshold

    def run(self, batch_size: int = 18, dry_run: bool = False,
            source: str = "auto", **kwargs) -> AgentResult:
        """
        Main classification loop.

        source: "auto"     — try BigQuery first, fall back to offline sample
                "bigquery"  — live SAP Cortex data (GL range 160000-199999)
                "offline"   — use the 18-account offline sample
        """
        start = time.time()
        result = AgentResult(agent_id=self.AGENT_ID, status="success", started_at=self.now_iso())

        # ── Load accounts ──
        accounts = self._load_accounts(source, batch_size)
        if not accounts:
            result.summary = {"message": "No tax GL accounts found"}
            result.completed_at = self.now_iso()
            result.elapsed_seconds = time.time() - start
            return result

        reference = self._load_approved_reference()
        log.info(f"Classifying {len(accounts)} tax GL accounts | {len(reference)} approved references")

        auto_approved = 0
        pending_review = 0

        for i, account in enumerate(accounts[:batch_size], 1):
            log.info(f"[{i}/{min(len(accounts), batch_size)}] {account['gl_account']} — "
                     f"{(account.get('description') or '')[:60]}")

            similar = self._find_similar(account.get("description", ""), reference)
            decision = self._classify(account, similar)

            if not decision:
                result.errors += 1
                log.warning(f"  -> Classification failed for {account['gl_account']}")
                continue

            score = decision["confidence_score"]
            status = "approved" if score >= self.AUTO_APPROVE_THRESHOLD else "pending"

            log.info(f"  -> {decision['tax_category']} | {decision['confidence_label']} "
                     f"({score:.0%}) | {status.upper()}")

            entry = {
                **account,
                **decision,
                "status": status,
                "drafted_by": self.AGENT_ID,
                "drafted_at": self.now_iso(),
                "model_version": self.model,
            }

            if dry_run:
                result.results.append(entry)
                result.processed += 1
                if status == "approved":
                    auto_approved += 1
                else:
                    pending_review += 1
                continue

            # Write to appropriate store. Supabase is the durable backing
            # store when SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY are set;
            # the in-memory list is the legacy fallback.
            if status == "approved":
                _approved_tax_mappings.append(entry)
                auto_approved += 1
            else:
                _pending_tax_mappings.append(entry)
                pending_review += 1
                if supabase_available():
                    tax_store.write_pending(entry)

            result.results.append(entry)
            result.processed += 1

            time.sleep(cfg.API_DELAY)

        result.completed_at = self.now_iso()
        result.elapsed_seconds = time.time() - start
        result.summary = {
            "total_accounts": len(accounts),
            "classified": result.processed,
            "auto_approved": auto_approved,
            "pending_review": pending_review,
            "errors": result.errors,
            "avg_confidence": round(
                sum(r["confidence_score"] for r in result.results if "confidence_score" in r)
                / max(result.processed, 1), 3
            ),
            "threshold": self.AUTO_APPROVE_THRESHOLD,
            "dry_run": dry_run,
        }
        return result

    def get_pending_tax_mappings(self) -> list[dict]:
        """Returns all pending tax GL mappings awaiting controller review.

        Resolution order:
          1. Supabase  — durable, survives Cloud Run restarts.
          2. BigQuery  — legacy demo dataset (Max's 86-account fixture).
          3. In-memory — last-resort fallback when neither is available.
        """
        if supabase_available():
            rows = tax_store.get_pending(limit=50)
            if rows:
                return rows
        if self.cx.available:
            try:
                sql = f"""
                SELECT * FROM `{cfg.PROJECT}.{cfg.DISE_DATASET}.tax_pending_mappings`
                WHERE status = 'pending'
                ORDER BY ABS(posting_amount) DESC
                LIMIT 50
                """
                rows = self.cx.query(sql)
                if rows:
                    return rows
            except Exception:
                pass
        return [m for m in _pending_tax_mappings if m.get("status") == "pending"]

    def get_approved_tax_mappings(self) -> list[dict]:
        """Returns all approved tax GL mappings."""
        if supabase_available():
            rows = tax_store.get_approved(limit=200)
            if rows:
                return rows
        if self.cx.available:
            try:
                sql = f"""
                SELECT * FROM `{cfg.PROJECT}.{cfg.DISE_DATASET}.tax_gl_mapping`
                WHERE status IN ('approved', 'promoted')
                ORDER BY gl_account
                LIMIT 100
                """
                rows = self.cx.query(sql)
                if rows:
                    return rows
            except Exception:
                pass
        return [m for m in _approved_tax_mappings]

    def approve_mapping(self, gl_account: str, reviewer: str = "controller",
                        override_category: str | None = None,
                        override_reason: str | None = None) -> bool:
        """Move a pending mapping to approved. Optionally override the AI category."""
        if supabase_available():
            ok = tax_store.approve(
                gl_account,
                reviewer=reviewer,
                override_category=override_category,
                override_reason=override_reason,
            )
            if ok:
                log.info(f"Approved tax mapping (supabase): {gl_account}")
                return True

        # Legacy in-memory fallback
        for m in _pending_tax_mappings:
            if m["gl_account"] == gl_account and m.get("status") == "pending":
                m["status"] = "approved"
                m["reviewed_by"] = reviewer
                m["reviewed_at"] = self.now_iso()
                if override_category and override_category in TAX_CATEGORIES:
                    m["tax_category"] = override_category
                    m["tax_category_label"] = TAX_CATEGORY_LABELS.get(override_category, override_category)
                    m["disclosure_table"] = CATEGORY_TO_TABLE.get(override_category, "")
                _approved_tax_mappings.append(m)
                write_audit_event(
                    module="tax",
                    event_type="HUMAN_OVERRIDDEN" if override_category else "HUMAN_APPROVED",
                    actor=reviewer, actor_type="HUMAN",
                    gl_account=gl_account,
                    payload={"agent_category": m.get("tax_category"),
                             "final_category": m.get("tax_category"),
                             "override_reason": override_reason},
                )
                log.info(f"Approved tax mapping (in-memory): {gl_account} → {m['tax_category']}")
                return True
        return False

    def reject_mapping(self, gl_account: str, reviewer: str = "controller",
                       reason: str = "") -> bool:
        """Reject a pending mapping."""
        if supabase_available():
            ok = tax_store.reject(gl_account, reviewer=reviewer, reason=reason)
            if ok:
                log.info(f"Rejected tax mapping (supabase): {gl_account}")
                return True

        # Legacy in-memory fallback
        for m in _pending_tax_mappings:
            if m["gl_account"] == gl_account and m.get("status") == "pending":
                m["status"] = "rejected"
                m["reviewed_by"] = reviewer
                m["reviewed_at"] = self.now_iso()
                m["rejection_reason"] = reason
                log.info(f"Rejected tax mapping: {gl_account}")
                return True
        return False

    def get_all_accounts(self) -> list[dict]:
        """Returns all 18 sample tax GL accounts (unclassified)."""
        return SAMPLE_TAX_GL_ACCOUNTS[:]

    # ── Private methods ──────────────────────────────────────

    def _load_accounts(self, source: str, batch_size: int) -> list[dict]:
        """Load GL accounts from BigQuery or offline sample."""
        use_offline = source == "offline" or (source == "auto" and not self.cx.available)

        if not use_offline and source in ("bigquery", "auto"):
            try:
                gl_start = cfg.__dict__.get("TAX_GL_RANGE_START", "0000160000")
                gl_end = cfg.__dict__.get("TAX_GL_RANGE_END", "0000199999")
                sql = f"""
                SELECT
                  b.HKONT AS gl_account,
                  a.BKTXT AS description,
                  SUM(b.WRBTR) AS posting_amount,
                  a.GJAHR AS fiscal_year,
                  a.BUKRS AS company_code
                FROM `{cfg.PROJECT}.{cfg.SAP_CDC_DATASET}.bkpf` a
                JOIN `{cfg.PROJECT}.{cfg.SAP_CDC_DATASET}.bseg` b
                  ON a.MANDT = b.MANDT AND a.BUKRS = b.BUKRS
                  AND a.BELNR = b.BELNR AND a.GJAHR = b.GJAHR
                WHERE a.BUKRS = @company_code
                  AND a.GJAHR = @fiscal_year
                  AND b.HKONT BETWEEN @gl_start AND @gl_end
                GROUP BY b.HKONT, a.BKTXT, a.GJAHR, a.BUKRS
                ORDER BY ABS(SUM(b.WRBTR)) DESC
                LIMIT {batch_size}
                """
                rows = self.cx.query(sql, [
                    self.cx.param("company_code", "STRING", cfg.COMPANY_CODE),
                    self.cx.param("fiscal_year", "STRING", cfg.FISCAL_YEAR),
                    self.cx.param("gl_start", "STRING", "0000160000"),
                    self.cx.param("gl_end", "STRING", "0000199999"),
                ])
                if rows:
                    log.info(f"Loaded {len(rows)} tax accounts from BigQuery")
                    return rows
            except Exception as e:
                log.warning(f"BigQuery load failed: {e}, falling back to offline sample")

        log.info(f"Using offline sample: {len(SAMPLE_TAX_GL_ACCOUNTS)} accounts")
        return SAMPLE_TAX_GL_ACCOUNTS[:]

    def _load_approved_reference(self) -> list[dict]:
        """Load approved tax mappings as reference for similarity matching."""
        approved = self.get_approved_tax_mappings()
        if approved:
            return approved
        # Seed with the most obvious accounts as bootstrap reference
        bootstrap = [
            {"gl_account": "0000160000", "description": "Federal Income Tax Expense Current",
             "tax_category": "current_federal", "confidence_label": "HIGH"},
            {"gl_account": "0000163000", "description": "Deferred Tax Liability Accelerated Depreciation",
             "tax_category": "deferred_tax_liab", "confidence_label": "HIGH"},
            {"gl_account": "0000164000", "description": "Income Before Income Taxes Domestic",
             "tax_category": "pretax_domestic", "confidence_label": "HIGH"},
        ]
        return bootstrap

    def _classify(self, account: dict, similar: list[dict]) -> dict | None:
        """Call Claude to classify one tax GL account."""
        sim_text = "\n\nSIMILAR APPROVED TAX ACCOUNTS:\n" if similar else "\n\nNo similar approved tax accounts found.\n"
        for i, s in enumerate(similar[:5], 1):
            sim_text += (f"{i}. {s['gl_account']} — \"{s.get('description','')}\" "
                         f"→ {s.get('tax_category','')} ({s.get('confidence_label','')})\n")

        prompt = f"""Classify this SAP GL account into an ASC 740 income tax category:

GL Account: {account['gl_account']}
Description: {(account.get('description') or '')[:500]}
SAP Account Type: {account.get('account_type', 'unknown')}
Jurisdiction Hint: {account.get('jurisdiction_hint', 'none')}
FY Amount: ${float(account.get('posting_amount', 0)):,.0f}
{sim_text}
Respond with JSON only. Provide a specific ASC citation (e.g. ASC 740-10-50-9, ASC 740-10-50-2)."""

        decision = self.call_claude(SYSTEM_PROMPT, prompt, max_tokens=600)
        if not decision or not isinstance(decision, dict):
            return None

        # Validate
        if decision.get("tax_category") not in TAX_CATEGORIES:
            log.warning(f"Invalid tax_category: {decision.get('tax_category')}")
            return None

        score = float(decision.get("confidence_score", 0))
        if not 0.0 <= score <= 1.0:
            return None

        decision["confidence_score"] = score
        decision["tax_category_label"] = TAX_CATEGORY_LABELS.get(decision["tax_category"], decision["tax_category"])
        decision["disclosure_table"] = CATEGORY_TO_TABLE.get(decision["tax_category"], "")
        return decision

    def _find_similar(self, description: str, reference: list[dict], top_n: int = 3) -> list[dict]:
        """Jaccard similarity against approved tax mappings."""
        if not description:
            return []
        import re
        q_tokens = set(w for w in re.split(r"[-/&,.\s]+", description.lower()) if len(w) > 2)
        if not q_tokens:
            return []

        scored = []
        for ref in reference:
            r_desc = ref.get("description", "")
            r_tokens = set(w for w in re.split(r"[-/&,.\s]+", r_desc.lower()) if len(w) > 2)
            if not r_tokens:
                continue
            inter = len(q_tokens & r_tokens)
            union = len(q_tokens | r_tokens)
            if inter > 0:
                scored.append({**ref, "similarity_score": round(inter / union, 3)})

        scored.sort(key=lambda x: x["similarity_score"], reverse=True)
        return scored[:top_n]
