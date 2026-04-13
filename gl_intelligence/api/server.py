"""
Flask API Server — unified HTTP interface for the GL Intelligence Platform.
Serves both the agent API and the static dashboard.
"""

from __future__ import annotations

import json
import logging
import os

from flask import Flask, jsonify, request, send_from_directory
from flask.wrappers import Response
from flask_cors import CORS

from gl_intelligence.config import cfg
from gl_intelligence.cortex.client import CortexClient
from gl_intelligence.agents.orchestrator import AgentOrchestrator

log = logging.getLogger("api.server")

app = Flask(__name__, static_folder=None)
CORS(app)
_orchestrator: AgentOrchestrator | None = None


def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


# ── Health & Status ─────────────────────────────────────────

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "project": cfg.PROJECT, "version": "0.2.0"})


@app.route("/api/status")
def platform_status():
    try:
        orch = get_orchestrator()
        status = orch.get_platform_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Cortex Data ─────────────────────────────────────────────

@app.route("/api/cortex/sap/gl-accounts")
def sap_gl_accounts():
    from gl_intelligence.cortex.sap import SAPConnector
    sap = SAPConnector(get_orchestrator().cx)
    fy = request.args.get("fiscal_year", cfg.FISCAL_YEAR)
    cc = request.args.get("company_code", cfg.COMPANY_CODE)
    accounts = sap.get_gl_accounts(cc, fy)
    return jsonify({"count": len(accounts), "accounts": accounts})


@app.route("/api/cortex/sap/trial-balance")
def sap_trial_balance():
    from gl_intelligence.cortex.sap import SAPConnector
    sap = SAPConnector(get_orchestrator().cx)
    tb = sap.get_trial_balance()
    return jsonify({"count": len(tb), "data": tb})


@app.route("/api/cortex/sap/journal-entries/<gl_account>")
def sap_journal_entries(gl_account):
    from gl_intelligence.cortex.sap import SAPConnector
    sap = SAPConnector(get_orchestrator().cx)
    entries = sap.get_journal_entries(gl_account)
    return jsonify({"gl_account": gl_account, "count": len(entries), "entries": entries})


@app.route("/api/cortex/oracle/chart-of-accounts")
def oracle_coa():
    from gl_intelligence.cortex.oracle import OracleEBSConnector
    oracle = OracleEBSConnector(get_orchestrator().cx)
    coa = oracle.get_chart_of_accounts()
    return jsonify({"count": len(coa), "data": coa})


@app.route("/api/cortex/sfdc/accounts")
def sfdc_accounts():
    from gl_intelligence.cortex.salesforce import SalesforceConnector
    sfdc = SalesforceConnector(get_orchestrator().cx)
    accounts = sfdc.get_accounts()
    return jsonify({"count": len(accounts), "data": accounts})


# ── DISE Data ───────────────────────────────────────────────

@app.route("/api/dise/mappings")
def dise_mappings():
    orch = get_orchestrator()
    mappings = orch.agents["mapping"].get_approved_mappings()
    return jsonify({"count": len(mappings), "mappings": mappings})


@app.route("/api/dise/pending")
def dise_pending():
    orch = get_orchestrator()
    pending = orch.agents["mapping"].get_pending_mappings()
    return jsonify({"count": len(pending), "pending": pending})


@app.route("/api/dise/pivot")
def dise_pivot():
    orch = get_orchestrator()
    fy = request.args.get("fiscal_year", cfg.FISCAL_YEAR)
    pivot = orch.agents["mapping"].get_dise_pivot(fy)
    return jsonify({"fiscal_year": fy, "data": pivot})


@app.route("/api/dise/close-tracker")
def close_tracker():
    orch = get_orchestrator()
    tasks = orch.agents["mapping"].get_close_tracker()
    return jsonify({"tasks": tasks})


@app.route("/api/dise/anomalies")
def anomalies():
    orch = get_orchestrator()
    status = request.args.get("status", "open")
    alerts = orch.agents["mapping"].get_anomaly_alerts(status)
    return jsonify({"count": len(alerts), "alerts": alerts})


# ── Agent Execution ─────────────────────────────────────────

