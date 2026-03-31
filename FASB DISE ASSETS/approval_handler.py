"""
BE Technology — GL Intelligence Platform
GL Mapping Agent — Approval Handler v1.1
─────────────────────────────────────────
Two components:

1. Approval Server (Flask / Cloud Run)
   Handles approve / override / reject actions from email links
   Promotes approved records from pending_mappings to gl_dise_mapping
   Updates mapping_decisions_log with human decision
   Triggers T001 close task recheck after every approval

2. Email Dispatcher
   Queries pending_mappings for PENDING records
   Sends one email per account (HIGH/MEDIUM materiality)
   Sends one bulk-approval email for LOW materiality batches

Prerequisites:
  pip install google-cloud-bigquery flask sendgrid

Environment variables:
  GOOGLE_CLOUD_PROJECT  — GCP project ID (default: diplomatic75)
  BQ_DATASET            — BigQuery dataset (default: dise_reporting)
  BQ_CDC_DATASET        — SAP CDC dataset (default: CORTEX_SAP_CDC)
  SENDGRID_API_KEY      — SendGrid API key for emails
  APPROVAL_BASE_URL     — Cloud Run approval server URL
  REVIEWER_EMAIL        — controller email for notifications
  REVIEWER_NAME         — default reviewer display name
  FISCAL_YEAR           — active fiscal year (default: 2023)
  COMPANY_CODE          — SAP company code (default: C006)
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import sys
import uuid
import json
import logging
from datetime import datetime, timezone
from html import escape as html_escape
from urllib.parse import quote_plus

from flask import Flask, request, jsonify
from google.cloud import bigquery

# ── Config ─────────────────────────────────────────────────────
PROJECT          = os.environ.get('GOOGLE_CLOUD_PROJECT', 'diplomatic75')
DATASET          = os.environ.get('BQ_DATASET',           'dise_reporting')
CDC_DATASET      = os.environ.get('BQ_CDC_DATASET',       'CORTEX_SAP_CDC')
FISCAL_YEAR      = os.environ.get('FISCAL_YEAR',          '2023')
COMPANY_CODE     = os.environ.get('COMPANY_CODE',         'C006')
APPROVAL_BASE_URL= os.environ.get('APPROVAL_BASE_URL',    'https://your-cloud-run-url.run.app')
REVIEWER_EMAIL   = os.environ.get('REVIEWER_EMAIL',       '')
REVIEWER_NAME    = os.environ.get('REVIEWER_NAME',        'Controller')
SENDGRID_KEY     = os.environ.get('SENDGRID_API_KEY',     '')
FROM_EMAIL       = os.environ.get('FROM_EMAIL',           'noreply@betechnology.com')

# HMAC signing key for approval links (prevents unauthorized approvals)
SIGNING_SECRET   = os.environ.get('APPROVAL_SIGNING_SECRET', 'change-me-in-production')

# Valid values — single source of truth
VALID_CATEGORIES = [
    'Purchases of inventory',
    'Employee compensation',
    'Depreciation',
    'Intangible asset amortization',
    'Other expenses',
]
VALID_CAPTIONS   = ['COGS', 'SG&A', 'R&D', 'Other income/expense']
VALID_STATUSES   = ['APPROVED', 'OVERRIDDEN', 'REJECTED']

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
)
log = logging.getLogger('approval-handler')

bq  = bigquery.Client(project=PROJECT)
app = Flask(__name__)


# ══════════════════════════════════════════════════════════════
# SECTION 0 — SECURITY HELPERS
# ══════════════════════════════════════════════════════════════

def _sign_url(gl_account: str, action: str) -> str:
    """Generate HMAC signature for an approval URL to prevent unauthorized actions."""
    payload = f"{gl_account}:{action}"
    sig = hmac.new(SIGNING_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return sig


def _verify_signature(gl_account: str, action: str, sig: str) -> bool:
    """Verify HMAC signature on an approval URL."""
    expected = _sign_url(gl_account, action)
    return hmac.compare_digest(sig, expected)


def _validate_gl_account(gl_account: str | None) -> str | None:
    """Validate GL account format. Returns cleaned value or None."""
    if not gl_account:
        return None
    cleaned = gl_account.strip()[:20]
    if not re.match(r'^[A-Za-z0-9_-]+$', cleaned):
        return None
    return cleaned


def _validate_reviewer(reviewer: str | None) -> str:
    """Sanitize reviewer name."""
    if not reviewer:
        return REVIEWER_NAME
    return reviewer.strip()[:100]


def _validate_category(category: str | None) -> str | None:
    """Validate category against allowed values."""
    if category and category in VALID_CATEGORIES:
        return category
    return None


def _validate_caption(caption: str | None) -> str | None:
    """Validate caption against allowed values."""
    if caption and caption in VALID_CAPTIONS:
        return caption
    return None


def _esc(value) -> str:
    """HTML-escape a value for safe rendering."""
    return html_escape(str(value)) if value is not None else ''


# ══════════════════════════════════════════════════════════════
# SECTION 1 — APPROVAL SERVER
# Cloud Run HTTP endpoint — handles approve/override/reject
# ══════════════════════════════════════════════════════════════

@app.route('/approve', methods=['GET'])
def approve():
    """
    One-click approval from email link.
    URL: /approve?gl_account=0000640080&reviewer=Controller&sig=abc123
    Promotes the pending record to gl_dise_mapping as-is.
    """
    gl_account = _validate_gl_account(request.args.get('gl_account'))
    reviewer   = _validate_reviewer(request.args.get('reviewer'))
    sig        = request.args.get('sig', '')

    if not gl_account:
        return jsonify({'error': 'Valid gl_account required'}), 400

    # Verify signature (skip in dev if secret is default)
    if SIGNING_SECRET != 'change-me-in-production':
        if not _verify_signature(gl_account, 'approve', sig):
            log.warning(f"Invalid signature for approve: {gl_account}")
            return _html_response('Unauthorized', 'Invalid or expired approval link.', success=False), 403

    try:
        pending = get_pending_record(gl_account)
        if not pending:
            return _html_response('Already Processed',
                f'Account {_esc(gl_account)} has already been reviewed.', success=True)

        promote_to_mapping(pending, reviewer, action='APPROVED')
        update_pending_status(gl_account, 'APPROVED', reviewer)
        write_human_decision_log(pending, reviewer, 'HUMAN_APPROVED', human_agreed=True)
        recheck_t001()

        log.info(f"APPROVED: {gl_account} — {pending.get('suggested_category')} — by {reviewer}")

        return _html_response(
            'Mapping Approved',
            f"""
            <p><strong>GL Account:</strong> {_esc(gl_account)}</p>
            <p><strong>Description:</strong> {_esc(pending.get('description'))}</p>
            <p><strong>Category:</strong> {_esc(pending.get('suggested_category'))}</p>
            <p><strong>Caption:</strong> {_esc(pending.get('suggested_caption'))}</p>
            <p><strong>ASC Citation:</strong> {_esc(pending.get('suggested_citation'))}</p>
            <p><strong>Approved by:</strong> {_esc(reviewer)}</p>
            <p style="color:#0A7C42;margin-top:16px">
              Record promoted to gl_dise_mapping. Close task T001 rechecked.
            </p>
            """,
            success=True
        )

    except Exception as e:
        log.error(f"Approval error for {gl_account}: {e}", exc_info=True)
        return _html_response('Error',
            'An internal error occurred. Please contact your administrator.',
            success=False), 500


@app.route('/override', methods=['GET', 'POST'])
def override():
    """
    Override form — reviewer can change category/caption/citation.
    GET:  renders the override form
    POST: saves the override decision
    """
    gl_account = _validate_gl_account(
        request.args.get('gl_account') or request.form.get('gl_account')
    )
    if not gl_account:
        return jsonify({'error': 'Valid gl_account required'}), 400

    if request.method == 'GET':
        pending = get_pending_record(gl_account)
        if not pending:
            return _html_response('Not Found',
                f'No pending record for {_esc(gl_account)}', success=False)

        cat_options = ''.join(
            f'<option value="{_esc(c)}" {"selected" if c == pending.get("suggested_category") else ""}>'
            f'{_esc(c)}</option>'
            for c in VALID_CATEGORIES
        )
        cap_options = ''.join(
            f'<option value="{_esc(c)}" {"selected" if c == pending.get("suggested_caption") else ""}>'
            f'{_esc(c)}</option>'
            for c in VALID_CAPTIONS
        )

        return f"""<!DOCTYPE html>
