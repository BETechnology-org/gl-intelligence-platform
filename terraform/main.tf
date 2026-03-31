# ============================================================
# BE Technology — GL Intelligence Platform
# Terraform — Complete DISE Client Environment
# ============================================================
# Usage:
#   terraform init
#   terraform plan -var="client_id=acme" -var="project_id=acme-gcp-prod"
#   terraform apply -var="client_id=acme" -var="project_id=acme-gcp-prod"
#
# This provisions a complete DISE environment for one client:
#   - BigQuery dataset with all tables and views
#   - IAM service account with least-privilege permissions
#   - Cloud Run job for the GL mapping agent
#   - Cloud Run service for the approval server
#   - Cloud Scheduler nightly trigger
#   - Secret Manager entries for credentials
# ============================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# ── Provider ──────────────────────────────────────────────────
provider "google" {
  project = var.project_id
  region  = var.region
}

# ── Local computed values ─────────────────────────────────────
locals {
  dataset_id    = "dise_reporting_${var.client_id}"
  sa_account_id = "dise-agent-${var.client_id}"
  sa_email      = "${local.sa_account_id}@${var.project_id}.iam.gserviceaccount.com"
  labels = {
    managed_by  = "terraform"
    platform    = "gl-intelligence"
    client      = var.client_id
    environment = var.environment
  }
}

# ============================================================
# SECTION 1 — BIGQUERY DATASET
# ============================================================

resource "google_bigquery_dataset" "dise_reporting" {
  dataset_id                 = local.dataset_id
  friendly_name              = "DISE Reporting — ${var.client_name}"
  description                = "BE Technology GL Intelligence Platform — DISE compliance dataset for ${var.client_name}. ASU 2024-03 / ASC 220-40."
  location                   = var.bq_location
  delete_contents_on_destroy = false

  labels = local.labels

  access {
    role          = "OWNER"
    user_by_email = var.admin_email
  }
  access {
    role          = "WRITER"
    user_by_email = local.sa_email
  }
}

# ============================================================
# SECTION 2 — BIGQUERY TABLES
# ============================================================

# ── gl_dise_mapping ───────────────────────────────────────────
resource "google_bigquery_table" "gl_dise_mapping" {
  dataset_id          = google_bigquery_dataset.dise_reporting.dataset_id
  table_id            = "gl_dise_mapping"
  deletion_protection = true
  description         = "GL account to DISE category mapping. Core classification layer for the DISE pivot. Every approved mapping decision lives here."
  labels              = local.labels

  schema = jsonencode([
    {name="gl_account",      type="STRING",    mode="REQUIRED", description="SAP GL account number (HKONT)"},
    {name="description",     type="STRING",    mode="NULLABLE", description="Account description from skat.txt50"},
    {name="dise_category",   type="STRING",    mode="NULLABLE", description="DISE natural expense category — must be one of the 5 ASC 220-40 categories"},
    {name="expense_caption", type="STRING",    mode="NULLABLE", description="Income statement caption: COGS | SG&A | R&D | Other income/expense"},
    {name="status",          type="STRING",    mode="NULLABLE", description="mapped | unmapped | review"},
    {name="notes",           type="STRING",    mode="NULLABLE", description="Methodology notes and rationale"},
    {name="reviewer",        type="STRING",    mode="NULLABLE", description="Name or email of approving reviewer"},
    {name="asc_citation",    type="STRING",    mode="NULLABLE", description="ASC citation e.g. ASC 220-40-50-6(c)"}
  ])
}

