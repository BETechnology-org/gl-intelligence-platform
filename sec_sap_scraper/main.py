#!/usr/bin/env python3
"""
SEC EDGAR ERP Scraper — Main entry point.

Finds public companies that mention SAP, Salesforce, or Oracle
in their SEC filings, enriches with company data, exports to CSV/Excel.

Usage:
    python main.py                              # all ERPs, last 2 years
    python main.py --erp SAP Oracle             # only SAP and Oracle
    python main.py --from 2024-01-01            # custom start date
    python main.py --skip-enrich                # skip enrichment (faster)
    python main.py --enrich-limit 100           # enrich top 100 only
"""

import argparse
import json
import os
import sys

import pandas as pd

from config import OUTPUT_CSV, OUTPUT_DIR, OUTPUT_XLSX
from scraper import enrich_companies, run_scraper


def save_results(companies: list, output_dir: str):
    """Save results to CSV, Excel, and JSON."""
    os.makedirs(output_dir, exist_ok=True)

    # Flatten lists to strings for tabular formats
    for c in companies:
        if isinstance(c.get("erp_vendors"), list):
            c["erp_vendors"] = " | ".join(c["erp_vendors"])
        if isinstance(c.get("keywords_found"), list):
            c["keywords_found"] = " | ".join(c["keywords_found"])

    df = pd.DataFrame(companies)

    # Reorder columns
    priority_cols = [
        "company_name", "ticker", "exchanges", "cik",
        "erp_vendors", "filing_count",
        "sic_description", "sic", "category",
        "address_city", "address_state", "address_zip",
        "phone", "website",
        "keywords_found",
        "filing_type", "filed_date",
    ]
    existing_cols = [c for c in priority_cols if c in df.columns]
    remaining_cols = [c for c in df.columns if c not in existing_cols]
    df = df[existing_cols + remaining_cols]

    # CSV
    csv_path = os.path.join(output_dir, OUTPUT_CSV)
    df.to_csv(csv_path, index=False)
    print(f"Saved CSV:   {csv_path}")

    # Excel — one sheet with all, plus per-ERP filtered sheets
    xlsx_path = os.path.join(output_dir, OUTPUT_XLSX)
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="All Companies")
        ws = writer.sheets["All Companies"]
        for col_idx, col in enumerate(df.columns, 1):
            max_len = max(len(str(col)), df[col].astype(str).str.len().max())
            ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = min(max_len + 2, 50)

        # Per-ERP sheets
        for erp in ["SAP", "Salesforce", "Oracle"]:
            erp_df = df[df["erp_vendors"].str.contains(erp, na=False)]
            if not erp_df.empty:
                sheet_name = f"{erp} Companies"
                erp_df.to_excel(writer, index=False, sheet_name=sheet_name)
                ws2 = writer.sheets[sheet_name]
                for col_idx, col in enumerate(erp_df.columns, 1):
                    max_len = max(len(str(col)), erp_df[col].astype(str).str.len().max())
                    ws2.column_dimensions[ws2.cell(row=1, column=col_idx).column_letter].width = min(max_len + 2, 50)

    print(f"Saved Excel: {xlsx_path}")

    # JSON
    json_path = os.path.join(output_dir, "erp_companies.json")
    with open(json_path, "w") as f:
        json.dump(companies, f, indent=2, default=str)
    print(f"Saved JSON:  {json_path}")

    return df


def print_summary(df: pd.DataFrame):
    """Print a summary of results."""
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print(f"Total unique companies: {len(df)}")

    if "ticker" in df.columns:
        with_ticker = df[df["ticker"].notna() & (df["ticker"] != "")]
        print(f"Companies with ticker:  {len(with_ticker)}")

    # ERP breakdown
    if "erp_vendors" in df.columns:
        print("\nBy ERP vendor:")
        for erp in ["SAP", "Salesforce", "Oracle"]:
            count = df["erp_vendors"].str.contains(erp, na=False).sum()
            if count:
                print(f"  {erp:12s}: {count}")
        multi = df["erp_vendors"].str.contains("|", regex=False, na=False).sum()
        if multi:
            print(f"  {'Multi-ERP':12s}: {multi}")

    if "sic_description" in df.columns:
        top_industries = df["sic_description"].value_counts().head(10)
        if not top_industries.empty:
            print("\nTop industries:")
            for industry, count in top_industries.items():
                if industry and str(industry) != "nan":
                    print(f"  {count:4d}  {industry}")

    if "address_state" in df.columns:
        top_states = df["address_state"].value_counts().head(5)
        if not top_states.empty:
            print("\nTop states:")
            for state, count in top_states.items():
                if state and str(state) != "nan":
                    print(f"  {count:4d}  {state}")

    print("\nTop 25 companies by filing mentions:")
    display_cols = ["company_name", "ticker", "erp_vendors", "filing_count", "sic_description"]
    display_cols = [c for c in display_cols if c in df.columns]
    print(df[display_cols].head(25).to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description="Scrape SEC EDGAR for companies using ERP systems")
    parser.add_argument("--from", dest="date_from", default="2023-01-01",
                        help="Start date (YYYY-MM-DD, default: 2023-01-01)")
    parser.add_argument("--to", dest="date_to", default=None,
                        help="End date (YYYY-MM-DD, default: today)")
    parser.add_argument("--erp", nargs="+", default=None,
                        help="ERP vendors to search (e.g. SAP Oracle Salesforce). Default: all")
    parser.add_argument("--max-pages", type=int, default=10,
                        help="Max pages per keyword (100 results/page)")
    parser.add_argument("--skip-enrich", action="store_true",
                        help="Skip enrichment (faster, less data)")
    parser.add_argument("--enrich-limit", type=int, default=300,
                        help="Max companies to enrich")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: ./output)")
    args = parser.parse_args()

    output_dir = args.output_dir or os.path.join(os.path.dirname(__file__), OUTPUT_DIR)

    print("=" * 60)
    print("SEC EDGAR ERP Company Scraper")
    print("=" * 60)

    # Step 1: Search
    companies = run_scraper(
        date_from=args.date_from,
        date_to=args.date_to,
        max_results_per_keyword=args.max_pages * 100,
        erp_filter=args.erp,
    )

    if not companies:
        print("\nNo companies found. Try adjusting date range or keywords.")
        sys.exit(0)

    # Step 2: Enrich
    if not args.skip_enrich:
        companies = enrich_companies(companies, max_enrich=args.enrich_limit)

    # Step 3: Save
    print(f"\nSaving results to {output_dir}/")
    df = save_results(companies, output_dir)

    # Step 4: Summary
    print_summary(df)

    print(f"\nDone! Files saved in: {output_dir}/")


if __name__ == "__main__":
    main()
