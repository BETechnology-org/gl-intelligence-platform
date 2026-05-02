# ============================================================
# Tax Reconciliation Module — tfvars additions
# Add these to your existing terraform.tfvars
# ============================================================

# ── Tax classifier Cloud Run image ────────────────────────────
# Build and push tax_03_classifier.py before running terraform apply:
#
#   cd /path/to/tax_classifier
#   docker build -t gcr.io/diplomatic75/tax-classifier:latest .
#   docker push gcr.io/diplomatic75/tax-classifier:latest
#
tax_classifier_image = "gcr.io/diplomatic75/tax-classifier:latest"

# ── Scheduling ────────────────────────────────────────────────
# Classifier runs day 3, ETR bridge runs day 5
# Gives 2 days for human review of pending mappings before
# the bridge SQL runs and produces disclosure output
tax_schedule_cron        = "0 6 5 * *"

# ── Classification settings ───────────────────────────────────
tax_confidence_threshold = "0.80"

# ── SAP GL account range for diplomatic75 ────────────────────
# Validated against CORTEX_SAP_CDC.bseg — tax accounts live here
tax_gl_account_range_start = "0000160000"
tax_gl_account_range_end   = "0000199999"

# ── Federal statutory rate ────────────────────────────────────
tax_federal_statutory_rate = 0.21