# ── pending_mappings ──────────────────────────────────────────
resource "google_bigquery_table" "pending_mappings" {
  dataset_id          = google_bigquery_dataset.dise_reporting.dataset_id
  table_id            = "pending_mappings"
  deletion_protection = false
  description         = "Agent working memory. Draft mapping decisions awaiting human approval before promotion to gl_dise_mapping."
  labels              = local.labels

  schema = jsonencode([
    {name="gl_account",         type="STRING",    mode="REQUIRED"},
    {name="description",        type="STRING",    mode="NULLABLE"},
    {name="posting_amount",     type="NUMERIC",   mode="NULLABLE"},
    {name="fiscal_year",        type="STRING",    mode="NULLABLE"},
    {name="company_code",       type="STRING",    mode="NULLABLE"},
    {name="suggested_category", type="STRING",    mode="NULLABLE"},
    {name="suggested_caption",  type="STRING",    mode="NULLABLE"},
    {name="suggested_citation", type="STRING",    mode="NULLABLE"},
    {name="draft_reasoning",    type="STRING",    mode="NULLABLE"},
    {name="confidence_score",   type="FLOAT64",   mode="NULLABLE"},
    {name="confidence_label",   type="STRING",    mode="NULLABLE"},
    {name="similar_accounts",   type="STRING",    mode="NULLABLE"},
    {name="materiality_flag",   type="STRING",    mode="NULLABLE"},
    {name="status",             type="STRING",    mode="REQUIRED"},
    {name="reviewed_category",  type="STRING",    mode="NULLABLE"},
    {name="reviewed_caption",   type="STRING",    mode="NULLABLE"},
    {name="reviewed_citation",  type="STRING",    mode="NULLABLE"},
    {name="override_reason",    type="STRING",    mode="NULLABLE"},
    {name="reviewer",           type="STRING",    mode="NULLABLE"},
    {name="reviewed_at",        type="TIMESTAMP", mode="NULLABLE"},
    {name="drafted_by",         type="STRING",    mode="NULLABLE"},
    {name="drafted_at",         type="TIMESTAMP", mode="NULLABLE"},
    {name="model_version",      type="STRING",    mode="NULLABLE"},
    {name="prompt_version",     type="STRING",    mode="NULLABLE"}
  ])
}

# ── mapping_decisions_log ─────────────────────────────────────
resource "google_bigquery_table" "mapping_decisions_log" {
  dataset_id          = google_bigquery_dataset.dise_reporting.dataset_id
  table_id            = "mapping_decisions_log"
  deletion_protection = true
  description         = "Immutable audit trail. Every agent action and human decision written here permanently. Auditor evidence package."
  labels              = local.labels

  schema = jsonencode([
    {name="event_id",        type="STRING",    mode="REQUIRED"},
    {name="event_type",      type="STRING",    mode="REQUIRED"},
    {name="event_timestamp", type="TIMESTAMP", mode="REQUIRED"},
    {name="gl_account",      type="STRING",    mode="REQUIRED"},
    {name="description",     type="STRING",    mode="NULLABLE"},
    {name="fiscal_year",     type="STRING",    mode="NULLABLE"},
    {name="company_code",    type="STRING",    mode="NULLABLE"},
    {name="posting_amount",  type="NUMERIC",   mode="NULLABLE"},
    {name="agent_category",  type="STRING",    mode="NULLABLE"},
    {name="agent_caption",   type="STRING",    mode="NULLABLE"},
    {name="agent_citation",  type="STRING",    mode="NULLABLE"},
    {name="agent_confidence",type="FLOAT64",   mode="NULLABLE"},
    {name="agent_reasoning", type="STRING",    mode="NULLABLE"},
    {name="final_category",  type="STRING",    mode="NULLABLE"},
    {name="final_caption",   type="STRING",    mode="NULLABLE"},
    {name="final_citation",  type="STRING",    mode="NULLABLE"},
    {name="human_agreed",    type="BOOL",      mode="NULLABLE"},
    {name="override_reason", type="STRING",    mode="NULLABLE"},
    {name="actor",           type="STRING",    mode="NULLABLE"},
    {name="actor_type",      type="STRING",    mode="NULLABLE"},
    {name="model_version",   type="STRING",    mode="NULLABLE"},
    {name="prompt_version",  type="STRING",    mode="NULLABLE"}
  ])
}

# ── close_tasks ───────────────────────────────────────────────
resource "google_bigquery_table" "close_tasks" {
  dataset_id          = google_bigquery_dataset.dise_reporting.dataset_id
  table_id            = "close_tasks"
  deletion_protection = false
  description         = "DISE close tracker. Six tasks driven by live BigQuery data queries."
  labels              = local.labels

  schema = jsonencode([
    {name="task_id",        type="STRING",    mode="REQUIRED"},
    {name="task_name",      type="STRING",    mode="REQUIRED"},
    {name="task_category",  type="STRING",    mode="REQUIRED"},
    {name="description",    type="STRING",    mode="NULLABLE"},
    {name="status_query",   type="STRING",    mode="REQUIRED"},
    {name="fiscal_year",    type="STRING",    mode="REQUIRED"},
    {name="fiscal_period",  type="STRING",    mode="REQUIRED"},
    {name="company_code",   type="STRING",    mode="REQUIRED"},
    {name="owner_name",     type="STRING",    mode="NULLABLE"},
    {name="owner_email",    type="STRING",    mode="NULLABLE"},
    {name="due_date",       type="DATE",      mode="NULLABLE"},
    {name="is_complete",    type="BOOL",      mode="NULLABLE"},
    {name="metric_value",   type="STRING",    mode="NULLABLE"},
    {name="detail",         type="STRING",    mode="NULLABLE"},
    {name="last_checked_at",type="TIMESTAMP", mode="NULLABLE"},
    {name="completed_at",   type="TIMESTAMP", mode="NULLABLE"},
    {name="created_at",     type="TIMESTAMP", mode="NULLABLE"},
    {name="sort_order",     type="INT64",     mode="NULLABLE"}
  ])
}

