"""
BE Technology — GL Intelligence Platform
Autonomous GL Mapping Agent — Approval Workflow v1.0
─────────────────────────────────────────────────────
DEPRECATED: Use approval_handler.py with SendGrid instead.
This file uses Gmail OAuth which requires browser-based token refresh
and is unsuitable for production Cloud Run deployments.

Kept for reference / local development only.

Components:
  1. Gmail notification — sends approval email after agent run
  2. Flask approval endpoint — handles approve / override clicks
  3. Close tracker integration — flips T001 green when queue clears

Prerequisites:
  pip install anthropic google-cloud-bigquery google-auth google-auth-oauthlib
              google-auth-httplib2 google-api-python-client flask

Gmail API setup (one-time):
  1. Go to console.cloud.google.com → APIs & Services → Enable APIs
  2. Search "Gmail API" and enable it
  3. Go to APIs & Services → Credentials → Create OAuth 2.0 Client ID
  4. Application type: Desktop App
  5. Download the JSON — save as credentials.json in same folder as this file
  6. Run: python approval_workflow.py setup
     This opens a browser, you log in, and token.json is created.
     After that, no more browser prompts.

Environment variables required (same as mapping_agent.py plus):
  ANTHROPIC_API_KEY
  GOOGLE_CLOUD_PROJECT=diplomatic75
  BQ_DATASET=dise_reporting
  REVIEWER_EMAIL=your-controller@company.com
  SENDER_EMAIL=your-gmail@gmail.com
  APPROVAL_BASE_URL=https://your-cloud-run-url.run.app
  PORT=8080  (Cloud Run default)
"""

from __future__ import annotations

import os
import json
import base64
import uuid
import logging
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape as html_escape

from flask import Flask, request, jsonify
from google.cloud import bigquery
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ── Configuration ──────────────────────────────────────────────
PROJECT          = os.environ.get('GOOGLE_CLOUD_PROJECT', 'diplomatic75')
DATASET          = os.environ.get('BQ_DATASET',           'dise_reporting')
REVIEWER_EMAIL   = os.environ.get('REVIEWER_EMAIL',       '')
SENDER_EMAIL     = os.environ.get('SENDER_EMAIL',         '')
APPROVAL_BASE_URL= os.environ.get('APPROVAL_BASE_URL',    'http://localhost:8080')
AGENT_ID         = 'GL_MAPPING_AGENT_v1'

GMAIL_SCOPES     = ['https://www.googleapis.com/auth/gmail.send']
TOKEN_FILE       = 'token.json'
CREDENTIALS_FILE = 'credentials.json'

# Valid values
VALID_CATEGORIES = [
    'Purchases of inventory', 'Employee compensation',
    'Depreciation', 'Intangible asset amortization', 'Other expenses',
]
VALID_CAPTIONS = ['COGS', 'SG&A', 'R&D', 'Other income/expense']

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s [%(name)s] %(message)s')
log = logging.getLogger('approval-workflow')

bq  = bigquery.Client(project=PROJECT)
app = Flask(__name__)


def _esc(value) -> str:
    """HTML-escape a value for safe rendering."""
    return html_escape(str(value)) if value is not None else ''


# ══════════════════════════════════════════════════════════════
# SECTION 1 — GMAIL AUTHENTICATION
# ══════════════════════════════════════════════════════════════

def get_gmail_service():
    """
    Returns authenticated Gmail API service.
    On first run: opens browser for OAuth consent.
    After that: uses token.json silently.
    """
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"credentials.json not found. Download from "
                    f"console.cloud.google.com → APIs & Services → Credentials"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


# ══════════════════════════════════════════════════════════════
# SECTION 2 — EMAIL BUILDER
# ══════════════════════════════════════════════════════════════

