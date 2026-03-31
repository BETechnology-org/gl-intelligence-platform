"""
Cortex Data Access Layer
Unified interface to SAP, Oracle EBS, and Salesforce data via Google Cortex Framework + BigQuery.
"""

from gl_intelligence.cortex.client import CortexClient
from gl_intelligence.cortex.sap import SAPConnector
from gl_intelligence.cortex.oracle import OracleEBSConnector
from gl_intelligence.cortex.salesforce import SalesforceConnector
