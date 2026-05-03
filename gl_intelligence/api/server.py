"""
Flask API Server — unified HTTP interface for the GL Intelligence Platform.
Serves both the agent API and the static dashboard.

Hardening:
- Origin-scoped CORS (CORS_ALLOWED_ORIGINS env, comma-separated)
- Security headers on every response (CSP, HSTS in prod, X-Frame-Options, ...)
- In-process per-IP rate limiting (RATE_LIMIT_PER_MINUTE env)
- Request-ID correlation for logs + responses
- Structured error handler that doesn't leak internals in prod
"""

from __future__ import annotations

import logging
import os
import secrets
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Deque

from flask import Flask, g, jsonify, request, send_from_directory
from flask.wrappers import Response
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from gl_intelligence.config import cfg
from gl_intelligence.agents.orchestrator import AgentOrchestrator


# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("api.server")


# ── Environment knobs ────────────────────────────────────────
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").lower()
IS_PROD = ENVIRONMENT in ("production", "prod")

_default_origins = (
    "https://truffles.ai,https://www.truffles.ai"
    if IS_PROD
    else "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8080"
)
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", _default_origins).split(",")
    if o.strip()
]

RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))
MAX_JSON_BYTES = int(os.environ.get("MAX_JSON_BYTES", str(1 * 1024 * 1024)))  # 1 MiB
APP_VERSION = os.environ.get("APP_VERSION", "0.2.0")


# ── Flask app ────────────────────────────────────────────────
app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_JSON_BYTES

# Only allow cross-origin from configured origins (no wildcard in prod).
CORS(
    app,
    resources={r"/api/*": {"origins": CORS_ALLOWED_ORIGINS}},
    supports_credentials=False,
    max_age=600,
)

_orchestrator: AgentOrchestrator | None = None
_orchestrator_lock = threading.Lock()


def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        with _orchestrator_lock:
            if _orchestrator is None:
                _orchestrator = AgentOrchestrator()
    return _orchestrator


# ── Rate limiter (per-IP, sliding window, in-process) ────────
_rate_buckets: dict[str, Deque[float]] = {}
_rate_lock = threading.Lock()
_RATE_EXEMPT_PATHS = {"/api/health"}


def _client_ip() -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _check_rate_limit() -> Response | None:
    if RATE_LIMIT_PER_MINUTE <= 0:
        return None
    if not request.path.startswith("/api/") or request.path in _RATE_EXEMPT_PATHS:
        return None

    key = _client_ip()
    now = time.monotonic()
    window_start = now - 60.0

    with _rate_lock:
        bucket = _rate_buckets.setdefault(key, deque())
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_PER_MINUTE:
            retry_after = max(1, int(60 - (now - bucket[0])))
            resp = jsonify({
                "error": "rate_limited",
                "message": "Too many requests. Please retry shortly.",
                "retry_after_seconds": retry_after,
            })
            resp.status_code = 429
            resp.headers["Retry-After"] = str(retry_after)
            return resp
        bucket.append(now)
    return None


# ── Request lifecycle hooks ──────────────────────────────────
@app.before_request
def _before_request() -> Response | None:
    g.request_id = request.headers.get("X-Request-ID") or secrets.token_hex(8)
    g.started_at = time.monotonic()
    limited = _check_rate_limit()
    if limited is not None:
        log.info("rate_limited ip=%s path=%s rid=%s", _client_ip(), request.path, g.request_id)
        return limited
    return None


def _apply_security_headers(resp: Response) -> Response:
    # Clickjacking / MIME / referrer
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), interest-cohort=()",
    )
    resp.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    resp.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")

    # HSTS only over HTTPS / in production
    if IS_PROD:
        resp.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=63072000; includeSubDomains; preload",
        )

    # Locked-down CSP for JSON API responses. HTML responses opt in separately below.
    ct = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if ct == "application/json":
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
    elif ct == "text/html":
        # Permissive CSP for dashboard HTML (inline scripts/styles present)
        # `connect-src data:` is required for GLTFLoader — the hero model
        # inlines geometry buffers as base64 data URIs and fetches them.
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "img-src 'self' data: blob: https:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "connect-src 'self' data: blob: https:; "
            "worker-src 'self' blob:; "
            "frame-ancestors 'none'; base-uri 'self'",
        )
    return resp