# ── close_task_history ────────────────────────────────────────
resource "google_bigquery_table" "close_task_history" {
  dataset_id          = google_bigquery_dataset.dise_reporting.dataset_id
  table_id            = "close_task_history"
  deletion_protection = false
  description         = "Historical record of close task status changes."
  labels              = local.labels

  schema = jsonencode([
    {name="history_id",   type="STRING",    mode="NULLABLE"},
    {name="task_id",      type="STRING",    mode="REQUIRED"},
    {name="fiscal_year",  type="STRING",    mode="REQUIRED"},
    {name="fiscal_period",type="STRING",    mode="REQUIRED"},
    {name="checked_at",   type="TIMESTAMP", mode="REQUIRED"},
    {name="was_complete", type="BOOL",      mode="NULLABLE"},
    {name="metric_value", type="STRING",    mode="NULLABLE"},
    {name="detail",       type="STRING",    mode="NULLABLE"},
    {name="changed_from", type="STRING",    mode="NULLABLE"},
    {name="changed_to",   type="STRING",    mode="NULLABLE"}
  ])
}

# ── anomaly_alerts ────────────────────────────────────────────
resource "google_bigquery_table" "anomaly_alerts" {
  dataset_id          = google_bigquery_dataset.dise_reporting.dataset_id
  table_id            = "anomaly_alerts"
  deletion_protection = false
  description         = "Statistical anomaly alerts from DISE category monitoring. Tiered P1/P2/P3 priority."
  labels              = local.labels

  schema = jsonencode([
    {name="alert_id",       type="STRING",    mode="NULLABLE"},
    {name="fiscal_year",    type="STRING",    mode="REQUIRED"},
    {name="fiscal_period",  type="STRING",    mode="REQUIRED"},
    {name="company_code",   type="STRING",    mode="REQUIRED"},
    {name="alert_date",     type="DATE",      mode="NULLABLE"},
    {name="alert_priority", type="STRING",    mode="NULLABLE"},
    {name="dise_category",  type="STRING",    mode="NULLABLE"},
    {name="expense_caption",type="STRING",    mode="NULLABLE"},
    {name="posting_period", type="STRING",    mode="NULLABLE"},
    {name="actual_amount",  type="FLOAT64",   mode="NULLABLE"},
    {name="expected_amount",type="FLOAT64",   mode="NULLABLE"},
    {name="deviation_pct",  type="FLOAT64",   mode="NULLABLE"},
    {name="alert_message",  type="STRING",    mode="NULLABLE"},
    {name="status",         type="STRING",    mode="NULLABLE"},
    {name="reviewed_by",    type="STRING",    mode="NULLABLE"},
    {name="reviewed_at",    type="TIMESTAMP", mode="NULLABLE"},
    {name="resolution_note",type="STRING",    mode="NULLABLE"},
    {name="created_at",     type="TIMESTAMP", mode="NULLABLE"}
  ])
}

# ── disclosure_approvals ──────────────────────────────────────
resource "google_bigquery_table" "disclosure_approvals" {
  dataset_id          = google_bigquery_dataset.dise_reporting.dataset_id
  table_id            = "disclosure_approvals"
  deletion_protection = false
  description         = "CFO and Controller approval records for DISE disclosure drafts."
  labels              = local.labels

  schema = jsonencode([
    {name="approval_id",     type="STRING",    mode="NULLABLE"},
    {name="fiscal_year",     type="STRING",    mode="REQUIRED"},
    {name="fiscal_period",   type="STRING",    mode="REQUIRED"},
    {name="company_code",    type="STRING",    mode="REQUIRED"},
    {name="approved_by",     type="STRING",    mode="NULLABLE"},
    {name="approved_at",     type="TIMESTAMP", mode="NULLABLE"},
    {name="approval_status", type="STRING",    mode="NULLABLE"},
    {name="comments",        type="STRING",    mode="NULLABLE"},
    {name="disclosure_hash", type="STRING",    mode="NULLABLE"}
  ])
}

