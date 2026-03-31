"""
BE Technology — GL Intelligence Platform
Autonomous GL Mapping Agent v1.1
─────────────────────────────────────────
Orchestrates the end-to-end mapping pipeline:
  1. Query unmapped GL accounts from BigQuery
  2. For each account, find 5 similar approved accounts
  3. Call Claude with account + similar accounts + ASC context
  4. Parse and validate structured response
  5. Write draft to pending_mappings
  6. Write event to mapping_decisions_log

Prerequisites:
  pip install anthropic google-cloud-bigquery

Environment variables required:
  ANTHROPIC_API_KEY    — your Anthropic API key
  GOOGLE_CLOUD_PROJECT — GCP project ID (default: diplomatic75)
  BQ_DATASET           — BigQuery dataset (default: dise_reporting)
  BQ_CDC_DATASET       — SAP CDC dataset (default: CORTEX_SAP_CDC)
  COMPANY_CODE         — SAP company code (default: C006)
  FISCAL_YEAR          — fiscal year to process (default: 2023)
"""

from __future__ import annotations

import os
import json
import re
import sys
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

import anthropic
from google.cloud import bigquery

# ── Configuration ──────────────────────────────────────────────
PROJECT       = os.environ.get('GOOGLE_CLOUD_PROJECT', 'diplomatic75')
DATASET       = os.environ.get('BQ_DATASET',           'dise_reporting')
CDC_DATASET   = os.environ.get('BQ_CDC_DATASET',       'CORTEX_SAP_CDC')
COMPANY_CODE  = os.environ.get('COMPANY_CODE',         'C006')
FISCAL_YEAR   = os.environ.get('FISCAL_YEAR',          '2023')
AGENT_ID      = 'GL_MAPPING_AGENT_v1'
MODEL         = os.environ.get('CLAUDE_MODEL',         'claude-sonnet-4-20250514')
PROMPT_VER    = 'v1.1'

# Materiality thresholds (USD) — configurable via env vars
HIGH_MATERIALITY   = int(os.environ.get('HIGH_MATERIALITY',   '500000'))
MEDIUM_MATERIALITY = int(os.environ.get('MEDIUM_MATERIALITY', '100000'))

# Rate limiting — seconds between Claude API calls
API_DELAY_SECONDS = float(os.environ.get('API_DELAY_SECONDS', '0.5'))

# Max retries on transient API failures
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '2'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
)
log = logging.getLogger('gl-mapping-agent')

# ── Valid values (single source of truth) ─────────────────────
VALID_CATEGORIES = [
    'Purchases of inventory',
    'Employee compensation',
    'Depreciation',
    'Intangible asset amortization',
    'Other expenses',
]

VALID_CAPTIONS = ['COGS', 'SG&A', 'R&D', 'Other income/expense']

VALID_CONFIDENCE_LABELS = ['HIGH', 'MEDIUM', 'LOW']


# ── Clients (lazy-initialized for better error messages) ──────
def _init_bq() -> bigquery.Client:
    try:
        return bigquery.Client(project=PROJECT)
    except Exception as e:
        log.error(f"Failed to initialize BigQuery client: {e}")
        log.error("Check GOOGLE_CLOUD_PROJECT and GCP credentials.")
        raise SystemExit(1)


def _init_claude() -> anthropic.Anthropic:
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        log.error("ANTHROPIC_API_KEY environment variable is not set.")
        raise SystemExit(1)
    return anthropic.Anthropic(api_key=api_key)


bq: bigquery.Client = _init_bq()
claude: anthropic.Anthropic = _init_claude()


# ══════════════════════════════════════════════════════════════
# SECTION 1 — THE MAPPING AGENT PROMPT
# ══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are the GL Mapping Agent for BE Technology's GL Intelligence Platform.

Your job is to classify General Ledger accounts from SAP ECC into the five natural expense
categories required by ASU 2024-03 (DISE) under ASC 220-40. Your decisions will be reviewed
and approved by a qualified Controller or Senior Accountant before being used in any SEC filing.

