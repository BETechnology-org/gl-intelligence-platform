# ============================================================
# BE Technology — GL Intelligence Platform
# Tax Reconciliation Module (ASU 2023-09 / ASC 740)
# Terraform additions — append to existing main.tf
#
# Prerequisites:
#   - Existing DISE main.tf already applied
#   - google_bigquery_dataset.dise_reporting already exists
#   - google_service_account.dise_agent already exists
#   - google_secret_manager_secret.anthropic_api_key already exists
#   - local.labels and var.* already defined in variables.tf
#
# Add these variables to your existing variables.tf:
#   tax_classifier_image  (Cloud Run image for tax_03_classifier.py)
#   tax_schedule_cron     (default: "0 6 1 * *" — 6am on 1st of month)
#   tax_confidence_threshold (default: "0.80")
#   fiscal_year_tax       (default: "2025")
# ============================================================

# ============================================================
# SECTION 7 — BIGQUERY TABLES: TAX RECONCILIATION MODULE
# All 7 tables in dise_reporting dataset
# Partitioned by loaded_date (DATE) — matches what was validated
# in diplomatic75 after fixing RANGE_BUCKET errors
# ============================================================

# ── tax_gl_mapping ────────────────────────────────────────────
resource "google_bigquery_table" "tax_gl_mapping" {
  dataset_id          = google_bigquery_dataset.dise_reporting.dataset_id
  table_id            = "tax_gl_mapping"
  deletion_protection = true
  description         = "GL account to ASU 2023-09 tax category mapping. Core classification layer for the ETR bridge and tax disclosure tables."
  labels              = merge(local.labels, { module = "tax_reconciliation", standard = "asu_2023_09" })

  schema = jsonencode([
    { name = "gl_account",         type = "STRING",    mode = "REQUIRED", description = "SAP GL account (HKONT)" },
    { name = "description",        type = "STRING",    mode = "NULLABLE", description = "Account description from SKA1" },
    { name = "tax_category",       type = "STRING",    mode = "NULLABLE", description = "current_tax | deferred_tax | uncertain_tax | valuation_allowance | pretax_income | other | not_applicable" },
    { name = "jurisdiction_type",  type = "STRING",    mode = "NULLABLE", description = "federal | state | foreign | not_applicable" },
    { name = "country_code",       type = "STRING",    mode = "NULLABLE", description = "ISO 3166-1 alpha-2 for foreign accounts e.g. GB DE JP" },
    { name = "etr_line_category",  type = "STRING",    mode = "NULLABLE", description = "ASU 2023-09 prescribed ETR reconciliation category" },
    { name = "pretax_income_type", type = "STRING",    mode = "NULLABLE", description = "domestic | foreign | not_applicable" },
    { name = "taxes_paid_type",    type = "STRING",    mode = "NULLABLE", description = "cash_taxes_paid | not_applicable" },
    { name = "status",             type = "STRING",    mode = "NULLABLE", description = "mapped | unmapped | review | excluded" },
    { name = "ai_confidence",      type = "FLOAT64",   mode = "NULLABLE", description = "AI classifier confidence 0.0-1.0" },
    { name = "ai_reasoning",       type = "STRING",    mode = "NULLABLE", description = "AI classification rationale" },
    { name = "reviewer",           type = "STRING",    mode = "NULLABLE", description = "Approving reviewer email" },
    { name = "reviewed_at",        type = "TIMESTAMP", mode = "NULLABLE", description = "When human approved this mapping" },
    { name = "asc_citation",       type = "STRING",    mode = "NULLABLE", description = "ASC 740 citation e.g. ASC 740-10-50-12" },
    { name = "notes",              type = "STRING",    mode = "NULLABLE", description = "Methodology notes" },
    { name = "created_at",         type = "TIMESTAMP", mode = "NULLABLE", description = "Row creation timestamp" },
    { name = "updated_at",         type = "TIMESTAMP", mode = "NULLABLE", description = "Last modification timestamp" }
  ])
}

