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

from gl_intelligence.config import cfg
from gl_intelligence.cortex.client import CortexClient
from gl_intelligence.agents.orchestrator import AgentOrchestrator

log = logging.getLogger("api.server")

app = Flask(__name__, static_folder=None)
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


@app.route("/")
def index():
    return send_from_directory(ROOT_DIR, "fasb_dise_platform.html")


@app.route("/dashboard")
def dashboard():
    return send_from_directory(ASSETS_DIR, "DISE_Dashboard.html")


@app.route("/<path:filename>")
def static_files(filename):
    # Try root first, then assets
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