You are an AI assistant and may make errors. When uncertain, be transparent about your
uncertainty and set your confidence score accordingly. A LOW confidence classification that
prompts human review is far more valuable than a HIGH confidence classification that is wrong.

═══════════════════════════════════════════════════════════
THE FIVE DISE CATEGORIES — EXACT NAMES AND ASC CITATIONS
═══════════════════════════════════════════════════════════

1. Purchases of inventory
   ASC 220-40-50-6(b)
   Includes: cost of goods purchased for resale, raw materials, direct materials
   Excludes: labour costs, overhead allocations, depreciation of manufacturing equipment
   Caption: almost always COGS

2. Employee compensation
   ASC 220-40-50-6(a)
   Includes: salaries, wages, bonuses, commissions, payroll taxes, benefits, pension expense,
             stock-based compensation, severance, recruitment fees, training costs,
             travel and entertainment (when primarily for employees)
   Excludes: payments to contractors/vendors who are not employees
   Caption: COGS if production labour, SG&A if selling/admin labour, R&D if R&D staff

3. Depreciation
   ASC 220-40-50-6(c)
   Includes: depreciation of TANGIBLE fixed assets — buildings, machinery, equipment,
             vehicles, computers/hardware, furniture, leasehold improvements,
             right-of-use assets under ASC 842
   Excludes: amortization of INTANGIBLE assets (that is category 4)
   CRITICAL DISTINCTION: Computer HARDWARE = Depreciation. Computer SOFTWARE = Amortization.
   Caption: COGS if manufacturing/production asset, SG&A if office/admin asset

4. Intangible asset amortization
   ASC 220-40-50-6(d)
   Includes: amortization of intangible assets — patents, trademarks, customer relationships,
             trade names, non-compete agreements, developed technology, computer software
             (both purchased and internally developed under ASC 350-40),
             goodwill impairment (if applicable)
   Excludes: depreciation of any tangible asset
   Caption: almost always SG&A

5. Other expenses
   ASC 220-40-50-6(e)
   Includes: everything that does not fit categories 1-4 — rent expense, utilities,
             insurance, professional fees, marketing, advertising, R&D costs,
             bad debt expense, foreign exchange losses, bank fees, miscellaneous
   Caption: COGS, SG&A, R&D, or Other income/expense depending on function

═══════════════════════════════════════════════════════════
COMMON EDGE CASES — DECISION RULES
═══════════════════════════════════════════════════════════
- Software development labour → Employee compensation (the person is an employee), NOT Other
- Contractor/outsourced services → Other expenses (not an employee)
- Operating lease payments (ASC 842) → Other expenses (not depreciation of a tangible asset you own)
- Right-of-use asset depreciation → Depreciation (ASC 842 creates a tangible ROU asset)
- Capitalized internal-use software amortization → Intangible asset amortization (ASC 350-40)
- R&D materials consumed → Other expenses with R&D caption (unless inventoriable)
- Freight-in on purchases → Purchases of inventory (part of inventory cost under ASC 330)
- Temporary staffing agencies → Other expenses (they are not your employees)
- If genuinely uncertain between two categories → pick the more conservative choice, set LOW confidence, and explain the ambiguity in reasoning

═══════════════════════════════════════════════════════════
INCOME STATEMENT CAPTIONS — VALID VALUES
═══════════════════════════════════════════════════════════
- COGS              (cost of goods sold / cost of revenues)
- SG&A              (selling, general and administrative)
- R&D               (research and development)
- Other income/expense

═══════════════════════════════════════════════════════════
ASC CITATION REFERENCE
═══════════════════════════════════════════════════════════
ASC 220-40-50-6(a)  Employee compensation
ASC 220-40-50-6(b)  Purchases of inventory
ASC 220-40-50-6(c)  Depreciation
ASC 220-40-50-6(d)  Intangible asset amortization
ASC 220-40-50-6(e)  Other expenses (catch-all)
ASC 350-40          Internal-use software (→ amortization)
ASC 842             Right-of-use asset depreciation (→ depreciation)
ASC 730             Research and development costs

