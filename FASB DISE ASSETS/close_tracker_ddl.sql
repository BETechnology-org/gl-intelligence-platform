-- ============================================================
-- GL INTELLIGENCE PLATFORM — CLOSE TASK TRACKER
-- Project: diplomatic75
-- Dataset: dise_reporting
-- ============================================================
-- Philosophy: Task status is driven by actual BigQuery query
-- results — not by manual checkbox clicks. A task is complete
-- when the data says it is complete.
-- ============================================================

-- ── Table: close_tasks ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS `diplomatic75.dise_reporting.close_tasks` (
  task_id         STRING NOT NULL,
  task_name       STRING NOT NULL,
  task_category   STRING NOT NULL,   -- MAPPING | RECONCILIATION | REVIEW | FILING
  description     STRING,
  status_query    STRING NOT NULL,   -- BigQuery SQL that returns a single row
  -- status_query must return:
  --   is_complete  BOOL
  --   metric_value STRING   (human-readable current state)
  --   detail       STRING   (explains why complete or not)
  fiscal_year     STRING NOT NULL,
  fiscal_period   STRING NOT NULL,   -- e.g. '2023-Q3'
  company_code    STRING NOT NULL,
  owner_name      STRING,
  owner_email     STRING,
  due_date        DATE,
  -- Runtime fields — updated nightly by Cloud Scheduler
  is_complete     BOOL,
  metric_value    STRING,
  detail          STRING,
  last_checked_at TIMESTAMP,
  completed_at    TIMESTAMP,
  -- Metadata
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  sort_order      INT64
);

-- ── Table: close_task_history ────────────────────────────────
-- Immutable log of every status change — audit trail
CREATE TABLE IF NOT EXISTS `diplomatic75.dise_reporting.close_task_history` (
  history_id      STRING DEFAULT GENERATE_UUID(),
  task_id         STRING NOT NULL,
  fiscal_year     STRING NOT NULL,
  fiscal_period   STRING NOT NULL,
  checked_at      TIMESTAMP NOT NULL,
  was_complete    BOOL,
  metric_value    STRING,
  detail          STRING,
  changed_from    STRING,   -- 'INCOMPLETE' | 'COMPLETE'
  changed_to      STRING
);

-- ============================================================
-- SEED DATA — Six close tasks for FY2023 / C006
-- Each status_query returns: is_complete, metric_value, detail
-- ============================================================

-- ── Task 1: GL Account Mapping Coverage ─────────────────────
-- Complete when zero accounts have posted material amounts
-- but are not in gl_dise_mapping (unmapped exposure = 0)
INSERT INTO `diplomatic75.dise_reporting.close_tasks`
  (task_id, task_name, task_category, description,
   fiscal_year, fiscal_period, company_code,
   owner_name, sort_order, due_date,
   status_query)
VALUES (
  'T001',
  'GL account mapping — zero unmapped exposure',
  'MAPPING',
  'Every GL account that posted material amounts this period must be mapped to a DISE category with an ASC citation. Task is complete when unclassified posting exposure is less than $1,000.',
  '2023', '2023-Q4', 'C006',
  'Controller', 1, DATE '2023-11-15',
  '''
  SELECT
    (SUM(unclassified_amount) < 1000 OR SUM(unclassified_amount) IS NULL)
      AS is_complete,
    CONCAT("$", FORMAT("%\'d", CAST(COALESCE(SUM(unclassified_amount),0) AS INT64)),
      " unclassified across ", CAST(COUNT(DISTINCT gl_account) AS STRING), " accounts")
      AS metric_value,
    CASE
      WHEN SUM(unclassified_amount) < 1000 OR SUM(unclassified_amount) IS NULL
        THEN "All material postings are mapped — disclosure is complete"
      ELSE CONCAT(CAST(COUNT(DISTINCT gl_account) AS STRING),
        " accounts not mapped. Top account: ",
        ARRAY_AGG(gl_account ORDER BY unclassified_amount DESC LIMIT 1)[OFFSET(0)])
    END AS detail
  FROM (
    SELECT
      bseg.HKONT AS gl_account,
      SUM(bseg.DMBTR) AS unclassified_amount
    FROM `diplomatic75.CORTEX_SAP_CDC.bkpf` bkpf
    JOIN `diplomatic75.CORTEX_SAP_CDC.bseg` bseg
      ON  bkpf.MANDT = bseg.MANDT
      AND bkpf.BELNR = bseg.BELNR
      AND bkpf.GJAHR = bseg.GJAHR
    LEFT JOIN `diplomatic75.dise_reporting.gl_dise_mapping` m
      ON  bseg.HKONT = m.gl_account
    WHERE bkpf.GJAHR = "2023"
      AND bkpf.BUKRS = "C006"
      AND bkpf.BLART NOT IN ("AA","AF","AB")
      AND m.gl_account IS NULL
    GROUP BY 1
    HAVING SUM(bseg.DMBTR) > 1000
  )
  '''
);