<html><head>
<title>Override Mapping — {_esc(gl_account)}</title>
<style>
  body{{font-family:Inter,sans-serif;max-width:680px;margin:40px auto;padding:0 24px;color:#0F1729}}
  h2{{color:#1A56DB;margin-bottom:4px}}
  .sub{{color:#7A8BA8;font-size:13px;margin-bottom:24px}}
  label{{display:block;font-size:12px;font-weight:500;color:#3D4D6A;margin-bottom:4px;margin-top:14px}}
  input,select,textarea{{width:100%;padding:8px 10px;border:1px solid #C8D3E8;border-radius:6px;font-size:13px;color:#0F1729}}
  textarea{{height:100px;resize:vertical}}
  .reasoning{{background:#F8F9FC;border:1px solid #E2E8F4;border-radius:6px;padding:12px;font-size:12px;color:#3D4D6A;line-height:1.6;margin-bottom:8px}}
  .conf{{display:inline-block;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:500;margin-bottom:16px}}
  .HIGH{{background:#E8F5EE;color:#0A7C42}}
  .MEDIUM{{background:#FEF3DC;color:#92580A}}
  .LOW{{background:#FDEAEA;color:#C81A1A}}
  button{{margin-top:20px;padding:10px 24px;background:#1A56DB;color:white;border:none;border-radius:6px;font-size:13px;cursor:pointer;font-weight:500}}
  button:hover{{background:#1648C8}}
</style></head><body>
<h2>Review GL Mapping</h2>
<div class="sub">GL Account {_esc(gl_account)} — Agent draft requires your review</div>

<label>Account Description</label>
<input type="text" value="{_esc(pending.get('description'))}" readonly style="background:#F8F9FC">

<label>Agent Reasoning</label>
<div class="reasoning">{_esc(pending.get('draft_reasoning'))}</div>
<span class="conf {_esc(pending.get('confidence_label'))}">{_esc(pending.get('confidence_label'))} confidence — {float(pending.get('confidence_score', 0)):.0%}</span>

<form method="POST" action="/override">
  <input type="hidden" name="gl_account" value="{_esc(gl_account)}">

  <label>DISE Category</label>
  <select name="category">{cat_options}</select>

  <label>Expense Caption</label>
  <select name="caption">{cap_options}</select>

  <label>ASC Citation</label>
  <input type="text" name="citation" value="{_esc(pending.get('suggested_citation'))}" maxlength="100">

  <label>Reviewer Name</label>
  <input type="text" name="reviewer" value="{_esc(REVIEWER_NAME)}" maxlength="100">

  <label>Override Reason (required if changing category)</label>
  <textarea name="override_reason" placeholder="Explain why you are changing the agent suggestion..." maxlength="2000"></textarea>

  <button type="submit">Save Decision</button>
</form>
</body></html>"""

    # POST — save the override
    category        = _validate_category(request.form.get('category'))
    caption         = _validate_caption(request.form.get('caption'))
    citation        = (request.form.get('citation', '') or '').strip()[:100]
    reviewer        = _validate_reviewer(request.form.get('reviewer'))
    override_reason = (request.form.get('override_reason', '') or '').strip()[:2000]

    if not category:
        return _html_response('Invalid Input', 'A valid DISE category is required.', success=False), 400
    if not caption:
        return _html_response('Invalid Input', 'A valid expense caption is required.', success=False), 400

    pending = get_pending_record(gl_account)
    if not pending:
        return _html_response('Not Found', f'No pending record for {_esc(gl_account)}', success=False)

    human_agreed = (
        category == pending.get('suggested_category') and
        caption  == pending.get('suggested_caption')
    )

    if not human_agreed and not override_reason:
        return _html_response('Override Reason Required',
            'You must provide a reason when changing the agent suggestion.', success=False), 400

    action = 'HUMAN_APPROVED' if human_agreed else 'HUMAN_OVERRIDDEN'

    # Override the pending record values for promotion
    pending['suggested_category'] = category
    pending['suggested_caption']  = caption
    pending['suggested_citation'] = citation

    try:
        promote_to_mapping(pending, reviewer, action=action, override_reason=override_reason)
        update_pending_status(
            gl_account,
            'OVERRIDDEN' if not human_agreed else 'APPROVED',
            reviewer,
            override_reason,
        )
        write_human_decision_log(
            pending, reviewer, action,
            human_agreed=human_agreed,
            override_reason=override_reason,
        )
        recheck_t001()

        log.info(f"{action}: {gl_account} — {category} — by {reviewer}")

        return _html_response(
            'Decision Saved',
            f'<p>GL {_esc(gl_account)} mapped to <strong>{_esc(category)}</strong> '
            f'({_esc(caption)}) and promoted to gl_dise_mapping.</p>'
            f'<p style="color:#0A7C42">Close task T001 rechecked.</p>',
            success=True
        )

    except Exception as e:
        log.error(f"Override error for {gl_account}: {e}", exc_info=True)
        return _html_response('Error',
            'An internal error occurred. Please contact your administrator.',
            success=False), 500


@app.route('/reject', methods=['GET'])
def reject():
    """Marks account as REJECTED — needs manual investigation."""
    gl_account = _validate_gl_account(request.args.get('gl_account'))
    reviewer   = _validate_reviewer(request.args.get('reviewer'))

    if not gl_account:
        return jsonify({'error': 'Valid gl_account required'}), 400

    try:
        update_pending_status(gl_account, 'REJECTED', reviewer)
        pending = get_pending_record_any_status(gl_account)
        if pending:
            write_human_decision_log(pending, reviewer, 'HUMAN_REJECTED', human_agreed=False)

        log.info(f"REJECTED: {gl_account} — requires manual investigation — by {reviewer}")

        return _html_response(
            'Account Flagged for Investigation',
            f'<p>GL {_esc(gl_account)} has been flagged. It will not appear in the DISE pivot '
            f'until manually classified and added to gl_dise_mapping.</p>',
            success=False
        )

    except Exception as e:
        log.error(f"Reject error for {gl_account}: {e}", exc_info=True)
        return _html_response('Error',
            'An internal error occurred. Please contact your administrator.',
            success=False), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint for Cloud Run."""
    try:
        # Verify BigQuery connectivity
        bq.query("SELECT 1").result()
        return jsonify({
            'status': 'ok',
            'project': PROJECT,
            'dataset': DATASET,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'detail': str(e)}), 503


# ══════════════════════════════════════════════════════════════
# SECTION 2 — BIGQUERY HELPERS
# ══════════════════════════════════════════════════════════════

def get_pending_record(gl_account: str) -> dict | None:
    """Fetch a single PENDING record from pending_mappings."""
    sql = f"""
    SELECT * FROM `{PROJECT}.{DATASET}.pending_mappings`
    WHERE gl_account = @gl_account AND status = 'PENDING'
    LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter('gl_account', 'STRING', gl_account)]
    )
    rows = list(bq.query(sql, job_config=job_config).result())
    return dict(rows[0]) if rows else None


def get_pending_record_any_status(gl_account: str) -> dict | None:
    """Fetch the most recent record for a GL account regardless of status."""
    sql = f"""
    SELECT * FROM `{PROJECT}.{DATASET}.pending_mappings`
    WHERE gl_account = @gl_account
    ORDER BY drafted_at DESC LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter('gl_account', 'STRING', gl_account)]
    )
    rows = list(bq.query(sql, job_config=job_config).result())
    return dict(rows[0]) if rows else None


def promote_to_mapping(pending: dict, reviewer: str,
                       action: str, override_reason: str = '') -> None:
    """
    Inserts the approved record into gl_dise_mapping.
    This is the moment the agent decision becomes part of the official mapping.
    """
    now = datetime.now(timezone.utc).isoformat()
    notes = (
        f"Autonomous mapping — {action} by {reviewer} on {now[:10]}. "
        f"Agent confidence: {pending.get('confidence_label', '?')} "
        f"({float(pending.get('confidence_score', 0)):.0%})."
    )
    if override_reason:
        notes += f" Override reason: {override_reason}"

    sql = f"""
    INSERT INTO `{PROJECT}.{DATASET}.gl_dise_mapping`
      (gl_account, description, dise_category, expense_caption,
       status, notes, reviewer, asc_citation)
    VALUES
      (@gl_account, @description, @dise_category, @expense_caption,
       'mapped', @notes, @reviewer, @asc_citation)
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter('gl_account',     'STRING', pending['gl_account']),
        bigquery.ScalarQueryParameter('description',    'STRING', str(pending.get('description', ''))[:500]),
        bigquery.ScalarQueryParameter('dise_category',  'STRING', pending['suggested_category']),
        bigquery.ScalarQueryParameter('expense_caption','STRING', pending['suggested_caption']),
        bigquery.ScalarQueryParameter('notes',          'STRING', notes[:2000]),
        bigquery.ScalarQueryParameter('reviewer',       'STRING', reviewer),
        bigquery.ScalarQueryParameter('asc_citation',   'STRING', str(pending.get('suggested_citation', ''))[:100]),
    ])
    bq.query(sql, job_config=job_config).result()
    log.info(f"Promoted {pending['gl_account']} to gl_dise_mapping ({action})")


def update_pending_status(gl_account: str, status: str,
                          reviewer: str, override_reason: str = '') -> None:
    """Updates the status of a pending_mappings record after human review."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")

    sql = f"""
    UPDATE `{PROJECT}.{DATASET}.pending_mappings`
    SET status          = @status,
        reviewer        = @reviewer,
        reviewed_at     = CURRENT_TIMESTAMP(),
        override_reason = @override_reason
    WHERE gl_account    = @gl_account
      AND status        = 'PENDING'
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter('status',          'STRING', status),
        bigquery.ScalarQueryParameter('reviewer',        'STRING', reviewer),
        bigquery.ScalarQueryParameter('override_reason', 'STRING', override_reason[:2000]),
        bigquery.ScalarQueryParameter('gl_account',      'STRING', gl_account),
    ])
    bq.query(sql, job_config=job_config).result()


def write_human_decision_log(pending: dict, reviewer: str, event_type: str,
                             human_agreed: bool,
                             override_reason: str = '') -> None:
    """Writes the human decision to the immutable audit log."""
    row = {
        'event_id':         str(uuid.uuid4()),
        'event_type':       event_type,
        'event_timestamp':  datetime.now(timezone.utc).isoformat(),
        'gl_account':       pending['gl_account'],
        'description':      str(pending.get('description', ''))[:500],
        'fiscal_year':      pending.get('fiscal_year', FISCAL_YEAR),
        'company_code':     pending.get('company_code', COMPANY_CODE),
        'posting_amount':   float(pending.get('posting_amount', 0)),
        'agent_category':   pending.get('suggested_category', ''),
        'agent_caption':    pending.get('suggested_caption', ''),
        'agent_citation':   pending.get('suggested_citation', ''),
        'agent_confidence': float(pending.get('confidence_score', 0)),
        'agent_reasoning':  str(pending.get('draft_reasoning', ''))[:5000],
        'final_category':   pending.get('suggested_category', ''),
        'final_caption':    pending.get('suggested_caption', ''),
        'final_citation':   pending.get('suggested_citation', ''),
        'human_agreed':     human_agreed,
        'override_reason':  override_reason[:2000],
        'actor':            reviewer,
        'actor_type':       'HUMAN',
        'model_version':    pending.get('model_version', ''),
        'prompt_version':   pending.get('prompt_version', ''),
    }
    errors = bq.insert_rows_json(
        f'{PROJECT}.{DATASET}.mapping_decisions_log', [row]
    )
    if errors:
        log.error(f"Audit log write error for {pending['gl_account']}: {errors}")


def recheck_t001() -> None:
    """
    Rechecks T001 close task after every approval.
    If zero unmapped accounts remain, T001 flips to complete.
    Uses parameterized fiscal year and company code.
    """
    try:
        check_sql = f"""
        SELECT COUNT(*) AS unmapped
        FROM `{PROJECT}.{CDC_DATASET}.bkpf` bkpf
        JOIN `{PROJECT}.{CDC_DATASET}.bseg` bseg
          ON  bkpf.MANDT = bseg.MANDT AND bkpf.BUKRS = bseg.BUKRS
          AND bkpf.BELNR = bseg.BELNR AND bkpf.GJAHR = bseg.GJAHR
        JOIN `{PROJECT}.{CDC_DATASET}.ska1` ska1
          ON  bseg.HKONT = ska1.SAKNR AND bseg.MANDT = ska1.MANDT
          AND ska1.ktopl = 'CA01'
        LEFT JOIN `{PROJECT}.{DATASET}.gl_dise_mapping` m
          ON bseg.HKONT = m.gl_account
        WHERE bkpf.GJAHR = @fiscal_year
          AND bkpf.BUKRS = @company_code
          AND bkpf.BLART NOT IN ('AA', 'AF', 'AB')
          AND (ska1.xbilk = '' OR ska1.xbilk IS NULL)
          AND m.gl_account IS NULL
        """
        check_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter('fiscal_year',  'STRING', FISCAL_YEAR),
            bigquery.ScalarQueryParameter('company_code', 'STRING', COMPANY_CODE),
        ])
        rows = list(bq.query(check_sql, job_config=check_config).result())
        unmapped = int(rows[0]['unmapped']) if rows else 0
        is_complete = unmapped == 0
        metric = (
            '$0 unclassified — mapping complete'
            if is_complete
            else f'{unmapped} accounts with unclassified postings'
        )

        update_sql = f"""
        UPDATE `{PROJECT}.{DATASET}.close_tasks`
        SET is_complete     = @is_complete,
            metric_value    = @metric,
            last_checked_at = CURRENT_TIMESTAMP(),
            completed_at    = CASE WHEN @is_complete AND completed_at IS NULL
                              THEN CURRENT_TIMESTAMP() ELSE completed_at END
        WHERE task_id = 'T001'
        """
        update_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter('is_complete', 'BOOL',   is_complete),
            bigquery.ScalarQueryParameter('metric',      'STRING', metric),
        ])
        bq.query(update_sql, job_config=update_config).result()
        log.info(f"T001 rechecked — unmapped={unmapped} is_complete={is_complete}")

    except Exception as e:
        log.error(f"T001 recheck failed: {e}", exc_info=True)


# ══════════════════════════════════════════════════════════════
# SECTION 3 — EMAIL DISPATCHER
# Run separately: python approval_handler.py send-emails
# ══════════════════════════════════════════════════════════════

def _build_approval_url(gl_account: str, action: str) -> str:
    """Build a signed approval URL."""
    sig = _sign_url(gl_account, action)
    reviewer_enc = quote_plus(REVIEWER_NAME)
    return f"{APPROVAL_BASE_URL}/{action}?gl_account={quote_plus(gl_account)}&reviewer={reviewer_enc}&sig={sig}"


def send_approval_emails() -> None:
    """
    Queries pending_mappings and sends approval emails.
    HIGH/MEDIUM materiality: one email per account with full reasoning.
    LOW materiality + HIGH confidence: one bulk-approval email.
    """
    if not REVIEWER_EMAIL:
        log.error("REVIEWER_EMAIL not set. Cannot send emails.")
        return
    if not SENDGRID_KEY:
        log.error("SENDGRID_API_KEY not set. Cannot send emails.")
        return

    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_KEY)
    except ImportError:
        log.error("sendgrid not installed. Run: pip install sendgrid")
        return

    sql = f"""
    SELECT * FROM `{PROJECT}.{DATASET}.pending_mappings`
    WHERE status = 'PENDING'
    ORDER BY
      CASE materiality_flag WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END,
      confidence_score DESC
    """
    pending = [dict(r) for r in bq.query(sql).result()]

    if not pending:
        log.info("No pending mappings to email.")
        return

    # Split into individual review vs bulk approval
    individual = [p for p in pending
                  if p.get('materiality_flag') in ('HIGH', 'MEDIUM')
                  or p.get('confidence_label') in ('LOW', 'MEDIUM')]
    bulk_set = set(id(p) for p in individual)
    bulk = [p for p in pending
            if p.get('materiality_flag') == 'LOW'
            and p.get('confidence_label') == 'HIGH'
            and id(p) not in bulk_set]

    log.info(f"Sending {len(individual)} individual + "
             f"{'1 bulk' if bulk else 'no bulk'} email "
             f"({len(bulk)} LOW/HIGH accounts)")

    sent = 0
    failed = 0

    # ── Individual emails ─────────────────────────────────────
    for p in individual:
        approve_url  = _build_approval_url(p['gl_account'], 'approve')
        override_url = f"{APPROVAL_BASE_URL}/override?gl_account={quote_plus(p['gl_account'])}"
        reject_url   = _build_approval_url(p['gl_account'], 'reject')

        conf_colour = {'HIGH': '#0A7C42', 'MEDIUM': '#92580A', 'LOW': '#C81A1A'}.get(
            p.get('confidence_label', ''), '#3D4D6A')
        mat_colour = {'HIGH': '#C81A1A', 'MEDIUM': '#92580A', 'LOW': '#0A7C42'}.get(
            p.get('materiality_flag', ''), '#3D4D6A')

        html = f"""<!DOCTYPE html><html><body style="font-family:Inter,sans-serif;max-width:600px;margin:0 auto;color:#0F1729">
<div style="background:#1A56DB;padding:16px 24px;border-radius:8px 8px 0 0">
  <div style="color:rgba(255,255,255,0.7);font-size:11px;letter-spacing:.1em;text-transform:uppercase">BE Technology &middot; GL Intelligence Platform</div>
  <div style="color:#FFFFFF;font-size:18px;font-weight:600;margin-top:4px">GL Mapping Review Required</div>
</div>
<div style="background:#F8F9FC;padding:20px 24px;border:1px solid #E2E8F4;border-top:none">
  <table style="width:100%;border-collapse:collapse;font-size:13px">
    <tr><td style="padding:6px 0;color:#7A8BA8;width:140px">GL Account</td><td style="font-weight:500">{_esc(p['gl_account'])}</td></tr>
    <tr><td style="padding:6px 0;color:#7A8BA8">Description</td><td style="font-weight:500">{_esc(p.get('description'))}</td></tr>
    <tr><td style="padding:6px 0;color:#7A8BA8">FY Postings</td><td>${float(p.get('posting_amount', 0)):,.0f}</td></tr>
    <tr><td style="padding:6px 0;color:#7A8BA8">Materiality</td><td style="color:{mat_colour};font-weight:500">{_esc(p.get('materiality_flag'))}</td></tr>
  </table>
</div>
<div style="background:#FFFFFF;padding:20px 24px;border:1px solid #E2E8F4;border-top:none">
  <div style="font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#1A56DB;margin-bottom:8px">Agent Recommendation</div>
  <table style="width:100%;border-collapse:collapse;font-size:13px">
    <tr><td style="padding:6px 0;color:#7A8BA8;width:140px">DISE Category</td><td style="font-weight:600;color:#0F1729">{_esc(p.get('suggested_category'))}</td></tr>
    <tr><td style="padding:6px 0;color:#7A8BA8">Caption</td><td>{_esc(p.get('suggested_caption'))}</td></tr>
    <tr><td style="padding:6px 0;color:#7A8BA8">ASC Citation</td><td style="font-family:monospace">{_esc(p.get('suggested_citation'))}</td></tr>
    <tr><td style="padding:6px 0;color:#7A8BA8">Confidence</td><td style="color:{conf_colour};font-weight:500">{_esc(p.get('confidence_label'))} ({float(p.get('confidence_score', 0)):.0%})</td></tr>
  </table>
  <div style="margin-top:12px;padding:12px;background:#F8F9FC;border-radius:6px;font-size:12px;color:#3D4D6A;line-height:1.7;border-left:3px solid #1A56DB">
    {_esc(p.get('draft_reasoning'))}
  </div>
</div>
<div style="padding:20px 24px;border:1px solid #E2E8F4;border-top:none;border-radius:0 0 8px 8px">
  <div style="font-size:11px;color:#7A8BA8;margin-bottom:12px">Review this mapping and take one of the following actions:</div>
  <a href="{approve_url}" style="display:inline-block;padding:10px 20px;background:#0A7C42;color:white;text-decoration:none;border-radius:6px;font-size:13px;font-weight:500;margin-right:8px">Approve</a>
  <a href="{override_url}" style="display:inline-block;padding:10px 20px;background:#1A56DB;color:white;text-decoration:none;border-radius:6px;font-size:13px;font-weight:500;margin-right:8px">Override</a>
  <a href="{reject_url}" style="display:inline-block;padding:10px 20px;background:#C81A1A;color:white;text-decoration:none;border-radius:6px;font-size:13px;font-weight:500">Reject</a>
  <div style="margin-top:16px;font-size:11px;color:#7A8BA8">{_esc(PROJECT)} &middot; FY{_esc(FISCAL_YEAR)} &middot; Company {_esc(COMPANY_CODE)}</div>
</div>
</body></html>"""

        message = Mail(
            from_email=FROM_EMAIL,
            to_emails=REVIEWER_EMAIL,
            subject=f"[{p.get('materiality_flag', 'REVIEW')}] GL Mapping Review — {p['gl_account']} {(p.get('description') or '')[:50]}",
            html_content=html,
        )
        try:
            sg.send(message)
            log.info(f"Email sent for {p['gl_account']}")
            sent += 1
        except Exception as e:
            log.error(f"Email failed for {p['gl_account']}: {e}")
            failed += 1

    # ── Bulk approval email ───────────────────────────────────
    if bulk:
        rows_html = ''.join(
            f"<tr style='border-bottom:1px solid #E2E8F4'>"
            f"<td style='padding:8px 12px;font-family:monospace;font-size:11px'>{_esc(p['gl_account'])}</td>"
            f"<td style='padding:8px 12px;font-size:12px'>{_esc(p.get('description'))}</td>"
            f"<td style='padding:8px 12px;font-size:12px'>{_esc(p.get('suggested_category'))}</td>"
            f"<td style='padding:8px 12px;font-size:12px'>${float(p.get('posting_amount', 0)):,.0f}</td>"
            f"<td style='padding:8px 12px'>"
            f"<a href='{_build_approval_url(p['gl_account'], 'approve')}' "
            f"style='color:#0A7C42;font-size:11px;font-weight:500'>Approve</a></td>"
            f"</tr>"
            for p in bulk
        )
        bulk_html = f"""<!DOCTYPE html><html><body style="font-family:Inter,sans-serif;max-width:700px;margin:0 auto;color:#0F1729">
<div style="background:#1A56DB;padding:16px 24px;border-radius:8px 8px 0 0">
  <div style="color:rgba(255,255,255,0.7);font-size:11px;text-transform:uppercase;letter-spacing:.1em">BE Technology &middot; GL Intelligence Platform</div>
  <div style="color:#FFFFFF;font-size:18px;font-weight:600;margin-top:4px">Bulk Approval — {len(bulk)} LOW Materiality Accounts</div>
  <div style="color:rgba(255,255,255,0.7);font-size:12px;margin-top:4px">All HIGH confidence &middot; Review individually or approve each below</div>
</div>
<div style="border:1px solid #E2E8F4;border-top:none;border-radius:0 0 8px 8px;overflow:hidden">
  <table style="width:100%;border-collapse:collapse">
    <thead style="background:#F8F9FC">
      <tr>
        <th style="padding:8px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#7A8BA8">GL Account</th>
        <th style="padding:8px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#7A8BA8">Description</th>
        <th style="padding:8px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#7A8BA8">Category</th>
        <th style="padding:8px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#7A8BA8">FY Amount</th>
        <th style="padding:8px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#7A8BA8">Action</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>
</body></html>"""

        message = Mail(
            from_email=FROM_EMAIL,
            to_emails=REVIEWER_EMAIL,
            subject=f"[BULK] GL Mapping Approval — {len(bulk)} LOW materiality accounts",
            html_content=bulk_html,
        )
        try:
            sg.send(message)
            log.info(f"Bulk email sent for {len(bulk)} accounts")
            sent += 1
        except Exception as e:
            log.error(f"Bulk email failed: {e}")
            failed += 1

    log.info(f"Email dispatch complete: {sent} sent, {failed} failed")


# ══════════════════════════════════════════════════════════════
# UTILITY — HTML RESPONSE HELPER
# ══════════════════════════════════════════════════════════════

def _html_response(title: str, body: str, success: bool = True) -> str:
    colour = '#0A7C42' if success else '#C81A1A'
    return f"""<!DOCTYPE html>
<html><head><title>{_esc(title)}</title>
<style>body{{font-family:Inter,sans-serif;max-width:560px;margin:60px auto;padding:0 24px;color:#0F1729}}
h2{{color:{colour}}}p{{color:#3D4D6A;line-height:1.6}}
.back{{margin-top:24px;font-size:12px;color:#7A8BA8}}</style>
</head><body>
<h2>{_esc(title)}</h2>{body}
<div class="back">BE Technology &middot; GL Intelligence Platform</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'server'

    if mode == 'send-emails':
        send_approval_emails()
    elif mode == 'server':
        port = int(os.environ.get('PORT', 8080))
        log.info(f"Starting approval server on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        print("Usage: python approval_handler.py [server|send-emails]")
        print("  server      — start the Flask approval endpoint (default)")
        print("  send-emails — dispatch approval emails for pending mappings")
        sys.exit(1)