@app.after_request
def _after_request(resp: Response) -> Response:
    resp.headers["X-Request-ID"] = getattr(g, "request_id", "-")
    _apply_security_headers(resp)
    try:
        elapsed_ms = int((time.monotonic() - g.started_at) * 1000)
    except Exception:
        elapsed_ms = -1
    log.info(
        "req rid=%s ip=%s %s %s -> %d in %dms",
        getattr(g, "request_id", "-"),
        _client_ip(),
        request.method,
        request.path,
        resp.status_code,
        elapsed_ms,
    )
    return resp


# ── Error handlers ───────────────────────────────────────────
def _error_response(status: int, code: str, message: str) -> tuple[Response, int]:
    return (
        jsonify({
            "error": code,
            "message": message,
            "request_id": getattr(g, "request_id", None),
        }),
        status,
    )


@app.errorhandler(HTTPException)
def _handle_http_exc(e: HTTPException):
    return _error_response(e.code or 500, e.name.lower().replace(" ", "_"), e.description or e.name)


@app.errorhandler(Exception)
def handle_exception(e: Exception):
    log.exception("unhandled rid=%s path=%s", getattr(g, "request_id", "-"), request.path)
    # Don't leak raw exception details in production.
    message = "Internal server error" if IS_PROD else f"{type(e).__name__}: {e}"
    return _error_response(500, "internal_error", message)


def _safe_run(fn, *args, **kwargs):
    """Run an agent call and convert exceptions into structured 500s."""
    try:
        return fn(*args, **kwargs), None
    except Exception as e:
        log.exception("agent error rid=%s", getattr(g, "request_id", "-"))
        return None, _error_response(
            500,
            "agent_error",
            "Agent execution failed" if IS_PROD else f"{type(e).__name__}: {e}",
        )


# ── Health & Status ─────────────────────────────────────────

@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "project": cfg.PROJECT,
        "version": APP_VERSION,
        "environment": ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/api/status")
def platform_status():
    result, err = _safe_run(lambda: get_orchestrator().get_platform_status())
    return err if err else jsonify(result)


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
    """DISE pivot. Reads live from Supabase dise_approved_mappings when
    available; falls back to legacy BigQuery / offline JSON path."""
    fy = request.args.get("fiscal_year", cfg.FISCAL_YEAR)
    from gl_intelligence.persistence import supabase_available
    if supabase_available():
        from gl_intelligence.persistence.aggregates import dise_pivot as sb_pivot
        pivot = sb_pivot(fiscal_year=fy)
        if pivot:
            return jsonify({"fiscal_year": fy, "data": pivot, "source": "supabase"})
    orch = get_orchestrator()
    pivot = orch.agents["mapping"].get_dise_pivot(fy)
    return jsonify({"fiscal_year": fy, "data": pivot, "source": "legacy"})


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
    if not isinstance(agent_name, str) or not isinstance(params, dict):
        return _error_response(400, "bad_request", "`agent` must be string and `params` must be object")

    result, err = _safe_run(lambda: get_orchestrator().run_agent(agent_name, **params))
    return err if err else jsonify(result.to_dict())


@app.route("/api/agents/run-all", methods=["POST"])
def run_all_agents():
    """Run the full agent pipeline."""
    body = request.get_json(silent=True) or {}
    dry_run = bool(body.get("dry_run", True))

    result, err = _safe_run(lambda: get_orchestrator().run_all(dry_run=dry_run))
    if err:
        return err
    return jsonify({name: r.to_dict() for name, r in result.items()})


@app.route("/api/agents/disclosure", methods=["POST"])
def generate_disclosure():
    """Generate DISE footnote disclosure."""
    body = request.get_json(silent=True) or {}
    fy = body.get("fiscal_year", cfg.FISCAL_YEAR)

    result, err = _safe_run(lambda: get_orchestrator().run_agent("disclosure", fiscal_year=fy))
    if err:
        return err
    return jsonify({
        "status": result.status,
        "summary": result.summary,
        "disclosure": result.results[0] if result.results else None,
    })


# ── Tax Data (ASC 740) ─────────────────────────────────────

