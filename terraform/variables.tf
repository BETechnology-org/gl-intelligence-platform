# ============================================================
# BE Technology — GL Intelligence Platform
# Terraform Variables
# ============================================================

# ── Required — must be set per client ─────────────────────────

variable "client_id" {
  description = "Short unique identifier for this client. Used in resource names. Lowercase letters, numbers, hyphens only. e.g. 'acme', 'fortune500co'"
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.client_id))
    error_message = "client_id must be lowercase letters, numbers, and hyphens only."
  }
}

variable "client_name" {
  description = "Full client company name for labels and descriptions. e.g. 'Acme Corporation'"
  type        = string
}

variable "project_id" {
  description = "GCP project ID where the client environment will be deployed. e.g. 'acme-gcp-prod'"
  type        = string
}

variable "admin_email" {
  description = "Google account email of the BE Technology admin who will have owner access to the dataset. e.g. 'mrobasson@gmail.com'"
  type        = string
}

variable "controller_email" {
  description = "Email address of the client controller who receives approval emails. e.g. 'controller@acme.com'"
  type        = string
}

variable "anthropic_api_key" {
  description = "Anthropic API key for Claude. Stored in Secret Manager — never logged."
  type        = string
  sensitive   = true
}

variable "company_code" {
  description = "SAP company code for this client. e.g. 'C006' or 'US01'"
  type        = string
}

variable "fiscal_year" {
  description = "Current fiscal year for DISE compliance. e.g. '2023'"
  type        = string
  default     = "2023"
}

# ── Optional — have sensible defaults ────────────────────────

variable "region" {
  description = "GCP region for Cloud Run and Cloud Scheduler"
  type        = string
  default     = "us-central1"
}

variable "region_suffix" {
  description = "Short suffix used in Cloud Run URLs — derived from region"
  type        = string
  default     = "uc"
}

variable "bq_location" {
  description = "BigQuery dataset location"
  type        = string
  default     = "US"
}

variable "cdc_dataset" {
  description = "Source SAP CDC dataset name in BigQuery. e.g. 'CORTEX_SAP_CDC'"
  type        = string
  default     = "CORTEX_SAP_CDC"
}

variable "environment" {
  description = "Deployment environment label"
  type        = string
  default     = "production"
  validation {
    condition     = contains(["production", "staging", "demo"], var.environment)
    error_message = "environment must be production, staging, or demo."
  }
}

variable "scheduler_timezone" {
  description = "Timezone for Cloud Scheduler nightly job"
  type        = string
  default     = "America/New_York"
}

variable "from_email" {
  description = "Gmail address used to send approval emails"
  type        = string
  default     = "mrobasson@gmail.com"
}

variable "agent_image" {
  description = "Docker image for the GL mapping agent Cloud Run job"
  type        = string
  default     = "gcr.io/diplomatic75/gl-mapping-agent:latest"
}

variable "approval_server_image" {
  description = "Docker image for the approval server Cloud Run service"
  type        = string
  default     = "gcr.io/diplomatic75/gl-approval-server:latest"
}