═══════════════════════════════════════════════════════════
CONFIDENCE SCORING RULES
═══════════════════════════════════════════════════════════
HIGH   (0.85–1.0):  Account description unambiguously matches one category.
                    Supported by at least one similar approved account with
                    the same category. You are certain of the classification.
                    Example: "Raw Material Purchases" → Purchases of inventory.

MEDIUM (0.60–0.84): Account description likely matches a category but there is
                    some ambiguity — e.g. could be compensation OR other expenses,
                    or the similar accounts suggest a different category.
                    Human should review carefully.
                    Example: "Temporary Help Services" → could be compensation or other.

LOW    (0.0–0.59):  Account description is ambiguous, novel, or contradicts
                    similar accounts. The human MUST investigate before approving.
                    Explain exactly what is uncertain in your reasoning.
                    Example: "Misc Expense Allocation" → insufficient detail to classify.

═══════════════════════════════════════════════════════════
OUTPUT FORMAT — CRITICAL
═══════════════════════════════════════════════════════════
Respond ONLY with a valid JSON object. No preamble, no explanation outside the JSON.
No markdown code blocks. Raw JSON only.

{
  "suggested_category": "<exact category name from the five above>",
  "suggested_caption": "<COGS | SG&A | R&D | Other income/expense>",
  "suggested_citation": "<ASC citation e.g. ASC 220-40-50-6(c)>",
  "confidence_score": <float 0.0-1.0>,
  "confidence_label": "<HIGH | MEDIUM | LOW>",
  "draft_reasoning": "<Full reasoning paragraph. Explain: (1) why you chose this category, (2) what ASC provision supports it, (3) how the similar accounts informed your decision, (4) any ambiguities or edge cases the reviewer should consider. Write as if explaining to a Controller who will sign off on this for an SEC filing. Minimum 3 sentences.>"
}
"""


def build_user_prompt(account: dict, similar: list[dict]) -> str:
    """Build the per-account prompt combining account data with similar references."""
    similar_text = ""
    if similar:
        similar_text = "\n\nSIMILAR APPROVED ACCOUNTS (use as reference):\n"
        for i, s in enumerate(similar, 1):
            similar_text += (
                f"{i}. GL {s['gl_account']} — \"{s['description']}\"\n"
                f"   Category: {s['dise_category']} | Caption: {s['expense_caption']}\n"
                f"   Citation: {s['asc_citation']} | Similarity: {s['similarity_score']:.3f}\n"
            )
    else:
        similar_text = (
            "\n\nSIMILAR APPROVED ACCOUNTS: None found — classify from first principles "
            "using the category definitions and edge case rules above.\n"
        )

    description = (account.get('description') or account.get('gl_account', 'Unknown'))[:500]
    posting = float(account.get('posting_amount', 0))

    return f"""Classify this GL account into one of the five DISE natural expense categories.