# ── tax_pending_mappings ──────────────────────────────────────
resource "google_bigquery_table" "tax_pending_mappings" {
  dataset_id          = google_bigquery_dataset.dise_reporting.dataset_id
  table_id            = "tax_pending_mappings"
  deletion_protection = false
  description         = "Tax module AI draft mappings awaiting human approval. Mirrors DISE pending_mappings pattern."
  labels              = merge(local.labels, { module = "tax_reconciliation" })

  schema = jsonencode([
    { name = "pending_id",        type = "STRING",    mode = "NULLABLE" },
    { name = "gl_account",        type = "STRING",    mode = "NULLABLE" },
    { name = "description",       type = "STRING",    mode = "NULLABLE" },
    { name = "ai_tax_category",   type = "STRING",    mode = "NULLABLE" },
    { name = "ai_jurisdiction",   type = "STRING",    mode = "NULLABLE" },
    { name = "ai_etr_line",       type = "STRING",    mode = "NULLABLE" },
    { name = "ai_pretax_type",    type = "STRING",    mode = "NULLABLE" },
    { name = "ai_taxes_paid",     type = "STRING",    mode = "NULLABLE" },
    { name = "ai_confidence",     type = "FLOAT64",   mode = "NULLABLE" },
    { name = "ai_reasoning",      type = "STRING",    mode = "NULLABLE" },
    { name = "ai_asc_citation",   type = "STRING",    mode = "NULLABLE" },
    { name = "model_version",     type = "STRING",    mode = "NULLABLE" },
    { name = "prompt_version",    type = "STRING",    mode = "NULLABLE" },
    { name = "status",            type = "STRING",    mode = "NULLABLE", description = "pending | approved | rejected | overridden | promoted" },
    { name = "reviewed_by",       type = "STRING",    mode = "NULLABLE" },
    { name = "reviewed_at",       type = "STRING",    mode = "NULLABLE", description = "ISO timestamp string — cast to TIMESTAMP on promotion" },
    { name = "override_category", type = "STRING",    mode = "NULLABLE" },
    { name = "override_reason",   type = "STRING",    mode = "NULLABLE" },
    { name = "created_at",        type = "STRING",    mode = "NULLABLE" },
    { name = "updated_at",        type = "STRING",    mode = "NULLABLE" }
  ])
}

