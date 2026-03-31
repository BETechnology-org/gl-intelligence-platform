"""
SEC EDGAR Scraper — finds public companies mentioning ERP systems
(SAP, Salesforce, Oracle) in their filings.

Uses the EDGAR full-text search API (EFTS):
  https://efts.sec.gov/LATEST/search-index?q=...
"""

import re
import time
from datetime import datetime

import requests

from config import (
    ERP_KEYWORDS,
    FILING_TYPES,
    RATE_LIMIT_CALLS,
    RATE_LIMIT_PERIOD,
    USER_AGENT,
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
}

_request_times: list = []


def _rate_limited_get(url: str, params: dict = None) -> requests.Response:
    """GET with SEC rate limiting (max 10 req/s, we use 8 to be safe)."""
    now = time.time()
    while _request_times and _request_times[0] < now - RATE_LIMIT_PERIOD:
        _request_times.pop(0)
    if len(_request_times) >= RATE_LIMIT_CALLS:
        sleep_time = RATE_LIMIT_PERIOD - (now - _request_times[0]) + 0.05
        if sleep_time > 0:
            time.sleep(sleep_time)
    _request_times.append(time.time())
    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp


def _parse_ticker_from_display(display_name: str) -> str:
    match = re.search(r'\(([A-Z]{1,5})\)', display_name)
    return match.group(1) if match else ""


def _parse_company_name(display_name: str) -> str:
    match = re.match(r'^(.+?)\s*\(', display_name)
    return match.group(1).strip() if match else display_name.strip()


def search_edgar(query: str, forms: str, date_from: str, date_to: str,
                 max_results: int = 1000) -> list:
    """Search EDGAR full-text search index. Returns list of hit dicts."""
    all_hits = []
    start = 0
    page_size = 100

    while start < max_results:
        params = {
            "q": query,
            "forms": forms,
            "startdt": date_from,
            "enddt": date_to,
            "start": start,
        }

        try:
            resp = _rate_limited_get("https://efts.sec.gov/LATEST/search-index", params)
            data = resp.json()
        except Exception as e:
            print(f"  [!] API error at start={start}: {e}")
            break

        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            break

        all_hits.extend(hits)

        total = data["hits"]["total"]["value"]
        start += page_size
        if start >= total:
            break

    return all_hits


def extract_company(hit: dict) -> dict:
    """Extract structured company info from an EFTS hit."""
    src = hit.get("_source", {})

    display_names = src.get("display_names", [])
    display = display_names[0] if display_names else ""

    ciks = src.get("ciks", [])
    cik = ciks[0].lstrip("0") if ciks else ""

    return {
        "cik": cik,
        "company_name": _parse_company_name(display),
        "ticker": _parse_ticker_from_display(display),
        "filing_type": src.get("form", src.get("file_type", "")),
        "filed_date": src.get("file_date", ""),
        "sic": (src.get("sics", [None]) or [None])[0] or "",
        "biz_location": (src.get("biz_locations", [""]) or [""])[0],
        "biz_state": (src.get("biz_states", [""]) or [""])[0],
        "inc_state": (src.get("inc_states", [""]) or [""])[0],
    }