@app.route("/api/tax/provision")
def tax_provision():
    """Returns the full tax provision dataset.

    Resolution order:
      1. Supabase tax_approved_mappings — live computation from
         approved mappings (the new DEMO/FY2024 dataset).
      2. Legacy curated `tax_provision_data.json` — fallback.
    """
    from gl_intelligence.persistence import supabase_available
    from gl_intelligence.agents.tax_agent import load_tax_data
    fy = request.args.get("fiscal_year", cfg.FISCAL_YEAR)
    if supabase_available():
        from gl_intelligence.persistence.aggregates import tax_provision as sb_provision
        live = sb_provision(fiscal_year=fy)
        if live:
            base = dict(load_tax_data() or {})
            base.update(live)
            return jsonify(base)
    return jsonify(load_tax_data())


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
    try:
        batch_size = int(body.get("batch_size", 18))
    except (TypeError, ValueError):
        return _error_response(400, "bad_request", "batch_size must be an integer")
    dry_run = bool(body.get("dry_run", False))
    source = body.get("source", "auto")
    if not isinstance(source, str):
        return _error_response(400, "bad_request", "source must be a string")
    batch_size = max(1, min(batch_size, 100))

    agent = TaxClassifierAgent(get_orchestrator().cx)
    result, err = _safe_run(lambda: agent.run(batch_size=batch_size, dry_run=dry_run, source=source))
    if err:
        return err
    return jsonify({
        "status": result.status,
        "summary": result.summary,
        "results": result.results,
        "elapsed_seconds": result.elapsed_seconds,
    })


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

    if not isinstance(gl_account, str) or not gl_account.strip():
        return _error_response(400, "bad_request", "gl_account required")

    agent = TaxClassifierAgent(get_orchestrator().cx)
    ok, err = _safe_run(lambda: agent.approve_mapping(gl_account, reviewer=reviewer, override_category=override))
    if err:
        return err
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

    if not isinstance(gl_account, str) or not gl_account.strip():
        return _error_response(400, "bad_request", "gl_account required")

    agent = TaxClassifierAgent(get_orchestrator().cx)
    ok, err = _safe_run(lambda: agent.reject_mapping(gl_account, reviewer=reviewer, reason=reason))
    if err:
        return err
    return jsonify({"success": ok, "gl_account": gl_account, "action": "rejected"})


@app.route("/api/tax/etr-bridge/run", methods=["POST"])
def etr_bridge_run():
    """Run the ETR Bridge Agent — produces Tables A, B, C from approved tax mappings."""
    from gl_intelligence.agents.etr_bridge_agent import ETRBridgeAgent
    body = request.get_json(silent=True) or {}
    fy = body.get("fiscal_year", cfg.FISCAL_YEAR)

    agent = ETRBridgeAgent(get_orchestrator().cx)
    result, err = _safe_run(lambda: agent.run(fiscal_year=fy))
    if err:
        return err
    return jsonify({
        "status": result.status,
        "summary": result.summary,
        "output": result.results[0] if result.results else None,
        "elapsed_seconds": result.elapsed_seconds,
    })


@app.route("/api/tax/etr-bridge/output")
def etr_bridge_output():
    """Returns the latest ETR bridge output (Tables A, B, C) — runs bridge if not yet computed."""
    from gl_intelligence.agents.etr_bridge_agent import ETRBridgeAgent
    fy = request.args.get("fiscal_year", cfg.FISCAL_YEAR)
    agent = ETRBridgeAgent(get_orchestrator().cx)
    result, err = _safe_run(lambda: agent.run(fiscal_year=fy))
    if err:
        return err
    if result.results:
        return jsonify(result.results[0])
    return _error_response(500, "no_output", "No ETR output produced")


# ── AI Chat ─────────────────────────────────────────────────

_CHAT_MAX_MESSAGES = 40
_CHAT_MAX_CHARS = 24_000


