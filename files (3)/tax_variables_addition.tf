# ============================================================
# Tax Reconciliation Module — Variable additions
# Append these to your existing variables.tf
# ============================================================

variable "tax_classifier_image" {
  description = "Container image URI for the tax GL classifier Cloud Run job"
  type        = string
  default     = "gcr.io/diplomatic75/tax-classifier:latest"
  # Build with: docker build -t gcr.io/{project}/tax-classifier:latest .
  # Push with:  docker push gcr.io/{project}/tax-classifier:latest
}

variable "tax_schedule_cron" {
  description = "Cron schedule for the ETR bridge BigQuery scheduled query. Default: 6am on the 5th of each month (2 days after classifier runs on the 3rd)"
  type        = string
  default     = "0 6 5 * *"
}

variable "tax_confidence_threshold" {
  description = "Gemini confidence threshold for auto-approval. Accounts below this go to human review in tax_pending_mappings."
  type        = string
  default     = "0.80"

  validation {
    condition     = tonumber(var.tax_confidence_threshold) >= 0.5 && tonumber(var.tax_confidence_threshold) <= 1.0
    error_message = "tax_confidence_threshold must be between 0.50 and 1.00"
  }
}

variable "tax_gl_account_range_start" {
  description = "Start of the SAP GL account range containing income tax accounts. Varies by client chart of accounts. diplomatic75 uses 0000160000."
  type        = string
  default     = "0000160000"
}

variable "tax_gl_account_range_end" {
  description = "End of the SAP GL account range containing income tax accounts."
  type        = string
  default     = "0000199999"
}

variable "tax_federal_statutory_rate" {
  description = "Federal statutory income tax rate as decimal. Default 0.21 for post-TCJA US rate."
  type        = number
  default     = 0.21

  validation {
    condition     = var.tax_federal_statutory_rate > 0 && var.tax_federal_statutory_rate < 1
    error_message = "Statutory rate must be between 0 and 1 (e.g. 0.21 for 21%)"
  }
}