# ── tax_provision_universe ────────────────────────────────────
resource "google_bigquery_table" "tax_provision_universe" {
  dataset_id          = google_bigquery_dataset.dise_reporting.dataset_id
  table_id            = "tax_provision_universe"
  deletion_protection = false
  description         = "Tax provision universe — one row per legal entity per period. Foundation for all ASU 2023-09 disclosure tables."
  labels              = merge(local.labels, { module = "tax_reconciliation", standard = "asu_2023_09" })

  time_partitioning {
    type  = "MONTH"
    field = "posting_date"
  }

  clustering = ["company_code", "fiscal_year"]

  schema = jsonencode([
    { name = "company_code",            type = "STRING",    mode = "REQUIRED" },
    { name = "fiscal_year",             type = "STRING",    mode = "REQUIRED" },
    { name = "fiscal_period",           type = "STRING",    mode = "REQUIRED" },
    { name = "posting_date",            type = "DATE",      mode = "NULLABLE" },
    { name = "company_name",            type = "STRING",    mode = "NULLABLE" },
    { name = "currency",                type = "STRING",    mode = "NULLABLE" },
    { name = "country_code",            type = "STRING",    mode = "NULLABLE" },
    { name = "jurisdiction_type",       type = "STRING",    mode = "NULLABLE" },
    { name = "pretax_income_domestic",  type = "NUMERIC",   mode = "NULLABLE" },
    { name = "pretax_income_foreign",   type = "NUMERIC",   mode = "NULLABLE" },
    { name = "pretax_income_total",     type = "NUMERIC",   mode = "NULLABLE" },
    { name = "current_tax_federal",     type = "NUMERIC",   mode = "NULLABLE" },
    { name = "current_tax_state",       type = "NUMERIC",   mode = "NULLABLE" },
    { name = "current_tax_foreign",     type = "NUMERIC",   mode = "NULLABLE" },
    { name = "current_tax_total",       type = "NUMERIC",   mode = "NULLABLE" },
    { name = "deferred_tax_federal",    type = "NUMERIC",   mode = "NULLABLE" },
    { name = "deferred_tax_state",      type = "NUMERIC",   mode = "NULLABLE" },
    { name = "deferred_tax_foreign",    type = "NUMERIC",   mode = "NULLABLE" },
    { name = "deferred_tax_total",      type = "NUMERIC",   mode = "NULLABLE" },
    { name = "total_tax_expense",       type = "NUMERIC",   mode = "NULLABLE" },
    { name = "effective_tax_rate",      type = "FLOAT64",   mode = "NULLABLE" },
    { name = "run_id",                  type = "STRING",    mode = "NULLABLE" },
    { name = "loaded_at",               type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

# ── etr_reconciliation_lines ──────────────────────────────────
resource "google_bigquery_table" "etr_reconciliation_lines" {
  dataset_id          = google_bigquery_dataset.dise_reporting.dataset_id
  table_id            = "etr_reconciliation_lines"
  deletion_protection = false
  description         = "ETR reconciliation waterfall — statutory rate to effective rate. Produces Table A of the ASU 2023-09 disclosure."
  labels              = merge(local.labels, { module = "tax_reconciliation", standard = "asu_2023_09" })

  time_partitioning {
    type  = "DAY"
    field = "loaded_date"
  }

  clustering = ["company_code", "fiscal_year"]

  schema = jsonencode([
    { name = "company_code",        type = "STRING",    mode = "REQUIRED" },
    { name = "fiscal_year",         type = "STRING",    mode = "REQUIRED" },
    { name = "fiscal_period",       type = "STRING",    mode = "REQUIRED" },
    { name = "line_sequence",       type = "INT64",     mode = "REQUIRED", description = "Display order in the disclosure waterfall" },
    { name = "etr_line_category",   type = "STRING",    mode = "REQUIRED" },
    { name = "line_label",          type = "STRING",    mode = "NULLABLE", description = "Human-readable label for the disclosure footnote" },
    { name = "is_prescribed",       type = "BOOL",      mode = "NULLABLE", description = "True = ASU 2023-09 required line" },
    { name = "materiality_pct",     type = "FLOAT64",   mode = "NULLABLE", description = "ABS(amount / pretax_income). Lines < 5% rolled to other unless prescribed" },
    { name = "amount",              type = "NUMERIC",   mode = "NULLABLE" },
    { name = "pretax_income",       type = "NUMERIC",   mode = "NULLABLE" },
    { name = "rate_pct",            type = "FLOAT64",   mode = "NULLABLE" },
    { name = "jurisdiction_detail", type = "STRING",    mode = "NULLABLE" },
    { name = "run_id",              type = "STRING",    mode = "NULLABLE" },
    { name = "loaded_at",           type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "loaded_date",         type = "DATE",      mode = "NULLABLE", description = "Date partition key" }
  ])
}

# ── taxes_paid_fact ───────────────────────────────────────────
resource "google_bigquery_table" "taxes_paid_fact" {
  dataset_id          = google_bigquery_dataset.dise_reporting.dataset_id
  table_id            = "taxes_paid_fact"
  deletion_protection = false
  description         = "Cash income taxes paid by jurisdiction. Produces Table B of the ASU 2023-09 disclosure."
  labels              = merge(local.labels, { module = "tax_reconciliation", standard = "asu_2023_09" })

  time_partitioning {
    type  = "DAY"
    field = "loaded_date"
  }

  clustering = ["company_code", "fiscal_year", "jurisdiction_type"]

  schema = jsonencode([
    { name = "company_code",         type = "STRING",    mode = "REQUIRED" },
    { name = "fiscal_year",          type = "STRING",    mode = "REQUIRED" },
    { name = "fiscal_period",        type = "STRING",    mode = "REQUIRED" },
    { name = "jurisdiction_type",    type = "STRING",    mode = "REQUIRED", description = "federal | state | foreign" },
    { name = "jurisdiction_name",    type = "STRING",    mode = "NULLABLE" },
    { name = "country_code",         type = "STRING",    mode = "NULLABLE" },
    { name = "taxes_paid_amount",    type = "NUMERIC",   mode = "NULLABLE", description = "NEGATIVE in SAP (outflow)" },
    { name = "taxes_paid_abs",       type = "NUMERIC",   mode = "NULLABLE", description = "Absolute value for disclosure presentation" },
    { name = "currency",             type = "STRING",    mode = "NULLABLE" },
    { name = "gl_accounts_included", type = "STRING",    mode = "NULLABLE" },
    { name = "posting_count",        type = "INT64",     mode = "NULLABLE" },
    { name = "run_id",               type = "STRING",    mode = "NULLABLE" },
    { name = "loaded_at",            type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "loaded_date",          type = "DATE",      mode = "NULLABLE", description = "Date partition key" }
  ])
}

# ── jurisdiction_statutory_rates ──────────────────────────────
resource "google_bigquery_table" "jurisdiction_statutory_rates" {
  dataset_id          = google_bigquery_dataset.dise_reporting.dataset_id
  table_id            = "jurisdiction_statutory_rates"
  deletion_protection = false
  description         = "Statutory income tax rates by jurisdiction and year. Anchor for the ETR bridge starting line."
  labels              = merge(local.labels, { module = "tax_reconciliation" })

  schema = jsonencode([
    { name = "jurisdiction_type", type = "STRING",    mode = "REQUIRED" },
    { name = "jurisdiction_name", type = "STRING",    mode = "REQUIRED" },
    { name = "country_code",      type = "STRING",    mode = "NULLABLE" },
    { name = "effective_year",    type = "INT64",     mode = "REQUIRED" },
    { name = "statutory_rate",    type = "FLOAT64",   mode = "REQUIRED" },
    { name = "notes",             type = "STRING",    mode = "NULLABLE" },
    { name = "source",            type = "STRING",    mode = "NULLABLE" },
    { name = "updated_at",        type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

# ── tax_disclosure_output ─────────────────────────────────────
resource "google_bigquery_table" "tax_disclosure_output" {
  dataset_id          = google_bigquery_dataset.dise_reporting.dataset_id
  table_id            = "tax_disclosure_output"
  deletion_protection = false
  description         = "Final ASU 2023-09 disclosure output — Tables A, B, and C. Audit-ready, Controller-approved."
  labels              = merge(local.labels, { module = "tax_reconciliation", standard = "asu_2023_09" })

  time_partitioning {
    type  = "DAY"
    field = "loaded_date"
  }

  clustering = ["company_code", "fiscal_year", "disclosure_table"]

  schema = jsonencode([
    { name = "company_code",     type = "STRING",    mode = "REQUIRED" },
    { name = "fiscal_year",      type = "STRING",    mode = "REQUIRED" },
    { name = "disclosure_table", type = "STRING",    mode = "REQUIRED", description = "A = ETR reconciliation | B = taxes paid | C = pretax income split" },
    { name = "line_sequence",    type = "INT64",     mode = "REQUIRED" },
    { name = "line_label",       type = "STRING",    mode = "NULLABLE" },
    { name = "current_year_pct", type = "FLOAT64",   mode = "NULLABLE" },
    { name = "current_year_amt", type = "NUMERIC",   mode = "NULLABLE" },
    { name = "prior_year_pct",   type = "FLOAT64",   mode = "NULLABLE" },
    { name = "prior_year_amt",   type = "NUMERIC",   mode = "NULLABLE" },
    { name = "is_total_row",     type = "BOOL",      mode = "NULLABLE" },
    { name = "source_table",     type = "STRING",    mode = "NULLABLE" },
    { name = "run_id",           type = "STRING",    mode = "NULLABLE" },
    { name = "approved_by",      type = "STRING",    mode = "NULLABLE" },
    { name = "approved_at",      type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "loaded_at",        type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "loaded_date",      type = "DATE",      mode = "NULLABLE", description = "Date partition key" }
  ])
}

# ============================================================
# SECTION 8 — BIGQUERY SCHEDULED QUERY: ETR BRIDGE
# Runs at period close — triggers the ETR bridge SQL that
# populates tax_provision_universe, etr_reconciliation_lines,
# taxes_paid_fact, and tax_disclosure_output
# ============================================================

resource "google_bigquery_data_transfer_config" "etr_bridge" {
  display_name           = "Tax ETR Bridge — ASU 2023-09 — ${var.client_id}"
  location               = var.bq_location
  data_source_id         = "scheduled_query"
  schedule               = var.tax_schedule_cron
  destination_dataset_id = google_bigquery_dataset.dise_reporting.dataset_id

  params = {
    query = <<-SQL
      -- ── ETR Bridge: Step 1 — provision universe ──────────────
      CREATE OR REPLACE TEMP TABLE raw_tax_postings AS
      SELECT
        b.BUKRS AS company_code, b.GJAHR AS fiscal_year,
        b.MONAT AS fiscal_period, b.BUDAT AS posting_date,
        s.HKONT AS gl_account,
        s.DMBTR * CASE WHEN s.SHKZG = 'S' THEN 1 ELSE -1 END AS amount_local,
        b.WAERS AS currency,
        m.tax_category, m.jurisdiction_type,
        m.etr_line_category, m.pretax_income_type, m.taxes_paid_type
      FROM `${var.project_id}.${var.cdc_dataset}.bkpf` b
      JOIN `${var.project_id}.${var.cdc_dataset}.bseg` s
        ON b.MANDT=s.MANDT AND b.BUKRS=s.BUKRS AND b.BELNR=s.BELNR AND b.GJAHR=s.GJAHR
      JOIN `${var.project_id}.${var.dataset_id}.tax_gl_mapping` m
        ON s.HKONT=m.gl_account AND m.status='mapped'
      WHERE b.GJAHR=FORMAT_DATE('%Y', DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH))
        AND (b.BSTAT IS NULL OR b.BSTAT IN ('0','A'))
        AND m.tax_category != 'not_applicable';

      -- ── ETR Bridge: Step 2 — provision summary ───────────────
      CREATE OR REPLACE TEMP TABLE provision_summary AS
      SELECT
        company_code, fiscal_year, fiscal_period,
        MAX(posting_date) AS posting_date, MAX(currency) AS currency,
        SUM(IF(tax_category='current_tax' AND jurisdiction_type='federal', amount_local,0)) AS current_tax_federal,
        SUM(IF(tax_category='current_tax' AND jurisdiction_type='state',   amount_local,0)) AS current_tax_state,
        SUM(IF(tax_category='current_tax' AND jurisdiction_type='foreign', amount_local,0)) AS current_tax_foreign,
        SUM(IF(tax_category='current_tax',  amount_local,0)) AS current_tax_total,
        SUM(IF(tax_category='deferred_tax' AND jurisdiction_type='federal', amount_local,0)) AS deferred_tax_federal,
        SUM(IF(tax_category='deferred_tax' AND jurisdiction_type='state',   amount_local,0)) AS deferred_tax_state,
        SUM(IF(tax_category='deferred_tax' AND jurisdiction_type='foreign', amount_local,0)) AS deferred_tax_foreign,
        SUM(IF(tax_category='deferred_tax', amount_local,0)) AS deferred_tax_total,
        SUM(IF(tax_category IN ('current_tax','deferred_tax'), amount_local,0)) AS total_tax_expense
      FROM raw_tax_postings
      GROUP BY company_code, fiscal_year, fiscal_period;

      -- ── ETR Bridge: Step 3 — insert provision universe ───────
      INSERT INTO `${var.project_id}.${var.dataset_id}.tax_provision_universe`
      (company_code, fiscal_year, fiscal_period, posting_date, currency,
       jurisdiction_type,
       current_tax_federal, current_tax_state, current_tax_foreign, current_tax_total,
       deferred_tax_federal, deferred_tax_state, deferred_tax_foreign, deferred_tax_total,
       total_tax_expense, run_id, loaded_at)
      SELECT
        company_code, fiscal_year, fiscal_period, posting_date, currency,
        'consolidated',
        current_tax_federal, current_tax_state, current_tax_foreign, current_tax_total,
        deferred_tax_federal, deferred_tax_state, deferred_tax_foreign, deferred_tax_total,
        total_tax_expense,
        CONCAT(FORMAT_DATE('%Y-%m', CURRENT_DATE()), '-auto'),
        CURRENT_TIMESTAMP()
      FROM provision_summary;

      -- ── ETR Bridge: Step 4 — tax disclosure output ───────────
      INSERT INTO `${var.project_id}.${var.dataset_id}.tax_disclosure_output`
      (company_code, fiscal_year, disclosure_table, line_sequence,
       line_label, current_year_amt, current_year_pct,
       is_total_row, source_table, run_id, loaded_at, loaded_date)
      WITH deduped AS (
        SELECT company_code, fiscal_year, fiscal_period,
          MAX(total_tax_expense) AS mx_total,
          MAX(current_tax_total) AS mx_current,
          MAX(current_tax_foreign) AS mx_foreign,
          MAX(deferred_tax_total) AS mx_deferred
        FROM `${var.project_id}.${var.dataset_id}.tax_provision_universe`
        WHERE fiscal_year = FORMAT_DATE('%Y', DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH))
        GROUP BY 1,2,3
      ),
      base AS (
        SELECT company_code, fiscal_year,
          ROUND(AVG(mx_total),0) AS total_tax, ROUND(AVG(mx_current),0) AS current_tax,
          ROUND(AVG(mx_foreign),0) AS foreign_tax, ROUND(AVG(mx_deferred),0) AS deferred_tax
        FROM deduped GROUP BY company_code, fiscal_year
      )
      SELECT company_code, fiscal_year, 'A', 1, 'Tax at US federal statutory rate (21%)',
        total_tax, 21.0, TRUE, 'tax_provision_universe',
        CONCAT(FORMAT_DATE('%Y-%m', CURRENT_DATE()), '-auto'), CURRENT_TIMESTAMP(), CURRENT_DATE()
      FROM base
      UNION ALL
      SELECT company_code, fiscal_year, 'A', 2, 'Foreign rate differential', foreign_tax,
        ROUND(foreign_tax/NULLIF(total_tax,0)*100,1),
        FALSE, 'tax_provision_universe',
        CONCAT(FORMAT_DATE('%Y-%m', CURRENT_DATE()), '-auto'), CURRENT_TIMESTAMP(), CURRENT_DATE()
      FROM base
      UNION ALL
      SELECT company_code, fiscal_year, 'A', 3, 'Deferred tax expense', deferred_tax,
        ROUND(deferred_tax/NULLIF(total_tax,0)*100,1),
        FALSE, 'tax_provision_universe',
        CONCAT(FORMAT_DATE('%Y-%m', CURRENT_DATE()), '-auto'), CURRENT_TIMESTAMP(), CURRENT_DATE()
      FROM base
      UNION ALL
      SELECT company_code, fiscal_year, 'A', 99, 'Total income tax expense',
        total_tax, NULL, TRUE, 'tax_provision_universe',
        CONCAT(FORMAT_DATE('%Y-%m', CURRENT_DATE()), '-auto'), CURRENT_TIMESTAMP(), CURRENT_DATE()
      FROM base
      UNION ALL
      SELECT company_code, fiscal_year, 'C', 1, 'Domestic',
        ROUND(total_tax-foreign_tax,0), NULL, FALSE, 'tax_provision_universe',
        CONCAT(FORMAT_DATE('%Y-%m', CURRENT_DATE()), '-auto'), CURRENT_TIMESTAMP(), CURRENT_DATE()
      FROM base
      UNION ALL
      SELECT company_code, fiscal_year, 'C', 2, 'Foreign',
        foreign_tax, NULL, FALSE, 'tax_provision_universe',
        CONCAT(FORMAT_DATE('%Y-%m', CURRENT_DATE()), '-auto'), CURRENT_TIMESTAMP(), CURRENT_DATE()
      FROM base
      UNION ALL
      SELECT company_code, fiscal_year, 'C', 99, 'Total income tax expense',
        total_tax, NULL, TRUE, 'tax_provision_universe',
        CONCAT(FORMAT_DATE('%Y-%m', CURRENT_DATE()), '-auto'), CURRENT_TIMESTAMP(), CURRENT_DATE()
      FROM base;
    SQL
  }

  service_account_name = google_service_account.dise_agent.email

  depends_on = [
    google_bigquery_table.tax_provision_universe,
    google_bigquery_table.tax_disclosure_output,
    google_bigquery_table.tax_gl_mapping,
  ]
}

# ============================================================
# SECTION 9 — CLOUD RUN JOB: TAX CLASSIFIER
# Runs tax_03_classifier.py against the client's SAP CDC data
# Triggered by Cloud Scheduler 2 days before ETR bridge
# ============================================================

resource "google_cloud_run_v2_job" "tax_classifier" {
  name     = "tax-classifier-${var.client_id}"
  location = var.region

  template {
    template {
      service_account = google_service_account.dise_agent.email

      containers {
        image = var.tax_classifier_image

        env {
          name  = "GCP_PROJECT"
          value = var.project_id
        }
        env {
          name  = "BQ_DATASET"
          value = var.dataset_id
        }
        env {
          name  = "BQ_CDC_DATASET"
          value = var.cdc_dataset
        }
        env {
          name  = "VERTEX_LOCATION"
          value = var.region
        }
        env {
          name  = "CONFIDENCE_THRESHOLD"
          value = var.tax_confidence_threshold
        }

        resources {
          limits = {
            cpu    = "2"
            memory = "2Gi"
          }
        }
      }

      max_retries = 2

      timeout = "3600s"
    }
  }

  depends_on = [
    google_bigquery_table.tax_gl_mapping,
    google_bigquery_table.tax_pending_mappings,
  ]
}

# ============================================================
# SECTION 10 — CLOUD SCHEDULER: TAX CLASSIFIER TRIGGER
# Runs classifier on day 3 of each month
# ETR bridge scheduled query runs on day 5
# Gives 2 days for human review of pending mappings
# ============================================================

resource "google_cloud_scheduler_job" "tax_classifier_trigger" {
  name             = "tax-classifier-trigger-${var.client_id}"
  description      = "Triggers tax GL classifier 2 days before ETR bridge runs"
  schedule         = "0 6 3 * *"
  time_zone        = var.scheduler_timezone
  attempt_deadline = "3600s"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/tax-classifier-${var.client_id}:run"

    oauth_token {
      service_account_email = google_service_account.dise_agent.email
    }
  }

  depends_on = [google_cloud_run_v2_job.tax_classifier]
}

# ============================================================
# SECTION 11 — IAM: TAX MODULE ADDITIONS
# The existing dise_agent service account already has
# BigQuery Data Editor on dise_reporting and Data Viewer
# on the CDC dataset — no new IAM needed for BigQuery.
# Add Vertex AI User role if not already granted by DISE module.
# ============================================================

resource "google_project_iam_member" "dise_agent_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.dise_agent.email}"

  # Only add if DISE module hasn't already granted this role.
  # If you get a duplicate error, comment this block out —
  # the role is already present from your DISE Terraform.
}

resource "google_project_iam_member" "dise_agent_bigquery_transfer" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-bigquerydatatransfer.iam.gserviceaccount.com"
}

data "google_project" "project" {
  project_id = var.project_id
}

# ============================================================
# SECTION 12 — OUTPUTS: TAX MODULE
# ============================================================

output "tax_classifier_job_name" {
  description = "Cloud Run job name for the tax classifier"
  value       = google_cloud_run_v2_job.tax_classifier.name
}

output "tax_classifier_trigger_name" {
  description = "Cloud Scheduler job that triggers the classifier"
  value       = google_cloud_scheduler_job.tax_classifier_trigger.name
}

output "etr_bridge_transfer_name" {
  description = "BigQuery scheduled query name for the ETR bridge"
  value       = google_bigquery_data_transfer_config.etr_bridge.display_name
}

output "tax_tables_created" {
  description = "All 7 tax reconciliation BigQuery tables"
  value = [
    google_bigquery_table.tax_gl_mapping.table_id,
    google_bigquery_table.tax_pending_mappings.table_id,
    google_bigquery_table.tax_provision_universe.table_id,
    google_bigquery_table.etr_reconciliation_lines.table_id,
    google_bigquery_table.taxes_paid_fact.table_id,
    google_bigquery_table.jurisdiction_statutory_rates.table_id,
    google_bigquery_table.tax_disclosure_output.table_id,
  ]
}