def run_scraper(date_from: str = "2023-01-01", date_to: str = None,
                max_results_per_keyword: int = 1000,
                erp_filter: list = None) -> list:
    """
    Main scraper: searches SEC EDGAR for ERP-related keywords across
    all configured ERP vendors (SAP, Salesforce, Oracle).
    Returns deduplicated list of companies with ERP vendor tags.

    erp_filter: optional list of ERP names to search, e.g. ["SAP", "Oracle"].
                If None, searches all configured ERPs.
    """
    if date_to is None:
        date_to = datetime.now().strftime("%Y-%m-%d")

    companies_by_cik = {}
    forms_filter = ",".join(FILING_TYPES)

    # Determine which ERPs to search
    erps_to_search = {}
    for erp_name, keywords in ERP_KEYWORDS.items():
        if erp_filter is None or erp_name in erp_filter:
            erps_to_search[erp_name] = keywords

    total_keywords = sum(len(kw) for kw in erps_to_search.values())
    print(f"Searching SEC EDGAR for ERP mentions in {', '.join(FILING_TYPES)} filings")
    print(f"ERP vendors: {', '.join(erps_to_search.keys())}")
    print(f"Date range: {date_from} to {date_to}")
    print(f"Total keywords: {total_keywords}")
    print("=" * 60)

    keyword_num = 0
    for erp_name, keywords in erps_to_search.items():
        print(f"\n--- {erp_name} ({len(keywords)} keywords) ---")

        for keyword in keywords:
            keyword_num += 1
            print(f"[{keyword_num}/{total_keywords}] Searching: {keyword} ...")

            hits = search_edgar(
                query=keyword,
                forms=forms_filter,
                date_from=date_from,
                date_to=date_to,
                max_results=max_results_per_keyword,
            )

            new_count = 0
            for hit in hits:
                company = extract_company(hit)
                cik = company["cik"]
                if not cik:
                    continue

                if cik not in companies_by_cik:
                    companies_by_cik[cik] = {
                        **company,
                        "erp_vendors": [erp_name],
                        "keywords_found": [keyword],
                        "filing_count": 1,
                    }
                    new_count += 1
                else:
                    existing = companies_by_cik[cik]
                    if erp_name not in existing["erp_vendors"]:
                        existing["erp_vendors"].append(erp_name)
                    if keyword not in existing["keywords_found"]:
                        existing["keywords_found"].append(keyword)
                    existing["filing_count"] += 1
                    if company["filed_date"] > existing.get("filed_date", ""):
                        existing["filed_date"] = company["filed_date"]

            print(f"  -> {len(hits)} filings, {new_count} new companies (total unique: {len(companies_by_cik)})")

    results = sorted(companies_by_cik.values(), key=lambda x: x["filing_count"], reverse=True)

    print("\n" + "=" * 60)
    print(f"Total unique companies found: {len(results)}")

    # Quick ERP breakdown
    erp_counts = {}
    for c in results:
        for erp in c["erp_vendors"]:
            erp_counts[erp] = erp_counts.get(erp, 0) + 1
    for erp, count in sorted(erp_counts.items()):
        print(f"  {erp}: {count} companies")
    multi = sum(1 for c in results if len(c["erp_vendors"]) > 1)
    if multi:
        print(f"  Multi-ERP (2+): {multi} companies")

    return results


def enrich_companies(companies: list, max_enrich: int = 300) -> list:
    """
    Enrich company records with SIC description, address,
    phone, website from the EDGAR submissions API.
    """
    to_enrich = min(max_enrich, len(companies))
    print(f"\nEnriching top {to_enrich} companies with EDGAR data...")

    for i, company in enumerate(companies[:to_enrich]):
        cik = company.get("cik", "")
        if not cik:
            continue

        cik_padded = cik.zfill(10)
        url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"

        try:
            resp = _rate_limited_get(url)
            info = resp.json()
        except Exception:
            continue

        company["sic_description"] = info.get("sicDescription", "")
        tickers = info.get("tickers", [])
        if tickers and not company.get("ticker"):
            company["ticker"] = tickers[0]
        company["all_tickers"] = ",".join(t for t in tickers if t)
        company["exchanges"] = ",".join(e for e in info.get("exchanges", []) if e)
        company["phone"] = info.get("phone", "")
        company["website"] = info.get("website", "")
        company["fiscal_year_end"] = info.get("fiscalYearEnd", "")
        company["category"] = info.get("category", "")

        biz_addr = info.get("addresses", {}).get("business", {})
        company["address_street"] = biz_addr.get("street1", "")
        company["address_city"] = biz_addr.get("city", "")
        company["address_state"] = biz_addr.get("stateOrCountry", "")
        company["address_zip"] = biz_addr.get("zipCode", "")

        if (i + 1) % 50 == 0:
            print(f"  Enriched {i + 1}/{to_enrich}...")

    print("  Enrichment complete.")
    return companies
