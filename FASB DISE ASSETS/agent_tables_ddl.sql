-- ============================================================
-- BE Technology — GL Intelligence Platform
-- Autonomous GL Mapping Agent — Foundation Tables v1.1
-- Project: diplomatic75
-- Dataset: dise_reporting
-- ============================================================
-- Changes in v1.1:
--   - Added reviewed_at timestamp default
--   - Added drafted_at timestamp default
--   - Improved table descriptions
--   - Added clustering for query performance
--   - Added event_timestamp default on audit log
-- ============================================================

-- ── Table 1: pending_mappings ────────────────────────────────
-- Agent working memory. Every draft mapping decision lives here
-- until a human approves, rejects, or overrides it.
-- Approved records are promoted to gl_dise_mapping.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `diplomatic75.dise_reporting.pending_mappings` (
  -- ── Account identity ──────────────────────────────────────
  gl_account            STRING    NOT NULL,   -- HKONT from bseg
  description           STRING,              -- txt50 from skat
  posting_amount        NUMERIC,             -- FY total from bseg.DMBTR
  fiscal_year           STRING,              -- e.g. '2023'
  company_code          STRING,              -- e.g. 'C006'

  -- ── Agent decision ────────────────────────────────────────
  suggested_category    STRING,              -- Full name e.g. 'Purchases of inventory'
  suggested_caption     STRING,              -- e.g. 'COGS'
  suggested_citation    STRING,              -- e.g. 'ASC 220-40-50-6(b)'
  draft_reasoning       STRING,              -- Full agent reasoning — shown to reviewer
  confidence_score      FLOAT64,            -- 0.0–1.0  high=0.85+  med=0.60+  low=<0.60
  confidence_label      STRING,              -- 'HIGH' | 'MEDIUM' | 'LOW'

  -- ── Similarity references ─────────────────────────────────
  -- JSON array of up to 5 similar approved accounts the agent
  -- used as reference. Format:
  -- [{"gl_account":"0000630040","description":"...","dise_category":"...","similarity":0.91}]
  similar_accounts      STRING,

  -- ── Materiality ───────────────────────────────────────────
  materiality_flag      STRING,             -- 'HIGH' | 'MEDIUM' | 'LOW'
  -- HIGH   = posting_amount >= 500000  → Controller review required
  -- MEDIUM = posting_amount >= 100000  → Senior Accountant review
  -- LOW    = posting_amount <  100000  → can be bulk-approved

  -- ── Workflow status ───────────────────────────────────────
  status                STRING    NOT NULL,  -- 'PENDING' | 'APPROVED' | 'REJECTED' | 'OVERRIDDEN'

  -- ── Human review ─────────────────────────────────────────
  -- Populated when reviewer acts. NULL until then.
  reviewed_category     STRING,              -- May differ from suggested if overridden
  reviewed_caption      STRING,
  reviewed_citation     STRING,
  override_reason       STRING,              -- Required if status = 'OVERRIDDEN'
  reviewer              STRING,              -- Name or email of approving human
  reviewed_at           TIMESTAMP,

  -- ── Agent metadata ────────────────────────────────────────
  drafted_by            STRING,             -- 'GL_MAPPING_AGENT_v1'
  drafted_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  model_version         STRING NOT NULL,    -- Claude model used e.g. 'claude-sonnet-4-20250514'
  prompt_version        STRING NOT NULL     -- Prompt version for reproducibility e.g. 'v1.1'
)
CLUSTER BY status, fiscal_year, company_code
OPTIONS (
  description = 'Agent working memory for autonomous GL mapping decisions. Records move from PENDING to APPROVED/REJECTED/OVERRIDDEN after human review. Approved records are promoted to gl_dise_mapping.'
);


-- ── Table 2: mapping_decisions_log ──────────────────────────
-- Immutable audit trail. Every agent action and human decision
-- is written here permanently and never updated or deleted.
-- This is the evidence package for auditors.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `diplomatic75.dise_reporting.mapping_decisions_log` (
  -- ── Event identity ────────────────────────────────────────
  event_id              STRING    NOT NULL,  -- UUID generated at insert time
  event_type            STRING    NOT NULL,
  -- Event types:
  --   AGENT_DRAFT        Agent created a draft mapping
  --   HUMAN_APPROVED     Reviewer approved agent suggestion as-is
  --   HUMAN_OVERRIDDEN   Reviewer changed category/caption/citation
  --   HUMAN_REJECTED     Reviewer rejected — account needs manual investigation
  --   PROMOTED           Record promoted from pending_mappings to gl_dise_mapping
  --   BULK_APPROVED      Reviewer bulk-approved a batch of LOW materiality records

  event_timestamp       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),

  -- ── Account ───────────────────────────────────────────────
  gl_account            STRING    NOT NULL,
  description           STRING,
  fiscal_year           STRING,
  company_code          STRING,
  posting_amount        NUMERIC,

  -- ── What the agent said ───────────────────────────────────
  agent_category        STRING,
  agent_caption         STRING,
  agent_citation        STRING,
  agent_confidence      FLOAT64,
  agent_reasoning       STRING,             -- Full text — never truncated

  -- ── What the human decided ───────────────────────────────
  final_category        STRING,             -- What actually went into gl_dise_mapping
  final_caption         STRING,
  final_citation        STRING,
  human_agreed          BOOL,               -- TRUE if human approved without change
  override_reason       STRING,

  -- ── Who acted ─────────────────────────────────────────────
  actor                 STRING,             -- 'GL_MAPPING_AGENT_v1' or reviewer name
  actor_type            STRING,             -- 'AGENT' | 'HUMAN'

  -- ── Agent metadata ────────────────────────────────────────
  model_version         STRING NOT NULL,
  prompt_version        STRING NOT NULL
)
PARTITION BY DATE(event_timestamp)
CLUSTER BY gl_account, event_type
OPTIONS (
  description = 'Immutable audit trail for all GL mapping decisions. Never updated or deleted. Provides auditor-facing evidence that every account classification was reviewed and approved by a qualified human before use in DISE disclosure. Partitioned by event date for efficient queries.'
);


-- ── Verification queries ─────────────────────────────────────
-- Run these after CREATE to confirm tables exist and are empty

SELECT 'pending_mappings'      AS table_name, COUNT(*) AS row_count
FROM `diplomatic75.dise_reporting.pending_mappings`
UNION ALL
SELECT 'mapping_decisions_log' AS table_name, COUNT(*) AS row_count
FROM `diplomatic75.dise_reporting.mapping_decisions_log`;