@app.route("/api/chat", methods=["POST"])
def chat():
    """Proxied Claude chat — keeps API key server-side."""
    import anthropic
    body = request.get_json(silent=True) or {}
    messages = body.get("messages", [])
    system = body.get("system", "You are a FASB financial disclosure compliance assistant.")

    if not isinstance(messages, list) or not messages:
        return _error_response(400, "bad_request", "messages required (non-empty list)")
    if len(messages) > _CHAT_MAX_MESSAGES:
        return _error_response(400, "bad_request", f"too many messages (max {_CHAT_MAX_MESSAGES})")
    total_chars = 0
    for m in messages:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
            return _error_response(400, "bad_request", "each message needs role=user|assistant and content")
        content = m.get("content")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            total_chars += sum(len(str(p)) for p in content)
        else:
            return _error_response(400, "bad_request", "message content must be string or list")
    if total_chars > _CHAT_MAX_CHARS:
        return _error_response(413, "payload_too_large", f"messages exceed {_CHAT_MAX_CHARS} chars")
    if not isinstance(system, str):
        return _error_response(400, "bad_request", "system must be a string")

    try:
        if cfg.use_bedrock():
            client = anthropic.AnthropicBedrock(
                aws_access_key=cfg.AWS_ACCESS_KEY_ID,
                aws_secret_key=cfg.AWS_SECRET_ACCESS_KEY,
                aws_region=cfg.AWS_BEDROCK_REGION,
            )
        else:
            if not cfg.ANTHROPIC_API_KEY:
                return _error_response(503, "ai_unavailable", "AI provider not configured")
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
        log.exception("chat error rid=%s", getattr(g, "request_id", "-"))
        return _error_response(
            502,
            "upstream_error",
            "AI provider error" if IS_PROD else f"{type(e).__name__}: {e}",
        )


# ── Classified data for frontend ────────────────────────────

@app.route("/api/classified/accounts")
def classified_accounts():
    """Returns all 501 classified accounts from offline pipeline."""
    from gl_intelligence.agents.base import load_offline_data
    data = load_offline_data()
    return jsonify({"count": len(data), "accounts": data})


# ── Audit log + Workiva-ready exports (Supabase-backed) ────
#
# These routes are gated on the Supabase env vars being set. When
# they are, controller actions in the legacy /app HTML UI flow
# through the durable Supabase backing store (replacing the
# module-level Python lists in tax_classifier_agent that lost
# state on every Cloud Run restart). When they're not, the routes
# return empty/501 — the legacy in-memory fallback continues to
# work, just without persistence.

@app.route("/api/audit-log")
def audit_log():
    """Return the most recent audit_log rows for a company × module.

    Query params:
      company_id  (optional; defaults to demo company C006)
      module      (optional; 'tax' | 'dise' | 'platform')
      limit       (optional; default 200, capped at 500)
    """
    from gl_intelligence.persistence import supabase_available
    from gl_intelligence.persistence.tax_store import list_audit_events
    if not supabase_available():
        return jsonify({"events": [], "count": 0, "supabase": False}), 200
    module = request.args.get("module")
    company_id = request.args.get("company_id")
    try:
        limit = max(1, min(int(request.args.get("limit", "200")), 500))
    except (TypeError, ValueError):
        return _error_response(400, "bad_request", "limit must be an integer")
    kwargs: dict = {"limit": limit}
    if company_id:
        kwargs["company_id"] = company_id
    if module:
        kwargs["module"] = module
    events = list_audit_events(**kwargs)
    return jsonify({"events": events, "count": len(events), "supabase": True})


def _export_response(content: bytes | str, *, mime: str, filename: str) -> Response:
    if isinstance(content, str):
        content = content.encode("utf-8")
    resp = Response(content, mimetype=mime)
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@app.route("/api/exports/dise")
def export_dise():
    """CSV / JSON / DOCX export of approved DISE mappings (ASU 2024-03)."""
    from gl_intelligence.persistence import supabase_available
    from gl_intelligence.persistence.supabase_client import (
        DEFAULT_COMPANY_ID,
        get_supabase,
    )
    from gl_intelligence.exports import dise_export

    fy = request.args.get("fiscal_year", cfg.FISCAL_YEAR)
    fmt = (request.args.get("format", "csv") or "csv").lower()
    company_id = request.args.get("company_id", DEFAULT_COMPANY_ID)

    rows: list[dict] = []
    if supabase_available():
        sb = get_supabase()
        try:
            rows = (
                sb.table("dise_approved_mappings").select("*")
                .eq("company_id", company_id).eq("fiscal_year", fy)
                .order("gl_account").execute()
            ).data or []
        except Exception as e:
            log.warning("dise export supabase read failed: %s", e)

    base = f"dise_disclosure_FY{fy}"
    if fmt == "csv":
        return _export_response(dise_export.to_csv(rows),
                                mime="text/csv; charset=utf-8",
                                filename=f"{base}.csv")
    if fmt == "json":
        return _export_response(dise_export.to_json(rows, fy),
                                mime="application/json",
                                filename=f"{base}.json")
    if fmt == "docx":
        return _export_response(
            dise_export.to_docx(rows, fy),
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=f"{base}.docx",
        )
    return _error_response(400, "bad_request", "format must be csv | json | docx")


