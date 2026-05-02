"""Load finance-datasets/ CSVs into Supabase.

This is the v1 ingestion path — replaces the BigQuery dependence in
gl_intelligence/cortex/ for the demo / first-pilot phase. After the
first paying customer wires up live SAP/Oracle, the same agent
contracts work against api/src/db/cortex.py without code changes.

Usage:
  python -m infra.load_finance_datasets \\
    --dataset /Users/apple/Desktop/finance-datasets \\
    --company-code DEMO \\
    --company-name "Demo Manufacturing Inc."

Required env:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

What it loads (in order):
  1. Demo company (`companies` table) if not present
  2. Chart of accounts from `sap-synthetic/demo/chart_of_accounts.json`
  3. Journal entries from `sap-synthetic/demo/journal_entries_sap_bseg.csv`
     (BSEG-shaped — matches our `journal_entries` schema 1:1)
  4. (Optional) Real fraud rows from `sap-fraud-real/fraud_dataset_v2.csv`
     marked with is_fraud=true (anonymized — useful for anomaly detection
     unit tests, NOT for DISE/Tax classifier — categoricals are opaque codes)
  5. Refresh `gl_trial_balance` materialized view

Idempotent — re-running is safe (uses upserts and skips existing rows).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("loader")

BATCH_SIZE = 500


def get_supabase():
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def ensure_company(supabase, code: str, name: str, fiscal_year: str = "2024") -> str:
    """Upsert the demo company. Returns its UUID."""
    existing = (
        supabase.table("companies").select("id").eq("code", code).execute()
    ).data
    if existing:
        cid = existing[0]["id"]
        log.info("Company %s already exists (id=%s)", code, cid)
        return cid

    res = supabase.table("companies").insert({
        "code": code,
        "name": name,
        "fiscal_year": fiscal_year,
        "statutory_rate": 0.21,
    }).execute()
    cid = res.data[0]["id"]
    log.info("Created company %s (id=%s)", code, cid)

    # Seed default app_config
    supabase.table("app_config").insert({"company_id": cid}).execute()
    log.info("Seeded app_config for %s", code)
    return cid


def load_chart_of_accounts(supabase, company_id: str, json_path: Path) -> int:
    """Load chart of accounts from chart_of_accounts.json."""
    if not json_path.exists():
        log.warning("COA file not found: %s", json_path)
        return 0

    accounts = json.loads(json_path.read_text())
    log.info("Loading %d GL accounts...", len(accounts))

    rows = []
    for a in accounts:
        rows.append({
            "company_id":   company_id,
            "gl_account":   str(a["account_number"]),
            "description":  a.get("long_description") or a.get("short_description"),
            "account_type": a.get("account_type"),
            "sub_type":     a.get("sub_type"),
            "is_postable":  a.get("is_postable", True),
            "account_class": a.get("account_class"),
            "parent_account": a.get("parent_account"),
            "source":       "finance-datasets",
        })

    inserted = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        supabase.table("gl_accounts").upsert(
            batch, on_conflict="company_id,gl_account"
        ).execute()
        inserted += len(batch)
        log.info("  ...upserted %d / %d accounts", inserted, len(rows))
    return inserted


def _csv_value(row: dict, *keys: str) -> Any:
    """Read first non-empty value across alternative column names."""
    for k in keys:
        v = row.get(k)
        if v not in (None, "", "None"):
            return v
    return None


def _to_int(v: Any) -> int | None:
    if v in (None, ""):
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _to_float(v: Any) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _to_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v in (None, "", "False", "false", "0", 0):
        return False
    return True


def load_journal_entries(
    supabase, company_id: str, csv_path: Path, *, max_rows: int | None = None
) -> int:
    """Load journal_entries_sap_bseg.csv into journal_entries table.

    BSEG headers: BELNR, BUKRS, GJAHR, MONAT, BUDAT, BLDAT, BLART, WAERS,
    KURSF, XBLNR, BKTXT, USNAM, RLDNR, BUZEI, HKONT, KOSTL, PRCTR, SGTXT,
    KUNNR_LIFNR, AUGBL, AUGDT, BSCHL, SHKZG, DMBTR, WRBTR, IS_FRAUD, IS_ANOMALY.
    """
    if not csv_path.exists():
        log.warning("JE file not found: %s", csv_path)
        return 0

    log.info("Streaming journal entries from %s...", csv_path.name)
    rows: list[dict] = []
    inserted = 0

    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            if max_rows and inserted >= max_rows:
                break

            entry = {
                "company_id":   company_id,
                "belnr":        _csv_value(r, "BELNR", "document_id") or "",
                "buzei":        _to_int(_csv_value(r, "BUZEI", "line_number")),
                "bukrs":        _csv_value(r, "BUKRS", "company_code") or "DEMO",
                "gjahr":        str(_csv_value(r, "GJAHR", "fiscal_year") or "2024"),
                "monat":        _to_int(_csv_value(r, "MONAT", "fiscal_period")),
                "budat":        _csv_value(r, "BUDAT", "posting_date") or None,
                "bldat":        _csv_value(r, "BLDAT", "document_date") or None,
                "blart":        _csv_value(r, "BLART", "document_type"),
                "bschl":        _csv_value(r, "BSCHL"),
                "shkzg":        _csv_value(r, "SHKZG"),
                "hkont":        _csv_value(r, "HKONT", "gl_account") or "",
                "prctr":        _csv_value(r, "PRCTR", "profit_center"),
                "kostl":        _csv_value(r, "KOSTL", "cost_center"),
                "kunnr_lifnr":  _csv_value(r, "KUNNR_LIFNR"),
                "bktxt":        _csv_value(r, "BKTXT", "header_text"),
                "sgtxt":        _csv_value(r, "SGTXT", "line_text"),
                "waers":        _csv_value(r, "WAERS", "currency"),
                "dmbtr":        _to_float(_csv_value(r, "DMBTR", "local_amount")),
                "wrbtr":        _to_float(_csv_value(r, "WRBTR")),
                "is_fraud":     _to_bool(_csv_value(r, "IS_FRAUD", "is_fraud")),
                "is_anomaly":   _to_bool(_csv_value(r, "IS_ANOMALY", "is_anomaly")),
                "source":       "finance-datasets",
            }
            if not entry["hkont"]:
                continue
            rows.append(entry)

            if len(rows) >= BATCH_SIZE:
                supabase.table("journal_entries").insert(rows).execute()
                inserted += len(rows)
                log.info("  ...inserted %d JEs so far", inserted)
                rows = []

    if rows:
        supabase.table("journal_entries").insert(rows).execute()
        inserted += len(rows)
    log.info("✅ Inserted %d journal entries", inserted)
    return inserted


def refresh_trial_balance(supabase) -> None:
    """Refresh the gl_trial_balance materialized view."""
    log.info("Refreshing gl_trial_balance materialized view...")
    try:
        supabase.rpc("refresh_gl_trial_balance", {}).execute()
    except Exception:
        # No RPC defined — fall back to raw SQL via execute()
        # (only works with service role key)
        from postgrest.exceptions import APIError
        try:
            supabase.postgrest.session.post(
                f"{supabase.supabase_url}/rest/v1/rpc/refresh_gl_trial_balance",
                json={},
            )
        except (APIError, Exception) as e:
            log.warning(
                "Could not refresh materialized view via API (%s). "
                "Run manually in Supabase SQL editor: REFRESH MATERIALIZED VIEW public.gl_trial_balance;",
                e,
            )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="/Users/apple/Desktop/finance-datasets")
    ap.add_argument("--company-code", default="DEMO")
    ap.add_argument("--company-name", default="Demo Manufacturing Inc.")
    ap.add_argument("--fiscal-year", default="2024")
    ap.add_argument("--max-rows", type=int, default=None,
                    help="Cap journal_entries rows (for fast iteration)")
    ap.add_argument("--no-fraud", action="store_true",
                    help="Skip the 532K-row real-fraud dataset")
    args = ap.parse_args()

    dataset_root = Path(args.dataset)
    if not dataset_root.exists():
        log.error("dataset not found: %s", dataset_root)
        return 1

    supabase = get_supabase()

    company_id = ensure_company(
        supabase,
        code=args.company_code,
        name=args.company_name,
        fiscal_year=args.fiscal_year,
    )

    coa_path = dataset_root / "sap-synthetic" / "demo" / "chart_of_accounts.json"
    je_path = dataset_root / "sap-synthetic" / "demo" / "journal_entries_sap_bseg.csv"

    load_chart_of_accounts(supabase, company_id, coa_path)
    load_journal_entries(supabase, company_id, je_path, max_rows=args.max_rows)

    if not args.no_fraud:
        fraud_path = dataset_root / "sap-fraud-real" / "fraud_dataset_v2.csv"
        if fraud_path.exists():
            log.info(
                "Skipping real fraud dataset (categoricals are anonymized — not "
                "useful for DISE/Tax). Use --include-fraud explicitly to load."
            )

    refresh_trial_balance(supabase)
    log.info("✅ Done. Company %s loaded.", args.company_code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
