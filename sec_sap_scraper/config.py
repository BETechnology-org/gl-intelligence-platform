"""
Configuration for SEC EDGAR ERP scraper.
Update USER_AGENT with your real name and email — SEC requires this.
"""

# SEC requires a User-Agent with your name and email
USER_AGENT = "BE Technology Solutions info@betechnology.com"

# Rate limit: SEC allows max 10 requests/second
RATE_LIMIT_CALLS = 8
RATE_LIMIT_PERIOD = 1  # seconds

# Filing types to search (10-K = annual, 10-Q = quarterly)
FILING_TYPES = ["10-K", "10-Q"]

# --- ERP KEYWORD GROUPS ---
# Each group: { "name": ..., "keywords": [...] }
# The scraper iterates all groups and tags each company with which ERP(s) they use.

ERP_KEYWORDS = {
    "SAP": [
        '"SAP ERP"',
        '"SAP S/4HANA"',
        '"SAP HANA"',
        '"SAP system"',
        '"SAP software"',
        '"SAP enterprise"',
        '"SAP implementation"',
        '"SAP platform"',
        '"SAP modules"',
        '"SAP R/3"',
        '"SAP Business One"',
        '"SAP SuccessFactors"',
        '"SAP Ariba"',
        '"SAP Concur"',
        '"SAP Fieldglass"',
    ],
    "Salesforce": [
        '"Salesforce CRM"',
        '"Salesforce platform"',
        '"Salesforce implementation"',
        '"Salesforce system"',
        '"Salesforce software"',
        '"Sales Cloud"',
        '"Service Cloud"',
        '"Salesforce Commerce Cloud"',
        '"Salesforce Marketing Cloud"',
        '"MuleSoft"',
        '"Salesforce Tableau"',
        '"Salesforce Einstein"',
        '"Salesforce integration"',
        '"Slack" AND "Salesforce"',
    ],
    "Oracle": [
        '"Oracle ERP"',
        '"Oracle Cloud"',
        '"Oracle Fusion"',
        '"Oracle NetSuite"',
        '"NetSuite ERP"',
        '"Oracle E-Business Suite"',
        '"Oracle EBS"',
        '"Oracle system"',
        '"Oracle implementation"',
        '"Oracle HCM"',
        '"Oracle Financials"',
        '"Oracle PeopleSoft"',
        '"PeopleSoft"',
        '"JD Edwards"',
        '"Oracle Hyperion"',
    ],
}

# Output files
OUTPUT_DIR = "output"
OUTPUT_CSV = "erp_companies.csv"
OUTPUT_XLSX = "erp_companies.xlsx"