@app.route("/api/exports/tax")
def export_tax():
    """CSV / JSON / DOCX export of approved tax mappings (ASU 2023-09)."""
    from gl_intelligence.persistence import supabase_available
    from gl_intelligence.persistence.supabase_client import (
        DEFAULT_COMPANY_ID,
        get_supabase,
    )
    from gl_intelligence.exports import tax_export

    fy = request.args.get("fiscal_year", cfg.FISCAL_YEAR)
    fmt = (request.args.get("format", "csv") or "csv").lower()
    company_id = request.args.get("company_id", DEFAULT_COMPANY_ID)

    rows: list[dict] = []
    if supabase_available():
        sb = get_supabase()
        try:
            rows = (
                sb.table("tax_approved_mappings").select("*")
                .eq("company_id", company_id).eq("fiscal_year", fy)
                .order("gl_account").execute()
            ).data or []
        except Exception as e:
            log.warning("tax export supabase read failed: %s", e)

    base = f"tax_disclosure_FY{fy}"
    if fmt == "csv":
        return _export_response(tax_export.to_csv(rows),
                                mime="text/csv; charset=utf-8",
                                filename=f"{base}.csv")
    if fmt == "json":
        return _export_response(tax_export.to_json(rows, fy),
                                mime="application/json",
                                filename=f"{base}.json")
    if fmt == "docx":
        return _export_response(
            tax_export.to_docx(rows, fy),
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=f"{base}.docx",
        )
    return _error_response(400, "bad_request", "format must be csv | json | docx")


# ── Finance Agents (per April-2026 Cross-Agent Architecture spec) ───
#
# 9 agents, each obeying the Standard Agent Contract. Routes:
#   GET  /api/finance/agents           — registry (which agents exist)
#   POST /api/finance/<slug>/run       — fire the agent
#   GET  /api/finance/<slug>/latest    — latest output rows for that agent
#   GET  /api/finance/runs             — agent_runs registry (recent N)

@app.route("/api/finance/agents")
def finance_agents_list():
    from gl_intelligence.finance_agents import list_agents
    return jsonify({"agents": list_agents(), "count": len(list_agents())})


@app.route("/api/finance/<slug>/run", methods=["POST"])
def finance_agent_run(slug: str):
    from gl_intelligence.finance_agents import get_agent
    from gl_intelligence.finance_agents.base import AgentInput
    body = request.get_json(silent=True) or {}
    try:
        params = AgentInput(
            company_code=body.get("company_code", cfg.COMPANY_CODE),
            fiscal_year=str(body.get("fiscal_year", cfg.FISCAL_YEAR)),
            fiscal_period=body.get("fiscal_period", "Full Year"),
            run_id=body.get("run_id"),
            dry_run=bool(body.get("dry_run", False)),
            extra=body.get("extra") or {},
        )
        agent = get_agent(slug)
    except ValueError as e:
        return _error_response(404, "unknown_agent", str(e))

    out, err = _safe_run(lambda: agent.run(params))
    if err:
        return err
    return jsonify({
        "run_id":       out.run_id,
        "module":       out.module,
        "status":       out.status,
        "rows_written": out.rows_written,
        "duration_ms":  out.duration_ms,
        "summary":      out.summary,
        "error":        out.error,
    })


@app.route("/api/finance/<slug>/latest")
def finance_agent_latest(slug: str):
    from gl_intelligence.finance_agents import get_agent
    from gl_intelligence.persistence import supabase_available
    from gl_intelligence.persistence.supabase_client import get_supabase
    if not supabase_available():
        return jsonify({"rows": [], "supabase": False})
    try:
        agent_cls = type(get_agent(slug))
    except ValueError as e:
        return _error_response(404, "unknown_agent", str(e))

    sb = get_supabase()
    company_code = request.args.get("company_code", cfg.COMPANY_CODE)
    fy = request.args.get("fiscal_year", cfg.FISCAL_YEAR)
    try:
        # Latest run_id for this slug+company+fy
        latest = (
            sb.table("agent_runs").select("run_id,created_at,duration_ms,output_summary,status,error")
            .eq("module", agent_cls.MODULE).eq("company_code", company_code)
            .eq("fiscal_year", fy).order("created_at", desc=True).limit(1).execute()
        ).data
        if not latest:
            return jsonify({"rows": [], "summary": None, "run_id": None})
        run_id = latest[0]["run_id"]
        output_rows: list[dict] = []
        for tbl in agent_cls.OUTPUT_TABLES or [agent_cls.OUTPUT_TABLE]:
            try:
                rows = (sb.table(tbl).select("*").eq("run_id", run_id).execute()).data or []
                output_rows.append({"table": tbl, "rows": rows})
            except Exception:
                pass
        return jsonify({
            "run_id":  run_id,
            "summary": latest[0].get("output_summary"),
            "status":  latest[0].get("status"),
            "duration_ms": latest[0].get("duration_ms"),
            "tables":  output_rows,
        })
    except Exception as e:
        log.exception("finance_agent_latest failed")
        return _error_response(500, "internal_error", str(e))