ACCOUNT TO CLASSIFY:
  GL Account:   {account['gl_account']}
  Description:  {description}
  FY{FISCAL_YEAR} Postings: ${posting:,.0f}
  Company Code: {COMPANY_CODE}
{similar_text}
Respond with JSON only."""


# ══════════════════════════════════════════════════════════════
# SECTION 2 — BIGQUERY QUERIES
# ══════════════════════════════════════════════════════════════

def get_unmapped_accounts() -> list[dict]:
    """
    Returns all P&L accounts that have fiscal year postings but are NOT
    in gl_dise_mapping and NOT already in pending_mappings.

    Uses parameterized queries for FISCAL_YEAR and COMPANY_CODE to
    prevent SQL injection.
    """
    sql = f"""
    SELECT
      bseg.HKONT                    AS gl_account,
      COALESCE(skat.TXT50, skat.TXT20, bseg.HKONT) AS description,
      ROUND(SUM(bseg.DMBTR), 0)     AS posting_amount
    FROM `{PROJECT}.{CDC_DATASET}.bkpf` bkpf
    JOIN `{PROJECT}.{CDC_DATASET}.bseg` bseg
      ON  bkpf.MANDT  = bseg.MANDT
      AND bkpf.BUKRS  = bseg.BUKRS
      AND bkpf.BELNR  = bseg.BELNR
      AND bkpf.GJAHR  = bseg.GJAHR
    JOIN `{PROJECT}.{CDC_DATASET}.ska1` ska1
      ON  bseg.HKONT  = ska1.SAKNR
      AND bseg.MANDT  = ska1.MANDT
      AND ska1.ktopl  = 'CA01'
    LEFT JOIN `{PROJECT}.{CDC_DATASET}.skat` skat
      ON  bseg.HKONT  = skat.SAKNR
      AND bseg.MANDT  = skat.MANDT
      AND skat.ktopl  = 'CA01'
      AND skat.SPRAS  = 'E'
    LEFT JOIN `{PROJECT}.{DATASET}.gl_dise_mapping` m
      ON  bseg.HKONT  = m.gl_account
    LEFT JOIN `{PROJECT}.{DATASET}.pending_mappings` p
      ON  bseg.HKONT  = p.gl_account
      AND p.fiscal_year = @fiscal_year
      AND p.status IN ('PENDING', 'APPROVED')
    WHERE bkpf.GJAHR   = @fiscal_year
      AND bkpf.BUKRS   = @company_code
      AND bkpf.BLART   NOT IN ('AA', 'AF', 'AB')
      AND (ska1.xbilk = '' OR ska1.xbilk IS NULL)
      AND m.gl_account IS NULL
      AND p.gl_account IS NULL
    GROUP BY 1, 2
    HAVING SUM(bseg.DMBTR) > 0
    ORDER BY posting_amount DESC
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter('fiscal_year',  'STRING', FISCAL_YEAR),
            bigquery.ScalarQueryParameter('company_code', 'STRING', COMPANY_CODE),
        ]
    )
    rows = list(bq.query(sql, job_config=job_config).result())
    accounts = [dict(r) for r in rows]
    log.info(f"Found {len(accounts)} unmapped accounts")
    return accounts