def build_approval_email(pending_records: list[dict]) -> str:
    """
    Builds the HTML approval email body.
    Each pending record gets its own card with approve / override buttons.
    HIGH materiality records are highlighted in red.
    """

    # ── Summary header ─────────────────────────────────────────
    total      = len(pending_records)
    high_mat   = sum(1 for r in pending_records if r['materiality_flag'] == 'HIGH')
    high_conf  = sum(1 for r in pending_records if r['confidence_label'] == 'HIGH')
    low_conf   = sum(1 for r in pending_records if r['confidence_label'] == 'LOW')

    # ── Confidence color map ───────────────────────────────────
    conf_colors = {
        'HIGH':   ('#E8F5EE', '#0A7C42', '✓ HIGH CONFIDENCE'),
        'MEDIUM': ('#FFF8E8', '#92580A', '~ MEDIUM CONFIDENCE'),
        'LOW':    ('#FFF0F0', '#C81A1A', '⚠ LOW CONFIDENCE — review carefully'),
    }
    mat_colors = {
        'HIGH':   '#C81A1A',
        'MEDIUM': '#92580A',
        'LOW':    '#0A7C42',
    }

    # ── Card HTML for each pending record ─────────────────────
    cards_html = ''
    for rec in pending_records:
        conf_bg, conf_fg, conf_label = conf_colors.get(
            rec.get('confidence_label', ''), ('#F1F4F9', '#3D4D6A', _esc(rec.get('confidence_label', '')))
        )
        mat_color = mat_colors.get(rec.get('materiality_flag', ''), '#3D4D6A')

        from urllib.parse import quote_plus
        gl_enc = quote_plus(str(rec.get('gl_account', '')))
        fy_enc = quote_plus(str(rec.get('fiscal_year', '')))
        approve_url  = f"{APPROVAL_BASE_URL}/approve?id={gl_enc}&fiscal_year={fy_enc}&action=approve"
        override_url = f"{APPROVAL_BASE_URL}/approve?id={gl_enc}&fiscal_year={fy_enc}&action=override"

        # Parse similar accounts JSON
        similar_html = ''
        try:
            similar = json.loads(rec.get('similar_accounts') or '[]')
            if similar:
                similar_html = '<div style="margin-top:10px"><strong style="font-size:11px;color:#7A8BA8">SIMILAR APPROVED ACCOUNTS USED AS REFERENCE:</strong><table style="width:100%;border-collapse:collapse;margin-top:6px;font-size:11px">'
                for s in similar[:3]:
                    similar_html += f"""
                    <tr style="border-bottom:1px solid #E2E8F4">
                      <td style="padding:4px 8px;color:#3D4D6A">{_esc(s.get('gl_account',''))}</td>
                      <td style="padding:4px 8px;color:#0F1729">{_esc(s.get('description',''))}</td>
                      <td style="padding:4px 8px;color:#1A56DB">{_esc(s.get('dise_category',''))}</td>
                      <td style="padding:4px 8px;color:#7A8BA8">{_esc(s.get('similarity_score',''))}</td>
                    </tr>"""
                similar_html += '</table></div>'
        except Exception:
            pass

        cards_html += f"""
        <div style="background:#FFFFFF;border:1px solid #E2E8F4;border-radius:8px;
                    margin-bottom:16px;overflow:hidden;
                    border-left:4px solid {mat_color}">

          <!-- Card header -->
          <div style="background:#F8F9FC;padding:12px 16px;
                      border-bottom:1px solid #E2E8F4;
                      display:flex;justify-content:space-between;align-items:center">
            <div>
              <span style="font-family:monospace;font-size:12px;
                           font-weight:600;color:#0F1729">{_esc(rec.get('gl_account',''))}</span>
              <span style="font-size:13px;color:#0F1729;margin-left:10px">
                {_esc(rec.get('description',''))}
              </span>
            </div>
            <span style="font-family:monospace;font-size:10px;font-weight:600;
                         color:{mat_color};padding:2px 8px;border-radius:3px;
                         background:{conf_bg}">
              {_esc(rec.get('materiality_flag',''))} MATERIALITY
            </span>
          </div>

          <!-- Card body -->
          <div style="padding:14px 16px">

            <!-- Agent decision -->
            <div style="background:{conf_bg};border-radius:6px;
                        padding:10px 14px;margin-bottom:12px">
              <div style="font-family:monospace;font-size:10px;
                          color:{conf_fg};margin-bottom:6px">
                {conf_label}
              </div>
              <table style="font-size:12px;border-collapse:collapse">
                <tr>
                  <td style="color:#7A8BA8;padding:2px 16px 2px 0;
                              font-family:monospace;font-size:10px">CATEGORY</td>
                  <td style="color:#0F1729;font-weight:600">
                    {_esc(rec.get('suggested_category',''))}
                  </td>
                </tr>
                <tr>
                  <td style="color:#7A8BA8;padding:2px 16px 2px 0;
                              font-family:monospace;font-size:10px">CAPTION</td>
                  <td style="color:#0F1729">{_esc(rec.get('suggested_caption',''))}</td>
                </tr>
                <tr>
                  <td style="color:#7A8BA8;padding:2px 16px 2px 0;
                              font-family:monospace;font-size:10px">CITATION</td>
                  <td style="color:#1A56DB;font-family:monospace;font-size:11px">
                    {_esc(rec.get('suggested_citation',''))}
                  </td>
                </tr>
                <tr>
                  <td style="color:#7A8BA8;padding:2px 16px 2px 0;
                              font-family:monospace;font-size:10px">AMOUNT</td>
                  <td style="color:#0F1729">
                    ${float(rec.get('posting_amount', 0)):,.0f} FY{_esc(rec.get('fiscal_year',''))}
                  </td>
                </tr>
              </table>
            </div>

            <!-- Agent reasoning -->
            <div style="font-size:12px;color:#3D4D6A;line-height:1.7;
                        margin-bottom:12px;padding:10px 14px;
                        background:#F8F9FC;border-radius:6px;
                        border-left:3px solid #1A56DB">
              <strong style="font-family:monospace;font-size:10px;
                             color:#7A8BA8;display:block;margin-bottom:4px">
                AGENT REASONING
              </strong>
              {_esc(rec.get('draft_reasoning',''))}
            </div>

            {similar_html}

            <!-- Action buttons -->
            <div style="margin-top:14px;display:flex;gap:10px">
              <a href="{approve_url}"
                 style="background:#0A7C42;color:#FFFFFF;padding:10px 20px;
                        border-radius:6px;text-decoration:none;font-size:13px;
                        font-weight:600;display:inline-block">
                ✓ Approve
              </a>
              <a href="{override_url}"
                 style="background:#FFFFFF;color:#1A56DB;padding:10px 20px;
                        border-radius:6px;text-decoration:none;font-size:13px;
                        font-weight:600;border:1px solid #1A56DB;display:inline-block">
                ✎ Override / Review
              </a>
            </div>

          </div>
        </div>
        """

    # ── Full email HTML ────────────────────────────────────────
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#F8F9FC;font-family:'Inter',Arial,sans-serif">
      <div style="max-width:700px;margin:0 auto;padding:24px 16px">

        <!-- Header -->
        <div style="background:#0F1729;border-radius:10px 10px 0 0;
                    padding:20px 24px;margin-bottom:0">
          <div style="font-size:10px;letter-spacing:0.14em;text-transform:uppercase;
                      color:#4A90D9;margin-bottom:4px">BE Technology</div>
          <div style="font-size:22px;font-weight:700;color:#FFFFFF">
            GL Mapping Agent — Approval Required
          </div>
          <div style="font-size:12px;color:#94A3B8;margin-top:4px">
            diplomatic75 · Company C006 · FY2023 · {datetime.now().strftime('%B %d, %Y %H:%M UTC')}
          </div>
        </div>

        <!-- Summary bar -->
        <div style="background:#1A56DB;padding:12px 24px;margin-bottom:20px;
                    display:flex;gap:24px">
          <div style="color:#FFFFFF;font-size:13px">
            <strong>{total}</strong> accounts pending review
          </div>
          <div style="color:#FFD700;font-size:13px">
            <strong>{high_mat}</strong> high materiality
          </div>
          <div style="color:#90EE90;font-size:13px">
            <strong>{high_conf}</strong> high confidence
          </div>
          {'<div style="color:#FFB3B3;font-size:13px"><strong>' + str(low_conf) + '</strong> low confidence — review carefully</div>' if low_conf > 0 else ''}
        </div>

        <!-- Instructions -->
        <div style="background:#EEF3FF;border:1px solid #C8D8FF;border-radius:8px;
                    padding:12px 16px;margin-bottom:20px;font-size:12px;color:#1A56DB">
          <strong>Instructions:</strong> Review each account below. Click
          <strong>Approve</strong> to accept the agent's suggestion, or
          <strong>Override</strong> to change the category before approving.
          High materiality accounts (≥$500K) require Controller sign-off.
          Your approval is recorded in the audit trail for SEC disclosure purposes.
        </div>

        <!-- Account cards -->
        {cards_html}

        <!-- Footer -->
        <div style="border-top:1px solid #E2E8F4;padding-top:16px;margin-top:8px;
                    font-size:10px;color:#7A8BA8;font-family:monospace">
          BE Technology · GL Intelligence Platform · ASU 2024-03 / ASC 220-40<br>
          Approvals are recorded in mapping_decisions_log and are legally significant.
          Do not approve accounts you have not reviewed.
        </div>

      </div>
    </body>
    </html>
    """
    return html


def send_approval_email(pending_records: list[dict]) -> bool:
    """Sends the approval email via Gmail API."""
    if not pending_records:
        log.info("No pending records — no email sent")
        return True

    try:
        service = get_gmail_service()

        msg = MIMEMultipart('alternative')
        msg['Subject'] = (
            f"[GL Intelligence] {len(pending_records)} accounts pending DISE mapping approval"
            f" — {sum(1 for r in pending_records if r['materiality_flag']=='HIGH')} HIGH materiality"
        )
        msg['From']    = SENDER_EMAIL
        msg['To']      = REVIEWER_EMAIL

        html_body = build_approval_email(pending_records)
        msg.attach(MIMEText(html_body, 'html'))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(
            userId='me',
            body={'raw': raw}
        ).execute()

        log.info(f"Approval email sent to {REVIEWER_EMAIL} "
                 f"({len(pending_records)} accounts)")
        return True

    except Exception as e:
        log.error(f"Email send failed: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# SECTION 3 — APPROVAL ENDPOINT (Flask / Cloud Run)
# Handles the approve / override button clicks from the email
# ══════════════════════════════════════════════════════════════

@app.route('/approve', methods=['GET', 'POST'])
def handle_approval():
    """
    Handles approval clicks from the email.

    GET  ?id=GL_ACCOUNT&fiscal_year=2023&action=approve
         → approves immediately, shows confirmation page

    GET  ?id=GL_ACCOUNT&fiscal_year=2023&action=override
         → shows override form where reviewer can change category

    POST (from override form)
         → saves the override and promotes to gl_dise_mapping
    """
    gl_account  = request.args.get('id')
    fiscal_year = request.args.get('fiscal_year', '2023')
    action      = request.args.get('action', 'approve')
    reviewer    = request.args.get('reviewer', REVIEWER_EMAIL)

    if not gl_account:
        return jsonify({'error': 'Missing account id'}), 400

    if action == 'approve' and request.method == 'GET':
        # Fetch the pending record
        record = get_pending_record(gl_account, fiscal_year)
        if not record:
            return _html_response('Already processed',
                f'Account {gl_account} has already been reviewed.', '#92580A')

        # Promote to gl_dise_mapping
        success = promote_to_mapping(
            gl_account      = gl_account,
            fiscal_year     = fiscal_year,
            final_category  = record['suggested_category'],
            final_caption   = record['suggested_caption'],
            final_citation  = record['suggested_citation'],
            reviewer        = reviewer,
            human_agreed    = True,
            override_reason = None,
            record          = record
        )
        if success:
            check_and_update_t001()
            return _html_response(
                '✓ Approved',
                f"""
                <strong>{gl_account}</strong> — {record['description']}<br><br>
                Mapped to: <strong>{record['suggested_category']}</strong>
                ({record['suggested_caption']})<br>
                Citation: {record['suggested_citation']}<br><br>
                This decision has been recorded in the audit trail.
                """,
                '#0A7C42'
            )
        return _html_response('Error', 'Approval failed — check logs.', '#C81A1A')

    elif action == 'override' and request.method == 'GET':
        # Show override form
        record = get_pending_record(gl_account, fiscal_year)
        if not record:
            return _html_response('Already processed',
                f'Account {gl_account} has already been reviewed.', '#92580A')

        categories = [
            'Purchases of inventory',
            'Employee compensation',
            'Depreciation',
            'Intangible asset amortization',
            'Other expenses'
        ]
        captions   = ['COGS', 'SG&A', 'R&D', 'Other income/expense']
        cat_options = ''.join(
            f'<option value="{c}" {"selected" if c==record["suggested_category"] else ""}>{c}</option>'
            for c in categories
        )
        cap_options = ''.join(
            f'<option value="{c}" {"selected" if c==record["suggested_caption"] else ""}>{c}</option>'
            for c in captions
        )

        return f"""
        <!DOCTYPE html><html>
        <head><meta charset="UTF-8">
        <title>Override Mapping — {gl_account}</title>
        <style>
          body{{font-family:Inter,Arial,sans-serif;background:#F8F9FC;
                margin:0;padding:24px}}
          .card{{background:#fff;border:1px solid #E2E8F4;border-radius:8px;
                 max-width:600px;margin:0 auto;padding:24px}}
          h2{{color:#0F1729;margin-top:0}}
          label{{display:block;font-size:12px;color:#7A8BA8;
                 margin-top:14px;margin-bottom:4px;font-family:monospace}}
          select,textarea,input{{width:100%;padding:8px 10px;border:1px solid #C8D3E8;
                                  border-radius:6px;font-size:13px;box-sizing:border-box}}
          .reasoning{{background:#F8F9FC;border-left:3px solid #1A56DB;
                      padding:10px;font-size:12px;color:#3D4D6A;
                      line-height:1.7;margin:12px 0;border-radius:0 6px 6px 0}}
          .btn{{background:#1A56DB;color:#fff;padding:10px 24px;border:none;
                border-radius:6px;font-size:13px;font-weight:600;cursor:pointer;
                margin-top:16px}}
        </style></head>
        <body>
        <div class="card">
          <h2>Override Mapping — {gl_account}</h2>
          <p style="color:#3D4D6A;font-size:13px">
            <strong>{record['description']}</strong><br>
            FY{fiscal_year} posting: ${float(record.get('posting_amount',0)):,.0f}
          </p>
          <div class="reasoning">
            <strong style="font-size:10px;color:#7A8BA8;font-family:monospace">
              AGENT REASONING
            </strong><br>
            {record['draft_reasoning']}
          </div>
          <form method="POST" action="/approve?id={gl_account}&fiscal_year={fiscal_year}&action=override&reviewer={reviewer}">
            <label>DISE CATEGORY</label>
            <select name="category">{cat_options}</select>

            <label>EXPENSE CAPTION</label>
            <select name="caption">{cap_options}</select>

            <label>ASC CITATION</label>
            <input name="citation" value="{_esc(record.get('suggested_citation',''))}" maxlength="100">

            <label>REASON FOR OVERRIDE (required)</label>
            <textarea name="reason" rows="3"
              placeholder="Explain why you are changing the agent's suggestion..."></textarea>

            <button type="submit" class="btn">Save Override & Approve</button>
          </form>
        </div>
        </body></html>
        """

    elif action == 'override' and request.method == 'POST':
        # Save the override with input validation
        category = request.form.get('category', '').strip()
        caption  = request.form.get('caption', '').strip()
        citation = request.form.get('citation', '').strip()[:100]
        reason   = request.form.get('reason', '').strip()[:2000]

        if category not in VALID_CATEGORIES:
            return _html_response('Invalid Input', 'A valid DISE category is required.', '#C81A1A')
        if caption not in VALID_CAPTIONS:
            return _html_response('Invalid Input', 'A valid expense caption is required.', '#C81A1A')

        record = get_pending_record(gl_account, fiscal_year)
        success = promote_to_mapping(
            gl_account      = gl_account,
            fiscal_year     = fiscal_year,
            final_category  = category,
            final_caption   = caption,
            final_citation  = citation,
            reviewer        = reviewer,
            human_agreed    = False,
            override_reason = reason,
            record          = record
        )
        if success:
            check_and_update_t001()
            return _html_response(
                'Override saved',
                f"""
                <strong>{_esc(gl_account)}</strong> mapped to:
                <strong>{_esc(category)}</strong> ({_esc(caption)})<br>
                Citation: {_esc(citation)}<br>
                Override reason: {_esc(reason)}<br><br>
                Recorded in audit trail.
                """,
                '#1A56DB'
            )
        return _html_response('Error', 'Override failed — check logs.', '#C81A1A')

    return jsonify({'error': 'Invalid request'}), 400


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'agent': 'GL_MAPPING_AGENT_v1'})


# ══════════════════════════════════════════════════════════════
# SECTION 4 — BIGQUERY OPERATIONS
# ══════════════════════════════════════════════════════════════

def get_pending_record(gl_account: str, fiscal_year: str) -> dict | None:
    """Fetches a single pending record."""
    sql = f"""
    SELECT *
    FROM `{PROJECT}.{DATASET}.pending_mappings`
    WHERE gl_account = @gl_account
      AND fiscal_year = @fiscal_year
      AND status = 'PENDING'
    LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter('gl_account',  'STRING', gl_account),
        bigquery.ScalarQueryParameter('fiscal_year', 'STRING', fiscal_year),
    ])
    rows = list(bq.query(sql, job_config=job_config).result())
    return dict(rows[0]) if rows else None