-- ── Task 1B: Pending Mappings Queue Cleared ───────────────────
-- Complete when all agent-drafted mappings have been reviewed
-- Prevents filing while approvals are still outstanding
INSERT INTO `diplomatic75.dise_reporting.close_tasks`
  (task_id, task_name, task_category, description,
   fiscal_year, fiscal_period, company_code,
   owner_name, sort_order, due_date,
   status_query)
VALUES (
  'T001B',
  'All pending agent mappings reviewed — zero outstanding',
  'MAPPING',
  'Every GL account classified by the mapping agent must be approved, overridden, or rejected by a qualified reviewer before the disclosure can proceed. This task completes when the pending_mappings queue has zero records with status PENDING.',
  '2023', '2023-Q4', 'C006',
  'Controller', 1, DATE '2023-11-18',
  '''
  SELECT
    (COUNT(*) = 0) AS is_complete,
    CONCAT(CAST(COUNT(*) AS STRING), " pending agent decisions") AS metric_value,
    CASE WHEN COUNT(*) = 0
      THEN "All agent mappings reviewed — approval queue empty"
      ELSE CONCAT(CAST(COUNT(*) AS STRING),
        " mappings awaiting review. Oldest: ",
        CAST(MIN(drafted_at) AS STRING))
    END AS detail
  FROM `diplomatic75.dise_reporting.pending_mappings`
  WHERE status = "PENDING"
    AND fiscal_year = "2023"
  '''
);

-- ── Task 2: DISE Pivot Reconciliation to Income Statement ────
-- Complete when DISE category totals match expected IS amounts
-- Uses a reference amounts table (seeded below)
INSERT INTO `diplomatic75.dise_reporting.close_tasks`
  (task_id, task_name, task_category, description,
   fiscal_year, fiscal_period, company_code,
   owner_name, sort_order, due_date,
   status_query)
VALUES (
  'T002',
  'DISE pivot reconciles to income statement — variance $0',
  'RECONCILIATION',
  'The sum of all DISE category amounts by expense caption must equal the income statement face amounts for COGS, SG&A, and R&D. A $1 variance means the disclosure is non-compliant.',
  '2023', '2023-Q4', 'C006',
  'Controller', 2, DATE '2023-11-20',
  '''
  WITH pivot_totals AS (
    SELECT
      m.expense_caption,
      ROUND(SUM(bseg.DMBTR), 0) AS dise_total
    FROM `diplomatic75.CORTEX_SAP_CDC.bkpf` bkpf
    JOIN `diplomatic75.CORTEX_SAP_CDC.bseg` bseg
      ON  bkpf.MANDT = bseg.MANDT
      AND bkpf.BELNR = bseg.BELNR
      AND bkpf.GJAHR = bseg.GJAHR
    JOIN `diplomatic75.dise_reporting.gl_dise_mapping` m
      ON  bseg.HKONT = m.gl_account
    WHERE bkpf.GJAHR = "2023"
      AND bkpf.BUKRS = "C006"
      AND bkpf.BLART NOT IN ("AA","AF","AB")
      AND m.status = "mapped"
    GROUP BY 1
  ),
  is_amounts AS (
    SELECT "COGS"  AS expense_caption, 28576364 AS is_amount UNION ALL
    SELECT "SG&A"  AS expense_caption, 8963875  AS is_amount UNION ALL
    SELECT "R&D"   AS expense_caption, 512000   AS is_amount
  ),
  variance AS (
    SELECT
      p.expense_caption,
      ABS(p.dise_total - i.is_amount) AS abs_variance,
      p.dise_total,
      i.is_amount
    FROM pivot_totals p
    JOIN is_amounts i USING (expense_caption)
  )
  SELECT
    (MAX(abs_variance) = 0) AS is_complete,
    CONCAT("Max variance: $", FORMAT("%\'d", CAST(MAX(abs_variance) AS INT64))) AS metric_value,
    CASE WHEN MAX(abs_variance) = 0
      THEN "All captions reconcile to income statement — zero variance"
      ELSE CONCAT("Largest variance in ",
        ARRAY_AGG(expense_caption ORDER BY abs_variance DESC LIMIT 1)[OFFSET(0)],
        ": $", FORMAT("%\'d", CAST(MAX(abs_variance) AS INT64)))
    END AS detail
  FROM variance
  '''
);