# ============================================================
# SECTION 3 — BIGQUERY VIEWS
# ============================================================

resource "google_bigquery_table" "v_close_tracker" {
  dataset_id          = google_bigquery_dataset.dise_reporting.dataset_id
  table_id            = "v_close_tracker"
  deletion_protection = false
  description         = "Close tracker view with computed status field."
  labels              = local.labels

  view {
    query = <<-EOT
      SELECT
        task_id, task_name, task_category, description,
        owner_name, due_date, is_complete, metric_value, detail,
        last_checked_at, completed_at, sort_order,
        fiscal_year, fiscal_period, company_code,
        CASE WHEN is_complete THEN 'COMPLETE' ELSE 'OPEN' END AS task_status,
        CASE WHEN is_complete THEN 1 ELSE 0 END AS complete_flag
      FROM `${var.project_id}.${local.dataset_id}.close_tasks`
      ORDER BY sort_order
    EOT
    use_legacy_sql = false
  }

  depends_on = [google_bigquery_table.close_tasks]
}

resource "google_bigquery_table" "v_anomaly_alerts" {
  dataset_id          = google_bigquery_dataset.dise_reporting.dataset_id
  table_id            = "v_anomaly_alerts"
  deletion_protection = false
  description         = "Anomaly alerts view with priority sort."
  labels              = local.labels

  view {
    query = <<-EOT
      SELECT
        alert_id, fiscal_year, fiscal_period, company_code,
        alert_date, alert_priority, dise_category, expense_caption,
        posting_period, actual_amount, expected_amount, deviation_pct,
        alert_message, status, reviewed_by, resolution_note,
        CASE alert_priority
          WHEN 'P1' THEN 1
          WHEN 'P2' THEN 2
          ELSE 3
        END AS priority_sort
      FROM `${var.project_id}.${local.dataset_id}.anomaly_alerts`
      ORDER BY priority_sort, deviation_pct DESC
    EOT
    use_legacy_sql = false
  }

  depends_on = [google_bigquery_table.anomaly_alerts]
}

resource "google_bigquery_table" "v_dise_pivot" {
  dataset_id          = google_bigquery_dataset.dise_reporting.dataset_id
  table_id            = "v_dise_pivot"
  deletion_protection = false
  description         = "Live DISE pivot view joining SAP CDC data to GL mapping."
  labels              = local.labels

  view {
    query = <<-EOT
      SELECT
        m.expense_caption,
        m.dise_category,
        bkpf.GJAHR AS fiscal_year,
        ROUND(SUM(bseg.DMBTR), 0) AS amount
      FROM `${var.project_id}.${var.cdc_dataset}.bkpf` bkpf
      JOIN `${var.project_id}.${var.cdc_dataset}.bseg` bseg
        ON  bkpf.MANDT = bseg.MANDT
        AND bkpf.BUKRS = bseg.BUKRS
        AND bkpf.BELNR = bseg.BELNR
        AND bkpf.GJAHR = bseg.GJAHR
      JOIN `${var.project_id}.${local.dataset_id}.gl_dise_mapping` m
        ON  bseg.HKONT = m.gl_account
      WHERE bkpf.BLART NOT IN ('AA','AF','AB')
        AND m.status = 'mapped'
      GROUP BY 1,2,3
    EOT
    use_legacy_sql = false
  }

  depends_on = [
    google_bigquery_table.gl_dise_mapping
  ]
}

# ============================================================
# SECTION 4 — SERVICE ACCOUNT AND IAM
# ============================================================

resource "google_service_account" "dise_agent" {
  account_id   = local.sa_account_id
  display_name = "DISE GL Mapping Agent — ${var.client_name}"
  description  = "Service account for BE Technology GL Intelligence Platform. Least-privilege access to BigQuery and Cloud Run."
}

# BigQuery data editor on the DISE dataset
resource "google_bigquery_dataset_iam_member" "dise_agent_editor" {
  dataset_id = google_bigquery_dataset.dise_reporting.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dise_agent.email}"
}

# BigQuery job user — needed to run queries
resource "google_project_iam_member" "dise_agent_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.dise_agent.email}"
}

# Read access to SAP CDC dataset
resource "google_bigquery_dataset_iam_member" "dise_agent_cdc_reader" {
  dataset_id = var.cdc_dataset
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.dise_agent.email}"
}