@app.route("/api/finance/runs")
def finance_runs():
    from gl_intelligence.persistence import supabase_available
    from gl_intelligence.persistence.supabase_client import get_supabase
    if not supabase_available():
        return jsonify({"runs": [], "supabase": False})
    try:
        limit = max(1, min(int(request.args.get("limit", "30")), 200))
    except (TypeError, ValueError):
        return _error_response(400, "bad_request", "limit must be an integer")
    sb = get_supabase()
    rows = (
        sb.table("agent_runs").select("*")
        .order("created_at", desc=True).limit(limit).execute()
    ).data or []
    return jsonify({"runs": rows, "count": len(rows), "supabase": True})


# ── Static files (dashboard) ───────────────────────────────

ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "FASB DISE ASSETS"))
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LANDING_DIR = os.path.join(ROOT_DIR, "landing")

# Assets with content-hashed filenames (safe to cache forever).
# Everything under `_next/static/` is fingerprinted by Next.js.
_IMMUTABLE_PREFIXES = ("_next/static/",)
# Long-cache asset extensions (also hashed implicitly, but with a lower max-age).
_CACHEABLE_EXTS = {
    ".js", ".css", ".woff", ".woff2", ".ttf", ".otf",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    ".gltf", ".glb", ".mp4", ".webm",
}


def _is_within(base: str, target: str) -> bool:
    """Defense-in-depth: ensure resolved path stays inside base."""
    base = os.path.realpath(base)
    target = os.path.realpath(target)
    return target == base or target.startswith(base + os.sep)


def _cache_control_for(path: str) -> str | None:
    norm = path.replace("\\", "/").lstrip("/")
    if any(norm.startswith(p) for p in _IMMUTABLE_PREFIXES):
        return "public, max-age=31536000, immutable"
    ext = os.path.splitext(norm)[1].lower()
    if ext in _CACHEABLE_EXTS:
        return "public, max-age=86400, stale-while-revalidate=604800"
    return None


def _serve_static(base: str, filename: str):
    resp = send_from_directory(base, filename, conditional=True)
    cc = _cache_control_for(filename)
    if cc:
        resp.headers["Cache-Control"] = cc
    return resp


@app.route("/")
def index():
    resp = send_from_directory(LANDING_DIR, "index.html")
    # HTML itself must revalidate so new deploys are visible quickly.
    resp.headers["Cache-Control"] = "public, max-age=0, must-revalidate"
    return resp


@app.route("/app")
def app_dashboard():
    return send_from_directory(ROOT_DIR, "GL_Intelligence_Platform_6.html")


@app.route("/dashboard")
def dashboard():
    return send_from_directory(ASSETS_DIR, "DISE_Dashboard.html")


@app.route("/<path:filename>")
def static_files(filename):
    # Reject suspicious paths up front
    if ".." in filename.replace("\\", "/").split("/"):
        return _error_response(400, "bad_request", "invalid path")

    for base in (LANDING_DIR, ROOT_DIR, ASSETS_DIR):
        candidate = os.path.join(base, filename)
        if os.path.isfile(candidate) and _is_within(base, candidate):
            return _serve_static(base, filename)
    return _error_response(404, "not_found", "file not found")


def create_app() -> Flask:
    """Factory function for gunicorn."""
    log.info(
        "GL Intelligence API starting env=%s cors=%s rate_limit=%s/min version=%s",
        ENVIRONMENT,
        CORS_ALLOWED_ORIGINS,
        RATE_LIMIT_PER_MINUTE,
        APP_VERSION,
    )
    return app