def get_all_pending(fiscal_year: str = '2023') -> list[dict]:
    """Returns all PENDING records ordered by materiality then confidence."""
    sql = f"""
    SELECT *
    FROM `{PROJECT}.{DATASET}.pending_mappings`
    WHERE status = 'PENDING'
      AND fiscal_year = @fiscal_year
    ORDER BY
      CASE materiality_flag WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END,
      CASE confidence_label WHEN 'LOW'  THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END,
      posting_amount DESC
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter('fiscal_year', 'STRING', fiscal_year),
    ])
    rows = list(bq.query(sql, job_config=job_config).result())
    return [dict(r) for r in rows]


def promote_to_mapping(
    gl_account: str, fiscal_year: str,
    final_category: str, final_caption: str, final_citation: str,
    reviewer: str, human_agreed: bool,
    override_reason: str | None, record: dict
) -> bool:
    """
    Promotes an approved pending_mapping to gl_dise_mapping.
    Updates pending_mappings status.
    Writes to mapping_decisions_log.
    All three operations in sequence.
    """
    now = datetime.now(timezone.utc).isoformat()

    try:
        # 1 — Insert into gl_dise_mapping
        insert_sql = f"""
        INSERT INTO `{PROJECT}.{DATASET}.gl_dise_mapping`
          (gl_account, description, dise_category, expense_caption,
           status, notes, reviewer, asc_citation)
        VALUES
          (@gl_account, @description, @category, @caption,
           'mapped', @notes, @reviewer, @citation)
        """
        notes = (
            f"Agent draft: {record.get('suggested_category')} — "
            f"{record.get('draft_reasoning','')[:200]}"
            + (f" | Override: {override_reason}" if override_reason else "")
        )
        bq.query(insert_sql, job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter('gl_account',  'STRING', gl_account),
                bigquery.ScalarQueryParameter('description', 'STRING', record.get('description','')),
                bigquery.ScalarQueryParameter('category',    'STRING', final_category),
                bigquery.ScalarQueryParameter('caption',     'STRING', final_caption),
                bigquery.ScalarQueryParameter('notes',       'STRING', notes),
                bigquery.ScalarQueryParameter('reviewer',    'STRING', reviewer),
                bigquery.ScalarQueryParameter('citation',    'STRING', final_citation),
            ]
        )).result()

        # 2 — Update pending_mappings status
        event_type = 'HUMAN_APPROVED' if human_agreed else 'HUMAN_OVERRIDDEN'
        update_sql = f"""
        UPDATE `{PROJECT}.{DATASET}.pending_mappings`
        SET status           = @status,
            reviewed_category= @category,
            reviewed_caption = @caption,
            reviewed_citation= @citation,
            override_reason  = @reason,
            reviewer         = @reviewer,
            reviewed_at      = @reviewed_at
        WHERE gl_account  = @gl_account
          AND fiscal_year = @fiscal_year
          AND status      = 'PENDING'
        """
        bq.query(update_sql, job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter('status',      'STRING', 'APPROVED' if human_agreed else 'OVERRIDDEN'),
                bigquery.ScalarQueryParameter('category',    'STRING', final_category),
                bigquery.ScalarQueryParameter('caption',     'STRING', final_caption),
                bigquery.ScalarQueryParameter('citation',    'STRING', final_citation),
                bigquery.ScalarQueryParameter('reason',      'STRING', override_reason or ''),
                bigquery.ScalarQueryParameter('reviewer',    'STRING', reviewer),
                bigquery.ScalarQueryParameter('reviewed_at', 'TIMESTAMP', now),
                bigquery.ScalarQueryParameter('gl_account',  'STRING', gl_account),
                bigquery.ScalarQueryParameter('fiscal_year', 'STRING', fiscal_year),
            ]
        )).result()

        # 3 — Write to audit log
        log_row = {
            'event_id':       str(uuid.uuid4()),
            'event_type':     event_type,
            'event_timestamp':now,
            'gl_account':     gl_account,
            'description':    record.get('description',''),
            'fiscal_year':    fiscal_year,
            'company_code':   record.get('company_code','C006'),
            'posting_amount': float(record.get('posting_amount', 0)),
            'agent_category': record.get('suggested_category',''),
            'agent_caption':  record.get('suggested_caption',''),
            'agent_citation': record.get('suggested_citation',''),
            'agent_confidence':float(record.get('confidence_score', 0)),
            'agent_reasoning':record.get('draft_reasoning',''),
            'final_category': final_category,
            'final_caption':  final_caption,
            'final_citation': final_citation,
            'human_agreed':   human_agreed,
            'override_reason':override_reason or '',
            'actor':          reviewer,
            'actor_type':     'HUMAN',
            'model_version':  record.get('model_version',''),
            'prompt_version': record.get('prompt_version',''),
        }
        errors = bq.insert_rows_json(
            f'{PROJECT}.{DATASET}.mapping_decisions_log', [log_row]
        )
        if errors:
            raise RuntimeError(f"Audit log error: {errors}")

        log.info(f"Promoted {gl_account} → {final_category} ({event_type})")
        return True

    except Exception as e:
        log.error(f"Promotion failed for {gl_account}: {e}")
        return False


def check_and_update_t001() -> None:
    """
    Checks if any PENDING records remain.
    If queue is empty, flips T001 (GL mapping task) to complete.
    This is the close tracker integration.
    """
    sql = f"""
    SELECT COUNT(*) AS pending_count
    FROM `{PROJECT}.{DATASET}.pending_mappings`
    WHERE status = 'PENDING'
    """
    rows = list(bq.query(sql).result())
    pending_count = rows[0]['pending_count'] if rows else 1

    if pending_count == 0:
        update_sql = f"""
        UPDATE `{PROJECT}.{DATASET}.close_tasks`
        SET is_complete   = TRUE,
            metric_value  = 'All pending mappings approved — zero unmapped exposure',
            last_checked_at = CURRENT_TIMESTAMP()
        WHERE task_id = 'T001'
        """
        bq.query(update_sql).result()
        log.info("T001 flipped to complete — all pending mappings approved")
    else:
        log.info(f"{pending_count} pending mappings still in queue")


# ══════════════════════════════════════════════════════════════
# SECTION 5 — HELPERS
# ══════════════════════════════════════════════════════════════

def _html_response(title: str, body: str, color: str) -> str:
    return f"""
    <!DOCTYPE html><html>
    <head><meta charset="UTF-8"><title>{title}</title></head>
    <body style="font-family:Inter,Arial,sans-serif;background:#F8F9FC;
                 display:flex;align-items:center;justify-content:center;
                 min-height:100vh;margin:0">
      <div style="background:#fff;border:1px solid #E2E8F4;border-radius:10px;
                  padding:32px;max-width:500px;text-align:center;
                  border-top:4px solid {color}">
        <div style="font-size:28px;font-weight:700;color:{color};
                    margin-bottom:12px">{title}</div>
        <div style="font-size:14px;color:#3D4D6A;line-height:1.7">{body}</div>
        <div style="margin-top:20px;font-size:11px;color:#7A8BA8;
                    font-family:monospace">
          BE Technology · GL Intelligence Platform
        </div>
      </div>
    </body></html>
    """


# ══════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else 'serve'

    if mode == 'setup':
        # One-time Gmail OAuth setup
        log.info("Setting up Gmail OAuth...")
        get_gmail_service()
        log.info("Gmail setup complete. token.json created.")

    elif mode == 'send':
        # Fetch pending records and send approval email
        fiscal_year = os.environ.get('FISCAL_YEAR', '2023')
        pending = get_all_pending(fiscal_year)
        if pending:
            log.info(f"Sending approval email for {len(pending)} pending records...")
            send_approval_email(pending)
        else:
            log.info("No pending records to send.")

    elif mode == 'serve':
        # Start the Flask approval endpoint
        port = int(os.environ.get('PORT', 8080))
        log.info(f"Starting approval server on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False)