# Secret Manager access for API keys
resource "google_project_iam_member" "dise_agent_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.dise_agent.email}"
}

# ============================================================
# SECTION 5 — SECRET MANAGER
# ============================================================

resource "google_secret_manager_secret" "anthropic_api_key" {
  secret_id = "dise-anthropic-api-key-${var.client_id}"
  labels    = local.labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "anthropic_api_key" {
  secret      = google_secret_manager_secret.anthropic_api_key.id
  secret_data = var.anthropic_api_key
}

# ============================================================
# SECTION 6 — CLOUD RUN: MAPPING AGENT JOB
# ============================================================

resource "google_cloud_run_v2_job" "mapping_agent" {
  name     = "dise-mapping-agent-${var.client_id}"
  location = var.region
  labels   = local.labels

  template {
    template {
      service_account = google_service_account.dise_agent.email
      max_retries     = 2

      containers {
        image = var.agent_image

        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        env {
          name  = "BQ_DATASET"
          value = local.dataset_id
        }
        env {
          name  = "BQ_CDC_DATASET"
          value = var.cdc_dataset
        }
        env {
          name  = "COMPANY_CODE"
          value = var.company_code
        }
        env {
          name  = "FISCAL_YEAR"
          value = var.fiscal_year
        }
        env {
          name  = "APPROVAL_BASE_URL"
          value = "https://dise-approval-${var.client_id}-${var.region_suffix}.a.run.app"
        }
        env {
          name = "ANTHROPIC_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.anthropic_api_key.secret_id
              version = "latest"
            }
          }
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }
    }
  }

  depends_on = [
    google_service_account.dise_agent,
    google_secret_manager_secret_version.anthropic_api_key
  ]
}

# ============================================================
# SECTION 7 — CLOUD RUN: APPROVAL SERVER
# ============================================================

resource "google_cloud_run_v2_service" "approval_server" {
  name     = "dise-approval-${var.client_id}"
  location = var.region
  labels   = local.labels

  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.dise_agent.email
    labels          = local.labels

    containers {
      image = var.approval_server_image

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "BQ_DATASET"
        value = local.dataset_id
      }
      env {
        name  = "FROM_EMAIL"
        value = var.from_email
      }
      env {
        name  = "TO_EMAIL"
        value = var.controller_email
      }
      env {
        name = "ANTHROPIC_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.anthropic_api_key.secret_id
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      ports {
        container_port = 8080
      }
    }
  }

  depends_on = [
    google_service_account.dise_agent,
    google_secret_manager_secret_version.anthropic_api_key
  ]
}

# Allow unauthenticated access to approval server
# (approval links in emails must be clickable without login)
resource "google_cloud_run_service_iam_member" "approval_public" {
  location = google_cloud_run_v2_service.approval_server.location
  service  = google_cloud_run_v2_service.approval_server.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ============================================================
# SECTION 8 — CLOUD SCHEDULER: NIGHTLY AGENT TRIGGER
# ============================================================

resource "google_cloud_scheduler_job" "nightly_mapping_agent" {
  name        = "dise-nightly-mapping-${var.client_id}"
  description = "Triggers GL mapping agent nightly at 2am to detect unmapped accounts"
  schedule    = "0 2 * * *"
  time_zone   = var.scheduler_timezone
  region      = var.region

  http_target {
    http_method = "POST"
    uri = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.mapping_agent.name}:run"

    oauth_token {
      service_account_email = google_service_account.dise_agent.email
    }
  }

  depends_on = [google_cloud_run_v2_job.mapping_agent]
}

# ============================================================
# SECTION 9 — OUTPUTS
# ============================================================

output "dataset_id" {
  description = "BigQuery dataset ID for this client"
  value       = google_bigquery_dataset.dise_reporting.dataset_id
}

output "service_account_email" {
  description = "Service account email for the mapping agent"
  value       = google_service_account.dise_agent.email
}

output "approval_server_url" {
  description = "Cloud Run URL for the approval server"
  value       = google_cloud_run_v2_service.approval_server.uri
}

output "mapping_agent_job_name" {
  description = "Cloud Run job name for the mapping agent"
  value       = google_cloud_run_v2_job.mapping_agent.name
}

output "scheduler_job_name" {
  description = "Cloud Scheduler job name"
  value       = google_cloud_scheduler_job.nightly_mapping_agent.name
}

output "dise_pivot_view" {
  description = "Fully qualified DISE pivot view"
  value       = "${var.project_id}.${local.dataset_id}.v_dise_pivot"
}
