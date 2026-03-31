# BE Technology — GL Intelligence Platform
# Complete Deployment Guide
# ============================================================

## What this Terraform package provisions

One `terraform apply` command creates a complete DISE compliance
environment for a new client in under 5 minutes:

- BigQuery dataset with all 7 tables and 3 views
- Service account with least-privilege IAM permissions
- Cloud Run job for the autonomous GL mapping agent
- Cloud Run service for the approval server (permanent HTTPS URL)
- Cloud Scheduler nightly trigger at 2am
- Secret Manager entry for the Anthropic API key

## Prerequisites

Install these tools before running:

```bash
# Terraform
brew install terraform          # macOS
# or download from terraform.io

# Google Cloud SDK
brew install google-cloud-sdk   # macOS
# or download from cloud.google.com/sdk

# Authenticate
gcloud auth application-default login
gcloud auth configure-docker
```

## Step 1 — Build and push Docker images (one time only)

Do this once from the diplomatic75 environment.
All clients share the same images — only the configuration changes.

```bash
# Build the mapping agent image
docker build -f Dockerfile.agent -t gcr.io/diplomatic75/gl-mapping-agent:latest .
docker push gcr.io/diplomatic75/gl-mapping-agent:latest

# Build the approval server image
docker build -f Dockerfile.approval -t gcr.io/diplomatic75/gl-approval-server:latest .
docker push gcr.io/diplomatic75/gl-approval-server:latest
```

## Step 2 — Configure a new client

Copy the example file and fill in client-specific values:

```bash
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars
```

Minimum required values:
- client_id        — short unique ID e.g. "acme-mfg"
- client_name      — full company name
- project_id       — their GCP project ID
- admin_email      — your Google account
- controller_email — their controller's email
- anthropic_api_key— your Anthropic API key
- company_code     — their SAP company code

## Step 3 — Deploy

```bash
# Initialise (first time only per machine)
terraform init

# Preview what will be created
terraform plan

# Deploy — takes about 3-5 minutes
terraform apply
```

Type `yes` when prompted. Terraform will output:
- dataset_id          — the BigQuery dataset name
- approval_server_url — the permanent HTTPS approval URL
- service_account     — the agent's service account email

## Step 4 — Load initial GL mapping data

After deployment, seed the gl_dise_mapping table by running
the mapping agent in test mode to validate accuracy, then
in run mode to classify all unmapped accounts:

```bash
export GOOGLE_CLOUD_PROJECT=<client_project_id>
export BQ_DATASET=dise_reporting_<client_id>
export BQ_CDC_DATASET=CORTEX_SAP_CDC
export COMPANY_CODE=<client_company_code>
export FISCAL_YEAR=2024
export ANTHROPIC_API_KEY=<your_key>

# Accuracy test first
python mapping_agent.py test

# If accuracy >= 85%, run the agent
python mapping_agent.py run
```

## Step 5 — Verify deployment

Run these queries in the client's BigQuery to confirm:

```sql
-- Confirm all tables exist
SELECT table_name, table_type
FROM `<project>.dise_reporting_<client_id>.INFORMATION_SCHEMA.TABLES`
ORDER BY table_name;

-- Confirm DISE pivot view works
SELECT * FROM `<project>.dise_reporting_<client_id>.v_dise_pivot`
WHERE fiscal_year = '2024'
LIMIT 10;
```

## Destroying a client environment

To remove all resources for a client:

```bash
terraform destroy
```

Note: gl_dise_mapping and mapping_decisions_log have
deletion_protection = true — these must be manually
disabled in BigQuery before destroy will complete.
This is intentional — it prevents accidental deletion
of audit trail data.

## Multi-client management

To manage multiple clients, use Terraform workspaces:

```bash
# Create workspace for each client
terraform workspace new acme-mfg
terraform workspace new retailco

# Switch between clients
terraform workspace select acme-mfg
terraform apply -var-file=clients/acme-mfg.tfvars

terraform workspace select retailco
terraform apply -var-file=clients/retailco.tfvars

# List all client environments
terraform workspace list
```

## Cost estimate per client per month

- BigQuery storage: ~$5-20 depending on data volume
- Cloud Run (agent job, nightly): ~$2-5
- Cloud Run (approval server, always-on): ~$15-30
- Cloud Scheduler: < $1
- Secret Manager: < $1
Total: approximately $25-60 per client per month

At $80K-$150K per client per year, infrastructure cost
is less than 0.1% of revenue per client.