-- ── Task 3: Anomaly Review — All P1 Alerts Cleared ──────────
-- Complete when no open Priority 1 anomaly alerts remain
INSERT INTO `diplomatic75.dise_reporting.close_tasks`
  (task_id, task_name, task_category, description,
   fiscal_year, fiscal_period, company_code,
   owner_name, sort_order, due_date,
   status_query)
VALUES (
  'T003',
  'All P1 anomaly alerts reviewed and cleared',
  'REVIEW',
  'Priority 1 anomaly alerts represent statistical outliers greater than 3 standard deviations from the period norm. Each must be reviewed by the Controller and either resolved or documented with a business explanation before the disclosure is filed.',
  '2023', '2023-Q4', 'C006',
  'Controller', 3, DATE '2023-11-22',
  '''
  SELECT
    (COUNT(*) = 0) AS is_complete,
    CONCAT(CAST(COUNT(*) AS STRING), " open P1 alerts") AS metric_value,
    CASE WHEN COUNT(*) = 0
      THEN "No open P1 alerts — all anomalies reviewed and cleared"
      ELSE CONCAT(CAST(COUNT(*) AS STRING),
        " P1 alerts unresolved. Oldest: ",
        CAST(MIN(alert_date) AS STRING))
    END AS detail
  FROM `diplomatic75.dise_reporting.anomaly_alerts`
  WHERE alert_priority = "P1"
    AND fiscal_year = "2023"
    AND status = "open"
  '''
);

-- ── Task 4: YoY Category Mix Stability Check ─────────────────
-- Complete when no DISE category has shifted more than 20%
-- relative to prior year without a documented explanation
INSERT INTO `diplomatic75.dise_reporting.close_tasks`
  (task_id, task_name, task_category, description,
   fiscal_year, fiscal_period, company_code,
   owner_name, sort_order, due_date,
   status_query)
VALUES (
  'T004',
  'Year-over-year category mix shift within tolerance',
  'REVIEW',
  'DISE category mix percentages must be consistent with prior year or the change must be explained by a documented operational reason. Auditors will question any category that shifts more than 20% without explanation. This task completes when all material shifts are either within tolerance or have been documented.',
  '2023', '2023-Q4', 'C006',
  'Senior Accountant', 4, DATE '2023-11-25',
  '''
  WITH yoy AS (
    SELECT
      m.dise_category,
      m.expense_caption,
      ROUND(SUM(CASE WHEN bkpf.GJAHR = "2022" THEN bseg.DMBTR ELSE 0 END), 0) AS fy2022,
      ROUND(SUM(CASE WHEN bkpf.GJAHR = "2023" THEN bseg.DMBTR ELSE 0 END), 0) AS fy2023
    FROM `diplomatic75.CORTEX_SAP_CDC.bkpf` bkpf
    JOIN `diplomatic75.CORTEX_SAP_CDC.bseg` bseg
      ON  bkpf.MANDT = bseg.MANDT
      AND bkpf.BELNR = bseg.BELNR
      AND bkpf.GJAHR = bseg.GJAHR
    JOIN `diplomatic75.dise_reporting.gl_dise_mapping` m
      ON  bseg.HKONT = m.gl_account
    WHERE bkpf.GJAHR IN ("2022","2023")
      AND bkpf.BUKRS = "C006"
      AND bkpf.BLART NOT IN ("AA","AF","AB")
      AND m.status = "mapped"
    GROUP BY 1, 2
  ),
  shifts AS (
    SELECT *,
      ABS((fy2023 - fy2022) / NULLIF(fy2022, 0)) * 100 AS shift_pct
    FROM yoy
    WHERE fy2022 > 0
  )
  SELECT
    (MAX(shift_pct) <= 20) AS is_complete,
    CONCAT("Max shift: ", CAST(ROUND(MAX(shift_pct),1) AS STRING), "%") AS metric_value,
    CASE WHEN MAX(shift_pct) <= 20
      THEN "All category mix shifts within 20% tolerance — no auditor questions expected"
      ELSE CONCAT(
        ARRAY_AGG(dise_category ORDER BY shift_pct DESC LIMIT 1)[OFFSET(0)],
        " shifted ", CAST(ROUND(MAX(shift_pct),1) AS STRING),
        "% YoY — document business reason before filing")
    END AS detail
  FROM shifts
  '''
);