@app.route("/api/agents/run", methods=["POST"])
def run_agent():
    """Run a specific agent. Body: {"agent": "mapping", "params": {...}}"""
    body = request.get_json(silent=True) or {}
    agent_name = body.get("agent", "mapping")
    params = body.get("params", {})

    orch = get_orchestrator()
    try:
        result = orch.run_agent(agent_name, **params)
        return jsonify(result.to_dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents/run-all", methods=["POST"])
def run_all_agents():
    """Run the full agent pipeline."""
    body = request.get_json(silent=True) or {}
    dry_run = body.get("dry_run", True)

    orch = get_orchestrator()
    try:
        results = orch.run_all(dry_run=dry_run)
        return jsonify({name: r.to_dict() for name, r in results.items()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents/disclosure", methods=["POST"])
def generate_disclosure():
    """Generate DISE footnote disclosure."""
    body = request.get_json(silent=True) or {}
    fy = body.get("fiscal_year", cfg.FISCAL_YEAR)

    orch = get_orchestrator()
    try:
        result = orch.run_agent("disclosure", fiscal_year=fy)
        return jsonify({
            "status": result.status,
            "summary": result.summary,
            "disclosure": result.results[0] if result.results else None,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Tax Data (ASC 740) ─────────────────────────────────────

@app.route("/api/tax/provision")
def tax_provision():
    """Returns the full tax provision dataset."""
    from gl_intelligence.agents.tax_agent import load_tax_data
    data = load_tax_data()
    return jsonify(data)


@app.route("/api/tax/rate-reconciliation")
def tax_rate_reconciliation():
    """Returns rate reconciliation line items."""
    from gl_intelligence.agents.tax_agent import load_tax_data
    data = load_tax_data()
    return jsonify({
        "statutory_rate": data.get("statutory_rate"),
        "effective_rate": data.get("effective_rate"),
        "items": data.get("rate_reconciliation", []),
    })


@app.route("/api/tax/jurisdictions")
def tax_jurisdictions():
    """Returns jurisdictional disaggregation per ASU 2023-09."""
    from gl_intelligence.agents.tax_agent import load_tax_data
    data = load_tax_data()
    return jsonify({
        "pretax_income": data.get("pretax_income"),
        "jurisdictions": data.get("jurisdictions", []),
        "cash_taxes_paid": data.get("cash_taxes_paid"),
    })


@app.route("/api/tax/expense-components")
def tax_expense_components():
    """Returns income tax expense components — current/deferred by jurisdiction (ASC 740-10-50-9/10)."""
    from gl_intelligence.agents.tax_agent import load_tax_data
    data = load_tax_data()
    return jsonify({
        "current_year": data.get("income_tax_expense_components", {}),
        "prior_year": data.get("prior_income_tax_expense_components", {}),
    })


@app.route("/api/tax/carryforwards")
def tax_carryforwards():
    """Returns NOL and credit carryforward schedules (ASC 740-10-50-3)."""
    from gl_intelligence.agents.tax_agent import load_tax_data
    data = load_tax_data()
    return jsonify({
        "carryforwards": data.get("carryforwards", []),
        "unremitted_foreign_earnings": data.get("unremitted_foreign_earnings", {}),
    })


# ── Tax GL Classifier (ASC 740 / ASU 2023-09) ─────────────

@app.route("/api/tax/classifier/accounts")
def tax_classifier_accounts():
    """Returns the SAP GL accounts in the tax account range (160000-199999)."""
    from gl_intelligence.agents.tax_classifier_agent import TaxClassifierAgent
    agent = TaxClassifierAgent(get_orchestrator().cx)
    accounts = agent.get_all_accounts()
    return jsonify({"count": len(accounts), "accounts": accounts})


@app.route("/api/tax/classifier/run", methods=["POST"])
def tax_classifier_run():
    """Run the Tax Classifier Agent — Claude classifies SAP GL tax accounts into ASC 740 categories."""
    from gl_intelligence.agents.tax_classifier_agent import TaxClassifierAgent
    body = request.get_json(silent=True) or {}
    batch_size = body.get("batch_size", 18)
    dry_run = body.get("dry_run", False)
    source = body.get("source", "auto")

    agent = TaxClassifierAgent(get_orchestrator().cx)
    try:
        result = agent.run(batch_size=batch_size, dry_run=dry_run, source=source)
        return jsonify({
            "status": result.status,
            "summary": result.summary,
            "results": result.results,
            "elapsed_seconds": result.elapsed_seconds,
        })
    except Exception as e:
        log.exception("Tax classifier error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/tax/classifier/pending")
def tax_classifier_pending():
    """Returns pending tax GL mappings awaiting controller review."""
    from gl_intelligence.agents.tax_classifier_agent import TaxClassifierAgent
    agent = TaxClassifierAgent(get_orchestrator().cx)
    pending = agent.get_pending_tax_mappings()
    return jsonify({"count": len(pending), "pending": pending})


@app.route("/api/tax/classifier/approved")
def tax_classifier_approved():
    """Returns all approved tax GL mappings."""
    from gl_intelligence.agents.tax_classifier_agent import TaxClassifierAgent
    agent = TaxClassifierAgent(get_orchestrator().cx)
    approved = agent.get_approved_tax_mappings()
    return jsonify({"count": len(approved), "approved": approved})


@app.route("/api/tax/classifier/approve", methods=["POST"])
def tax_classifier_approve():
    """Approve a pending tax GL mapping.
    Body: {"gl_account": "...", "reviewer": "...", "override_category": "..." (optional)}
    """
    from gl_intelligence.agents.tax_classifier_agent import TaxClassifierAgent
    body = request.get_json(silent=True) or {}
    gl_account = body.get("gl_account")
    reviewer = body.get("reviewer", "controller")
    override = body.get("override_category")

    if not gl_account:
        return jsonify({"error": "gl_account required"}), 400

    agent = TaxClassifierAgent(get_orchestrator().cx)
    ok = agent.approve_mapping(gl_account, reviewer=reviewer, override_category=override)
    return jsonify({"success": ok, "gl_account": gl_account, "action": "approved"})


@app.route("/api/tax/classifier/reject", methods=["POST"])
def tax_classifier_reject():
    """Reject a pending tax GL mapping.
    Body: {"gl_account": "...", "reviewer": "...", "reason": "..."}
    """
    from gl_intelligence.agents.tax_classifier_agent import TaxClassifierAgent
    body = request.get_json(silent=True) or {}
    gl_account = body.get("gl_account")
    reviewer = body.get("reviewer", "controller")
    reason = body.get("reason", "")

    if not gl_account:
        return jsonify({"error": "gl_account required"}), 400

    agent = TaxClassifierAgent(get_orchestrator().cx)
    ok = agent.reject_mapping(gl_account, reviewer=reviewer, reason=reason)
    return jsonify({"success": ok, "gl_account": gl_account, "action": "rejected"})


@app.route("/api/tax/etr-bridge/run", methods=["POST"])
def etr_bridge_run():
    """Run the ETR Bridge Agent — produces Tables A, B, C from approved tax mappings."""
    from gl_intelligence.agents.etr_bridge_agent import ETRBridgeAgent
    body = request.get_json(silent=True) or {}
    fy = body.get("fiscal_year", cfg.FISCAL_YEAR)

    agent = ETRBridgeAgent(get_orchestrator().cx)
    try:
        result = agent.run(fiscal_year=fy)
        return jsonify({
            "status": result.status,
            "summary": result.summary,
            "output": result.results[0] if result.results else None,
            "elapsed_seconds": result.elapsed_seconds,
        })
    except Exception as e:
        log.exception("ETR bridge error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/tax/etr-bridge/output")
def etr_bridge_output():
    """Returns the latest ETR bridge output (Tables A, B, C) — runs bridge if not yet computed."""
    from gl_intelligence.agents.etr_bridge_agent import ETRBridgeAgent
    fy = request.args.get("fiscal_year", cfg.FISCAL_YEAR)
    agent = ETRBridgeAgent(get_orchestrator().cx)
    try:
        result = agent.run(fiscal_year=fy)
        if result.results:
            return jsonify(result.results[0])
        return jsonify({"error": "No ETR output produced"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── AI Chat ─────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def chat():
    """Proxied Claude chat — keeps API key server-side."""
    import anthropic
    body = request.get_json(silent=True) or {}
    messages = body.get("messages", [])
    system = body.get("system", "You are a FASB financial disclosure compliance assistant.")

    if not messages:
        return jsonify({"error": "messages required"}), 400

    try:
        if cfg.use_bedrock():
            client = anthropic.AnthropicBedrock(
                aws_access_key=cfg.AWS_ACCESS_KEY_ID,
                aws_secret_key=cfg.AWS_SECRET_ACCESS_KEY,
                aws_region=cfg.AWS_BEDROCK_REGION,
            )
        else:
            client = anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=cfg.CLAUDE_MODEL,
            max_tokens=1200,
            system=system,
            messages=messages,
            timeout=30.0,
        )
        reply = response.content[0].text
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Classified data for frontend ────────────────────────────

@app.route("/api/classified/accounts")
def classified_accounts():
    """Returns all 501 classified accounts from offline pipeline."""
    from gl_intelligence.agents.base import load_offline_data
    data = load_offline_data()
    return jsonify({"count": len(data), "accounts": data})


# ── Static files (dashboard) ───────────────────────────────

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "FASB DISE ASSETS")
ROOT_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
LANDING_DIR = os.path.join(ROOT_DIR, "landing")


@app.route("/")
def index():
    return send_from_directory(LANDING_DIR, "index.html")


@app.route("/app")
def app_dashboard():
    return send_from_directory(ROOT_DIR, "GL_Intelligence_Platform_6.html")


@app.route("/dashboard")
def dashboard():
    return send_from_directory(ASSETS_DIR, "DISE_Dashboard.html")


@app.route("/<path:filename>")
def static_files(filename):
    # Landing page static assets (_next/*, favicon, images)
    landing_path = os.path.join(LANDING_DIR, filename)
    if os.path.isfile(landing_path):
        return send_from_directory(LANDING_DIR, filename)
    # Fallback: root dir, then FASB assets dir
    root_path = os.path.join(ROOT_DIR, filename)
    if os.path.isfile(root_path):
        return send_from_directory(ROOT_DIR, filename)
    return send_from_directory(ASSETS_DIR, filename)


@app.errorhandler(Exception)
def handle_exception(e):
    """Return JSON for all unhandled errors instead of HTML."""
    log.exception("Unhandled error")
    return jsonify({"error": str(e)}), 500


def create_app() -> Flask:
    """Factory function for gunicorn."""
    return app