def get_similar_accounts(description: str) -> list[dict]:
    """
    Finds up to 5 most similar approved accounts using word overlap (Jaccard similarity).
    This is the reference library the agent uses for every decision.
    """
    if not description or not description.strip():
        return []

    sql = f"""
    WITH
    test_words AS (
      SELECT DISTINCT word
      FROM UNNEST(
        SPLIT(LOWER(REGEXP_REPLACE(@description, r'[-/&,.]', ' ')), ' ')
      ) AS word
      WHERE LENGTH(TRIM(word)) > 2
    ),
    approved_tokens AS (
      SELECT
        gl_account,
        description,
        dise_category,
        expense_caption,
        asc_citation,
        LOWER(REGEXP_REPLACE(description, r'[-/&,.]', ' ')) AS desc_clean
      FROM `{PROJECT}.{DATASET}.gl_dise_mapping`
      WHERE status = 'mapped'
        AND description IS NOT NULL
        AND LENGTH(TRIM(description)) > 0
    ),
    test_word_count AS (
      SELECT COUNT(DISTINCT word) AS cnt FROM test_words
    ),
    scored AS (
      SELECT
        a.gl_account,
        a.description,
        a.dise_category,
        a.expense_caption,
        a.asc_citation,
        a.desc_clean,
        COUNT(DISTINCT t.word)  AS matching_words,
        MAX(twc.cnt)            AS test_word_cnt,
        ARRAY_LENGTH(
          SPLIT(TRIM(REGEXP_REPLACE(a.desc_clean, r'\\s+', ' ')), ' ')
        ) AS account_word_cnt
      FROM approved_tokens a
      CROSS JOIN test_words t
      CROSS JOIN test_word_count twc
      WHERE STRPOS(a.desc_clean, t.word) > 0
      GROUP BY 1,2,3,4,5,6
    )
    SELECT
      gl_account,
      description,
      dise_category,
      expense_caption,
      asc_citation,
      matching_words,
      ROUND(
        matching_words / GREATEST(test_word_cnt + account_word_cnt - matching_words, 1),
        3
      ) AS similarity_score
    FROM scored
    WHERE matching_words > 0
    ORDER BY similarity_score DESC, matching_words DESC
    LIMIT 5
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter('description', 'STRING', description)
        ]
    )
    try:
        rows = list(bq.query(sql, job_config=job_config).result())
        return [dict(r) for r in rows]
    except Exception as e:
        log.warning(f"Similar accounts query failed: {e}")
        return []


def write_pending_mapping(account: dict, decision: dict, similar: list[dict]) -> None:
    """Inserts a draft mapping into pending_mappings."""
    posting = float(account.get('posting_amount', 0))
    materiality = (
        'HIGH'   if posting >= HIGH_MATERIALITY   else
        'MEDIUM' if posting >= MEDIUM_MATERIALITY else
        'LOW'
    )
    # Truncate similar_accounts JSON to prevent BigQuery field overflow
    similar_json = json.dumps(similar, default=str)
    if len(similar_json) > 50_000:
        similar_json = json.dumps(similar[:3], default=str)

    row = {
        'gl_account':         account['gl_account'],
        'description':        (account.get('description') or '')[:500],
        'posting_amount':     posting,
        'fiscal_year':        FISCAL_YEAR,
        'company_code':       COMPANY_CODE,
        'suggested_category': decision['suggested_category'],
        'suggested_caption':  decision['suggested_caption'],
        'suggested_citation': decision['suggested_citation'],
        'draft_reasoning':    decision['draft_reasoning'][:5000],
        'confidence_score':   float(decision['confidence_score']),
        'confidence_label':   decision['confidence_label'],
        'similar_accounts':   similar_json,
        'materiality_flag':   materiality,
        'status':             'PENDING',
        'drafted_by':         AGENT_ID,
        'drafted_at':         datetime.now(timezone.utc).isoformat(),
        'model_version':      MODEL,
        'prompt_version':     PROMPT_VER,
    }
    errors = bq.insert_rows_json(
        f'{PROJECT}.{DATASET}.pending_mappings', [row]
    )
    if errors:
        raise RuntimeError(f"BigQuery insert error for {account['gl_account']}: {errors}")


def write_audit_log(account: dict, decision: dict, event_type: str = 'AGENT_DRAFT') -> None:
    """Writes an immutable event to mapping_decisions_log."""
    row = {
        'event_id':          str(uuid.uuid4()),
        'event_type':        event_type,
        'event_timestamp':   datetime.now(timezone.utc).isoformat(),
        'gl_account':        account['gl_account'],
        'description':       (account.get('description') or '')[:500],
        'fiscal_year':       FISCAL_YEAR,
        'company_code':      COMPANY_CODE,
        'posting_amount':    float(account.get('posting_amount', 0)),
        'agent_category':    decision['suggested_category'],
        'agent_caption':     decision['suggested_caption'],
        'agent_citation':    decision['suggested_citation'],
        'agent_confidence':  float(decision['confidence_score']),
        'agent_reasoning':   decision['draft_reasoning'][:5000],
        'actor':             AGENT_ID,
        'actor_type':        'AGENT',
        'model_version':     MODEL,
        'prompt_version':    PROMPT_VER,
    }
    errors = bq.insert_rows_json(
        f'{PROJECT}.{DATASET}.mapping_decisions_log', [row]
    )
    if errors:
        raise RuntimeError(f"Audit log insert error for {account['gl_account']}: {errors}")


# ══════════════════════════════════════════════════════════════
# SECTION 3 — CLAUDE API CALL
# ══════════════════════════════════════════════════════════════

def _strip_markdown_fences(raw: str) -> str:
    """Robustly strip markdown code fences from Claude's response."""
    raw = raw.strip()
    if raw.startswith('```'):
        parts = raw.split('```')
        # Extract content between first pair of fences
        if len(parts) >= 3:
            inner = parts[1]
        else:
            inner = parts[1] if len(parts) > 1 else raw
        # Remove optional language identifier (e.g. "json\n")
        inner = re.sub(r'^[a-zA-Z]*\n?', '', inner, count=1)
        return inner.strip()
    return raw


