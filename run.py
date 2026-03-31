#!/usr/bin/env python3
"""
GL Intelligence Platform — Main Entry Point
============================================

Usage:
  python run.py status                     # Show platform status
  python run.py serve                      # Start API server + dashboard
  python run.py agent mapping              # Run GL mapping agent
  python run.py agent mapping --dry-run    # Dry run (no writes)
  python run.py agent recon                # Run reconciliation
  python run.py agent anomaly              # Run anomaly detection
  python run.py agent disclosure           # Generate DISE footnote
  python run.py agent all                  # Run full pipeline
  python run.py test                       # Accuracy test
  python run.py cortex sap                 # Show SAP data summary
  python run.py cortex oracle              # Show Oracle EBS data summary
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import os
import warnings

warnings.filterwarnings("ignore")

# Add parent to path so gl_intelligence is importable
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("gl-intelligence")


def cmd_status(args):
    """Show platform status."""
    from gl_intelligence.agents.orchestrator import AgentOrchestrator
    orch = AgentOrchestrator()
    status = orch.get_platform_status()

    print("\n" + "=" * 60)
    print("  GL INTELLIGENCE PLATFORM — STATUS")
    print("=" * 60)
    print(f"  Project:           {status['config']['project']}")
    print(f"  SAP CDC:           {status['config']['sap_cdc']}")
    print(f"  Oracle CDC:        {status['config']['oracle_cdc']}")
    print(f"  SFDC CDC:          {status['config']['sfdc_cdc']}")
    print(f"  Company:           {status['config']['company_code']}")
    print(f"  Fiscal Year:       {status['config']['fiscal_year']}")
    print(f"  Approved Mappings: {status['approved_mappings']}")
    print(f"  Pending Mappings:  {status['pending_mappings']}")

    print("\n  DISE Pivot:")
    for row in status["dise_pivot"]:
        print(f"    {row.get('expense_caption', ''):8} | {str(row.get('dise_category', '')):35} | ${row.get('amount', 0):>12,}")

    print("\n  Close Tracker:")
    for task in status["close_tracker"]:
        icon = "DONE" if task.get("is_complete") else "OPEN"
        print(f"    [{icon}] {task.get('task_id', '')} — {str(task.get('task_name', ''))[:50]}")

    alerts = status["anomaly_alerts"]
    print(f"\n  Open Anomaly Alerts: {len(alerts)}")
    print("=" * 60)


def cmd_serve(args):
    """Start the API server."""
    from gl_intelligence.api.server import app
    from gl_intelligence.config import cfg

    port = args.port or cfg.PORT
    log.info(f"Starting GL Intelligence Platform on port {port}")
    log.info(f"Dashboard: http://localhost:{port}/")
    log.info(f"API:       http://localhost:{port}/api/status")
    app.run(host="0.0.0.0", port=port, debug=args.debug)


def cmd_agent(args):
    """Run an agent."""
    from gl_intelligence.agents.orchestrator import AgentOrchestrator
    orch = AgentOrchestrator()

    if args.agent_name == "all":
        results = orch.run_all(dry_run=args.dry_run)
        for name, result in results.items():
            print(f"\n{name}: {json.dumps(result.to_dict(), indent=2, default=str)}")
    else:
        params = {"dry_run": args.dry_run} if args.agent_name == "mapping" else {}
        if args.batch:
            params["batch_size"] = args.batch
        result = orch.run_agent(args.agent_name, **params)
        print(json.dumps(result.to_dict(), indent=2, default=str))

        # Print detailed results for disclosure
        if args.agent_name == "disclosure" and result.results:
            narrative = result.results[0].get("narrative", "")
            if narrative:
                print("\n" + "=" * 60)
                print("  DISE FOOTNOTE DISCLOSURE")
                print("=" * 60)
                print(narrative)


def cmd_test(args):
    """Run accuracy test."""
    from gl_intelligence.agents.mapping_agent import MappingAgent
    agent = MappingAgent()
    result = agent.run_accuracy_test(sample_size=args.sample or 20)
    print(json.dumps(result.to_dict(), indent=2, default=str))
    print(f"\nAccuracy: {result.summary.get('accuracy', 0) * 100:.1f}%")


def cmd_cortex(args):
    """Show Cortex data summary."""
    from gl_intelligence.cortex.client import CortexClient

    cx = CortexClient()

    if args.source == "sap":
        from gl_intelligence.cortex.sap import SAPConnector
        sap = SAPConnector(cx)
        print("\n=== SAP GL Accounts ===")
        accounts = sap.get_gl_accounts()
        print(f"Total P&L accounts: {len(accounts)}")
        for a in accounts[:15]:
            print(f"  {a['gl_account']} | {str(a['description'])[:40]:40} | ${a['posting_amount']:>12,.0f}")
        if len(accounts) > 15:
            print(f"  ... and {len(accounts) - 15} more")

        print("\n=== Company Codes ===")
        for cc in sap.get_company_codes():
            print(f"  {cc['company_code']} — {cc.get('company_name', '')}")

    elif args.source == "oracle":
        from gl_intelligence.cortex.oracle import OracleEBSConnector
        oracle = OracleEBSConnector(cx)
        print("\n=== Oracle EBS Chart of Accounts ===")
        coa = oracle.get_chart_of_accounts()
        print(f"Total accounts: {len(coa)}")
        for a in coa[:15]:
            print(f"  {a.get('account_code', '')} | Company: {a.get('company', '')} | Type: {a.get('ACCOUNT_TYPE', '')}")

    elif args.source == "sfdc":
        from gl_intelligence.cortex.salesforce import SalesforceConnector
        sfdc = SalesforceConnector(cx)
        print("\n=== Salesforce ===")
        tables = sfdc.get_available_tables()
        print(f"Available tables: {tables}")
        accounts = sfdc.get_accounts(limit=10)
        print(f"Accounts: {len(accounts)}")

    else:
        # Show all datasets
        print("\n=== Cortex Datasets ===")
        for ds in cx.bq.list_datasets():
            tables = cx.list_tables(ds.dataset_id)
            print(f"  {ds.dataset_id}: {len(tables)} tables")


def main():
    parser = argparse.ArgumentParser(
        description="GL Intelligence Platform — Agentic Financial Data Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", help="Command to run")

    # status
    sub.add_parser("status", help="Show platform status")

    # serve
    serve_p = sub.add_parser("serve", help="Start API server + dashboard")
    serve_p.add_argument("--port", type=int, default=None)
    serve_p.add_argument("--debug", action="store_true")

    # agent
    agent_p = sub.add_parser("agent", help="Run an agent")
    agent_p.add_argument("agent_name", choices=["mapping", "recon", "anomaly", "disclosure", "all"])
    agent_p.add_argument("--dry-run", action="store_true")
    agent_p.add_argument("--batch", type=int, default=None)

    # test
    test_p = sub.add_parser("test", help="Run accuracy test")
    test_p.add_argument("--sample", type=int, default=20)

    # cortex
    cortex_p = sub.add_parser("cortex", help="Explore Cortex data")
    cortex_p.add_argument("source", nargs="?", default="all", choices=["sap", "oracle", "sfdc", "all"])

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "status": cmd_status,
        "serve": cmd_serve,
        "agent": cmd_agent,
        "test": cmd_test,
        "cortex": cmd_cortex,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