-- ── Task 5: Audit Trail Completeness ─────────────────────────
-- Complete when every mapped GL account has a reviewer name,
-- review date, and ASC citation populated
INSERT INTO `diplomatic75.dise_reporting.close_tasks`
  (task_id, task_name, task_category, description,
   fiscal_year, fiscal_period, company_code,
   owner_name, sort_order, due_date,
   status_query)
VALUES (
  'T005',
  'Audit trail complete — all mapped accounts documented',
  'REVIEW',
  'Every GL account in the mapping table must have a reviewer name, review date, and ASC citation. Accounts missing this documentation cannot be included in the audit trail package. Auditors will test a sample — any undocumented account in the sample fails the test.',
  '2023', '2023-Q4', 'C006',
  'Controller', 5, DATE '2023-11-28',
  '''
  SELECT
    (COUNT(*) = 0) AS is_complete,
    CONCAT(CAST(COUNT(*) AS STRING), " accounts with incomplete documentation") AS metric_value,
    CASE WHEN COUNT(*) = 0
      THEN "All mapped accounts have reviewer, date, and ASC citation — audit trail complete"
      ELSE CONCAT(CAST(COUNT(*) AS STRING),
        " accounts missing documentation. First: ", 
        COALESCE(ARRAY_AGG(gl_account LIMIT 1)[OFFSET(0)], "unknown"))
    END AS detail
  FROM `diplomatic75.dise_reporting.gl_dise_mapping`
  WHERE status = "mapped"
    AND (
      reviewer IS NULL OR reviewer = ""
      OR reviewed_at IS NULL
      OR asc_citation IS NULL OR asc_citation = ""
    )
  '''
);

-- ── Task 6: Disclosure Draft Approved ────────────────────────
-- Complete when the disclosure_approvals table has a CFO sign-off
-- for the current period (manually triggered — human in the loop)
INSERT INTO `diplomatic75.dise_reporting.close_tasks`
  (task_id, task_name, task_category, description,
   fiscal_year, fiscal_period, company_code,
   owner_name, sort_order, due_date,
   status_query)
VALUES (
  'T006',
  'DISE disclosure draft approved by CFO',
  'FILING',
  'The final DISE disclosure footnote must be approved by the CFO before inclusion in the 10-Q or 10-K filing. This is the only task in the close tracker that requires a deliberate human action — the CFO clicks Approve in the platform. All other tasks are data-driven.',
  '2023', '2023-Q4', 'C006',
  'CFO', 6, DATE '2023-12-01',
  '''
  SELECT
    (COUNT(*) > 0) AS is_complete,
    CASE WHEN COUNT(*) > 0
      THEN CONCAT("Approved by ", MAX(approved_by), " on ", CAST(MAX(approved_at) AS STRING))
      ELSE "Awaiting CFO approval"
    END AS metric_value,
    CASE WHEN COUNT(*) > 0
      THEN "Disclosure approved and ready for filing — Section 302 certification can proceed"
      ELSE "CFO approval required before disclosure can be included in SEC filing"
    END AS detail
  FROM `diplomatic75.dise_reporting.disclosure_approvals`
  WHERE fiscal_year = "2023"
    AND fiscal_period = "2023-Q4"
    AND company_code = "C006"
    AND approval_status = "approved"
  '''
);

-- ── Supporting table: disclosure_approvals ───────────────────
CREATE TABLE IF NOT EXISTS `diplomatic75.dise_reporting.disclosure_approvals` (
  approval_id     STRING DEFAULT GENERATE_UUID(),
  fiscal_year     STRING NOT NULL,
  fiscal_period   STRING NOT NULL,
  company_code    STRING NOT NULL,
  approved_by     STRING,
  approved_at     TIMESTAMP,
  approval_status STRING,   -- 'pending' | 'approved' | 'rejected'
  comments        STRING,
  disclosure_hash STRING    -- SHA256 of the disclosure text at time of approval
);