def _validate_decision(decision: dict) -> None:
    """Validate all fields in the agent's decision. Raises ValueError on failure."""
    # Check required fields
    required = [
        'suggested_category', 'suggested_caption',
        'suggested_citation', 'confidence_score',
        'confidence_label', 'draft_reasoning',
    ]
    missing = [f for f in required if f not in decision]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    # Validate category
    if decision['suggested_category'] not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category: '{decision['suggested_category']}'. "
            f"Must be one of: {VALID_CATEGORIES}"
        )

    # Validate caption
    if decision['suggested_caption'] not in VALID_CAPTIONS:
        raise ValueError(
            f"Invalid caption: '{decision['suggested_caption']}'. "
            f"Must be one of: {VALID_CAPTIONS}"
        )

    # Validate confidence label
    if decision['confidence_label'] not in VALID_CONFIDENCE_LABELS:
        raise ValueError(
            f"Invalid confidence label: '{decision['confidence_label']}'. "
            f"Must be one of: {VALID_CONFIDENCE_LABELS}"
        )

    # Validate confidence score range
    score = float(decision['confidence_score'])
    if not 0.0 <= score <= 1.0:
        raise ValueError(
            f"Confidence score {score} out of range. Must be 0.0-1.0."
        )
    decision['confidence_score'] = score  # ensure float

    # Validate reasoning is substantive
    reasoning = decision.get('draft_reasoning', '')
    if len(reasoning.strip()) < 50:
        raise ValueError(
            f"Reasoning too short ({len(reasoning)} chars). "
            "Must be at least 50 characters with substantive explanation."
        )


def call_mapping_agent(account: dict, similar: list[dict]) -> Optional[dict]:
    """
    Calls Claude with the account description and similar approved accounts.
    Returns parsed and validated JSON decision, or None if all retries fail.
    Includes retry logic for transient API failures.
    """
    user_prompt = build_user_prompt(account, similar)
    raw = ''

    for attempt in range(1, MAX_RETRIES + 2):  # +2 because range is exclusive and we start at 1
        try:
            response = claude.messages.create(
                model=MODEL,
                max_tokens=800,
                system=SYSTEM_PROMPT,
                messages=[{'role': 'user', 'content': user_prompt}],
                timeout=30.0,
            )
            raw = response.content[0].text.strip()
            raw = _strip_markdown_fences(raw)

            decision = json.loads(raw)
            _validate_decision(decision)
            return decision

        except anthropic.APIConnectionError as e:
            log.warning(f"  API connection error (attempt {attempt}): {e}")
            if attempt <= MAX_RETRIES:
                time.sleep(2 ** attempt)
                continue
            return None

        except anthropic.RateLimitError as e:
            log.warning(f"  Rate limited (attempt {attempt}): {e}")
            if attempt <= MAX_RETRIES:
                time.sleep(5 * attempt)
                continue
            return None

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            log.error(
                f"  Validation error for {account['gl_account']} "
                f"(attempt {attempt}): {e}"
            )
            if attempt <= MAX_RETRIES:
                time.sleep(1)
                continue
            log.error(f"  Raw response (truncated): {raw[:500]}")
            return None

        except Exception as e:
            log.error(f"  Unexpected error for {account['gl_account']}: {type(e).__name__}: {e}")
            return None


# ══════════════════════════════════════════════════════════════
# SECTION 4 — BLIND ACCURACY TEST
# Run this BEFORE deploying against real unmapped accounts.
# Tests the agent against already-mapped accounts.
# Target: 85%+ agreement on category for HIGH confidence decisions.
# ══════════════════════════════════════════════════════════════

