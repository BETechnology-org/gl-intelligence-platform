"""Tax module agents — ASU 2023-09 + ASC 740 compliance.

Three agents:
- TaxClassifierAgent  — Step 2: classify GL accounts into ASC 740 categories
- ETRBridgeAgent      — Step 4: aggregate approved mappings into Tables A/B/C
- TaxDisclosureAgent  — Step 5: generate full ASC 740 footnote narrative
"""