def run_accuracy_test(sample_size: int = 20) -> dict:
    """
    Blind accuracy test against existing approved mappings.
    Hides the approved category and asks the agent to classify from scratch.
    Measures agreement between agent suggestion and human-approved category.
    """
    if sample_size < 1:
        log.error("sample_size must be >= 1")
        return {}

    log.info(f"Running blind accuracy test on {sample_size} accounts...")

    sql = f"""
    SELECT gl_account, description, dise_category, expense_caption, asc_citation
    FROM `{PROJECT}.{DATASET}.gl_dise_mapping`
    WHERE status = 'mapped'
    ORDER BY RAND()
    LIMIT @sample_size
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter('sample_size', 'INT64', sample_size),
        ]
    )
    approved = [dict(r) for r in bq.query(sql, job_config=job_config).result()]

    if not approved:
        log.warning("No approved mappings found for accuracy test.")
        return {'total': 0, 'error': 'No approved mappings found'}

    results = {
        'total': len(approved),
        'correct_category': 0,
        'correct_caption': 0,
        'high_confidence_correct': 0,
        'high_confidence_total': 0,
        'errors': 0,
        'details': [],
    }

    for acc in approved:
        test_account = {
            'gl_account':     acc['gl_account'],
            'description':    acc['description'],
            'posting_amount': 100_000,  # dummy amount for test
        }

        # Get similar accounts — exclude the test account itself
        similar = [
            s for s in get_similar_accounts(acc['description'] or '')
            if s['gl_account'] != acc['gl_account']
        ]

        decision = call_mapping_agent(test_account, similar)
        if not decision:
            results['errors'] += 1
            continue

        cat_match     = decision['suggested_category'] == acc['dise_category']
        caption_match = decision['suggested_caption']  == acc['expense_caption']

        if cat_match:
            results['correct_category'] += 1
        if caption_match:
            results['correct_caption'] += 1
        if decision['confidence_label'] == 'HIGH':
            results['high_confidence_total'] += 1
            if cat_match:
                results['high_confidence_correct'] += 1

        results['details'].append({
            'gl_account':        acc['gl_account'],
            'description':       acc['description'],
            'approved_category': acc['dise_category'],
            'agent_category':    decision['suggested_category'],
            'agent_caption':     decision['suggested_caption'],
            'confidence':        decision['confidence_label'],
            'confidence_score':  decision['confidence_score'],
            'category_match':    cat_match,
            'caption_match':     caption_match,
        })

        status = 'MATCH' if cat_match else 'MISMATCH'
        log.info(
            f"  [{status}] {acc['gl_account']} "
            f"| Approved: {acc['dise_category'][:25]:25} "
            f"| Agent: {decision['suggested_category'][:25]:25} "
            f"| Conf: {decision['confidence_label']}"
        )

        # Rate limiting
        time.sleep(API_DELAY_SECONDS)

    valid = results['total'] - results['errors']
    results['category_accuracy']  = round(results['correct_category'] / valid, 3) if valid else 0.0
    results['caption_accuracy']   = round(results['correct_caption']  / valid, 3) if valid else 0.0
    results['high_conf_accuracy'] = round(
        results['high_confidence_correct'] / results['high_confidence_total'], 3
    ) if results['high_confidence_total'] else 0.0

    log.info(f"\n{'=' * 55}")
    log.info(f"  ACCURACY TEST RESULTS")
    log.info(f"{'=' * 55}")
    log.info(f"  Accounts tested:        {results['total']}")
    log.info(f"  Category accuracy:      {results['category_accuracy'] * 100:.1f}%")
    log.info(f"  Caption accuracy:       {results['caption_accuracy'] * 100:.1f}%")
    log.info(f"  High-conf accuracy:     {results['high_conf_accuracy'] * 100:.1f}%  "
             f"({results['high_confidence_correct']}/{results['high_confidence_total']})")
    log.info(f"  Parse/API errors:       {results['errors']}")
    log.info(f"{'=' * 55}")

    if results['category_accuracy'] >= 0.85:
        log.info("  PASS — accuracy above 85%% threshold. Safe to deploy.")
    else:
        log.warning("  FAIL — accuracy below 85%%. Refine prompt before deploying.")

    return results


# ══════════════════════════════════════════════════════════════
# SECTION 5 — MAIN AGENT LOOP
# ══════════════════════════════════════════════════════════════

def run_agent(dry_run: bool = False, batch_size: int = 20) -> dict:
    """
    Main agent loop. Processes unmapped accounts in batches.

    Args:
        dry_run:    If True, show decisions without writing to BigQuery.
        batch_size: Max accounts to process per run. Must be 1-100.

    Returns:
        Summary dict with processed/errors counts.
    """
    batch_size = max(1, min(batch_size, 100))

    log.info(
        f"GL Mapping Agent starting — project={PROJECT} "
        f"dataset={DATASET} fiscal_year={FISCAL_YEAR} company={COMPANY_CODE} "
        f"model={MODEL} dry_run={dry_run}"
    )

    accounts = get_unmapped_accounts()
    if not accounts:
        log.info("No unmapped accounts found. Nothing to do.")
        return {'processed': 0, 'errors': 0}

    to_process = accounts[:batch_size]
    log.info(f"Processing {len(to_process)} of {len(accounts)} unmapped accounts...")

    processed = 0
    errors = 0

    for i, account in enumerate(to_process, 1):
        log.info(
            f"[{i}/{len(to_process)}] Processing: {account['gl_account']} — "
            f"{(account.get('description') or '')[:60]} "
            f"(${float(account.get('posting_amount', 0)):,.0f})"
        )

        # Step 1 — find similar approved accounts
        similar = get_similar_accounts(account.get('description') or '')
        log.info(f"  Found {len(similar)} similar accounts")

        # Step 2 — call Claude
        decision = call_mapping_agent(account, similar)
        if not decision:
            log.error(f"  Agent failed for {account['gl_account']} — skipping")
            errors += 1
            continue

        log.info(
            f"  -> {decision['suggested_category']} | "
            f"{decision['suggested_caption']} | "
            f"Confidence: {decision['confidence_label']} ({decision['confidence_score']:.2f})"
        )
        log.info(f"  Reasoning: {decision['draft_reasoning'][:200]}...")

        if dry_run:
            log.info("  [DRY RUN] — not writing to BigQuery")
            processed += 1
        else:
            # Step 3 — write to pending_mappings + audit log
            try:
                write_pending_mapping(account, decision, similar)
                write_audit_log(account, decision, 'AGENT_DRAFT')
                log.info(f"  Written to pending_mappings successfully")
                processed += 1
            except Exception as e:
                log.error(f"  BigQuery write error for {account['gl_account']}: {e}")
                errors += 1

        # Rate limiting between API calls
        if i < len(to_process):
            time.sleep(API_DELAY_SECONDS)

    summary = {'processed': processed, 'errors': errors, 'total_unmapped': len(accounts)}
    log.info(
        f"\nAgent run complete — "
        f"processed={processed} errors={errors} "
        f"remaining={len(accounts) - processed - errors}"
    )
    if not dry_run and processed > 0:
        log.info(
            f"Review pending mappings:\n"
            f"  SELECT * FROM `{PROJECT}.{DATASET}.pending_mappings`\n"
            f"  WHERE status = 'PENDING'\n"
            f"  ORDER BY materiality_flag DESC, confidence_label, posting_amount DESC;"
        )

    return summary


# ══════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'test'

    if mode == 'test':
        log.info("Running accuracy test against existing mappings...")
        sample = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        results = run_accuracy_test(sample_size=sample)
        print(json.dumps(results, indent=2, default=str))

    elif mode == 'dry-run':
        batch = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        run_agent(dry_run=True, batch_size=batch)

    elif mode == 'run':
        batch = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        run_agent(dry_run=False, batch_size=batch)

    else:
        print("Usage: python mapping_agent.py <mode> [batch_size]")
        print()
        print("Modes:")
        print("  test [N]    — blind accuracy test against N existing mappings (default: 20)")
        print("  dry-run [N] — show decisions for N unmapped accounts, no writes (default: 5)")
        print("  run [N]     — process up to N unmapped accounts, write to BigQuery (default: 20)")
        sys.exit(1)


if __name__ == '__main__':
    main()
