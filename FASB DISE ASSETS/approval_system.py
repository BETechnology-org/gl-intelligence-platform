"""
BE Technology — GL Intelligence Platform
GL Mapping Agent — Gmail Approval System v1.0
──────────────────────────────────────────────
Sends approval emails for pending GL mapping decisions.
Provides one-click Approve and Override buttons.
Processes approvals and promotes records to gl_dise_mapping.

Components:
  1. send_approval_emails()   — sends pending decisions to reviewer
  2. approval_server()        — Flask endpoint that processes clicks
  3. promote_approved()       — moves approved records to gl_dise_mapping
  4. update_close_tracker()   — flips T001 green when queue is clear

Prerequisites:
  pip install anthropic google-cloud-bigquery google-auth google-auth-httplib2 google-api-python-client flask

OAuth setup (one time):
  1. Go to console.cloud.google.com
  2. APIs & Services → Credentials → Create OAuth 2.0 Client ID
  3. Application type: Desktop App
  4. Download JSON → save as credentials.json in same folder as this script
  5. Run: python approval_system.py setup
     This opens a browser to authorise Gmail access and saves token.json
"""

import os
import json
import base64
import uuid
import logging
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.cloud import bigquery

# ── Configuration ──────────────────────────────────────────────
PROJECT         = os.environ.get('GOOGLE_CLOUD_PROJECT', 'diplomatic75')
DATASET         = os.environ.get('BQ_DATASET',           'dise_reporting')
FROM_EMAIL      = 'mrobasson@gmail.com'
TO_EMAIL        = 'mr@betechnology.org'
APPROVAL_BASE   = os.environ.get('APPROVAL_BASE_URL',    'http://localhost:8080')
AGENT_ID        = 'GL_MAPPING_AGENT_v1'

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

bq = bigquery.Client(project=PROJECT)


# ══════════════════════════════════════════════════════════════
# SECTION 1 — GMAIL OAUTH SETUP
# ══════════════════════════════════════════════════════════════

def get_gmail_service():
    """
    Authenticates with Gmail API using OAuth 2.0.
    First run opens browser for authorisation and saves token.json.
    Subsequent runs use saved token automatically.
    """
    creds = None

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as f:
            f.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


# ══════════════════════════════════════════════════════════════
# SECTION 2 — FETCH PENDING DECISIONS
# ══════════════════════════════════════════════════════════════

def get_pending_decisions() -> list[dict]:
    """
    Returns all PENDING decisions from pending_mappings
    ordered by materiality (HIGH first) then confidence (LOW first —
    lowest confidence needs most attention).
    """
    sql = f"""
    SELECT
      gl_account,
      description,
      posting_amount,
      fiscal_year,
      company_code,
      suggested_category,
      suggested_caption,
      suggested_citation,
      draft_reasoning,
      confidence_score,
      confidence_label,
      similar_accounts,
      materiality_flag,
      drafted_at
    FROM `{PROJECT}.{DATASET}.pending_mappings`
    WHERE status = 'PENDING'
    ORDER BY
      CASE materiality_flag
        WHEN 'HIGH'   THEN 1
        WHEN 'MEDIUM' THEN 2
        ELSE 3
      END,
      CASE confidence_label
        WHEN 'LOW'    THEN 1
        WHEN 'MEDIUM' THEN 2
        ELSE 3
      END,
      posting_amount DESC
    """
    rows = list(bq.query(sql).result())
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════
# SECTION 3 — BUILD APPROVAL EMAIL HTML
# ══════════════════════════════════════════════════════════════

def confidence_color(label: str) -> str:
    return {'HIGH': '#0A7C42', 'MEDIUM': '#92580A', 'LOW': '#C81A1A'}.get(label, '#666')

def materiality_color(label: str) -> str:
    return {'HIGH': '#C81A1A', 'MEDIUM': '#92580A', 'LOW': '#0A7C42'}.get(label, '#666')

def category_color(cat: str) -> str:
    return {
        'Purchases of inventory':       '#0A6B62',
        'Employee compensation':        '#1A56DB',
        'Depreciation':                 '#92580A',
        'Intangible asset amortization':'#5B34DA',
        'Other expenses':               '#3D4D6A',
    }.get(cat, '#666')

def build_decision_card(d: dict, index: int) -> str:
    """Builds one HTML card per pending decision."""
    approve_url  = f"{APPROVAL_BASE}/approve/{d['gl_account']}"
    override_url = f"{APPROVAL_BASE}/override/{d['gl_account']}"

    similar = []
    if d.get('similar_accounts'):
        try:
            similar = json.loads(d['similar_accounts'])
        except:
            pass

    similar_html = ''
    if similar:
        similar_html = '<div style="margin-top:12px"><div style="font-size:11px;font-weight:600;color:#475569;margin-bottom:6px;text-transform:uppercase;letter-spacing:.06em">Similar approved accounts used as reference</div>'
        for s in similar:
            similar_html += f"""
            <div style="display:flex;align-items:center;justify-content:space-between;
                        padding:6px 10px;background:#F8F9FC;border-radius:4px;margin-bottom:4px">
              <div>
                <span style="font-family:monospace;font-size:11px;color:#64748B">{s.get('gl_account','')}</span>
                <span style="font-size:12px;color:#1E293B;margin-left:8px">{s.get('description','')}</span>
              </div>
              <div style="display:flex;gap:8px;align-items:center">
                <span style="font-size:11px;color:{category_color(s.get('dise_category',''))};
                             background:#F1F5F9;padding:2px 6px;border-radius:3px">
                  {s.get('dise_category','')}
                </span>
                <span style="font-family:monospace;font-size:10px;color:#94A3B8">
                  sim: {s.get('similarity_score',0):.2f}
                </span>
              </div>
            </div>"""
        similar_html += '</div>'

    amount_fmt = f"${float(d.get('posting_amount', 0)):,.0f}"

    return f"""
    <div style="background:#FFFFFF;border:1px solid #E2E8F4;border-radius:10px;
                margin-bottom:20px;overflow:hidden;
                border-left:4px solid {confidence_color(d['confidence_label'])}">

      <!-- Card header -->
      <div style="padding:14px 18px;background:#F8F9FC;
                  border-bottom:1px solid #E2E8F4;
                  display:flex;align-items:center;justify-content:space-between">
        <div>
          <span style="font-family:monospace;font-size:12px;
                       font-weight:600;color:#0F1729">{d['gl_account']}</span>
          <span style="font-size:14px;font-weight:600;color:#0F1729;
                       margin-left:10px">{d['description']}</span>
        </div>
        <div style="display:flex;gap:8px">
          <span style="font-size:10px;font-weight:600;padding:3px 8px;border-radius:4px;
                       background:{materiality_color(d['materiality_flag'])}22;
                       color:{materiality_color(d['materiality_flag'])}">
            {d['materiality_flag']} MATERIALITY
          </span>
          <span style="font-size:10px;font-weight:600;padding:3px 8px;border-radius:4px;
                       background:{confidence_color(d['confidence_label'])}22;
                       color:{confidence_color(d['confidence_label'])}">
            {d['confidence_label']} CONFIDENCE {d['confidence_score']:.0%}
          </span>
        </div>
      </div>

      <!-- Card body -->
      <div style="padding:16px 18px">

        <!-- Agent decision -->
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px">
          <div style="background:#F8F9FC;border-radius:6px;padding:10px 12px">
            <div style="font-size:9px;font-weight:600;color:#94A3B8;
                        text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">
              DISE Category
            </div>
            <div style="font-size:13px;font-weight:600;
                        color:{category_color(d['suggested_category'])}">
              {d['suggested_category']}
            </div>
          </div>
          <div style="background:#F8F9FC;border-radius:6px;padding:10px 12px">
            <div style="font-size:9px;font-weight:600;color:#94A3B8;
                        text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">
              IS Caption
            </div>
            <div style="font-size:13px;font-weight:600;color:#0F1729">
              {d['suggested_caption']}
            </div>
          </div>
          <div style="background:#F8F9FC;border-radius:6px;padding:10px 12px">
            <div style="font-size:9px;font-weight:600;color:#94A3B8;
                        text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">
              FY2023 Amount
            </div>
            <div style="font-size:13px;font-weight:600;color:#0F1729">
              {amount_fmt}
            </div>
          </div>
        </div>

        <!-- ASC Citation -->
        <div style="background:#EEF3FF;border-radius:6px;padding:8px 12px;
                    margin-bottom:14px;display:flex;align-items:center;gap:8px">
          <span style="font-size:10px;font-weight:600;color:#1A56DB;
                       text-transform:uppercase;letter-spacing:.06em">ASC Citation</span>
          <span style="font-family:monospace;font-size:12px;color:#1A56DB;font-weight:500">
            {d['suggested_citation']}
          </span>
        </div>

        <!-- Agent reasoning -->
        <div style="margin-bottom:14px">
          <div style="font-size:10px;font-weight:600;color:#475569;
                      text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">
            Agent Reasoning
          </div>
          <div style="font-size:13px;color:#1E293B;line-height:1.7;
                      background:#FFFBF0;border-left:3px solid #C9A84C;
                      padding:10px 14px;border-radius:0 6px 6px 0">
            {d['draft_reasoning']}
          </div>
        </div>

        {similar_html}

        <!-- Action buttons -->
        <div style="display:flex;gap:10px;margin-top:18px">
          <a href="{approve_url}"
             style="flex:1;display:block;text-align:center;padding:12px;
                    background:#0A7C42;color:#FFFFFF;text-decoration:none;
                    border-radius:6px;font-weight:600;font-size:13px">
            ✓ Approve — {d['suggested_category']}
          </a>
          <a href="{override_url}"
             style="flex:1;display:block;text-align:center;padding:12px;
                    background:#FFFFFF;color:#0F1729;text-decoration:none;
                    border-radius:6px;font-weight:600;font-size:13px;
                    border:1px solid #C8D3E8">
            ✎ Override / Reject
          </a>
        </div>

      </div>
    </div>"""


def build_email_html(decisions: list[dict]) -> str:
    """Builds the complete approval email HTML."""
    high   = [d for d in decisions if d['materiality_flag'] == 'HIGH']
    medium = [d for d in decisions if d['materiality_flag'] == 'MEDIUM']
    low    = [d for d in decisions if d['materiality_flag'] == 'LOW']
    total_amount = sum(float(d.get('posting_amount', 0)) for d in decisions)

    cards_html = ''.join(
        build_decision_card(d, i) for i, d in enumerate(decisions)
    )

    bulk_approve_url = f"{APPROVAL_BASE}/bulk-approve-low"

    bulk_section = ''
    if low:
        bulk_section = f"""
        <div style="background:#E8F5EE;border:1px solid #A8D5BA;border-radius:8px;
                    padding:14px 18px;margin-bottom:20px">
          <div style="font-size:12px;font-weight:600;color:#0A7C42;margin-bottom:4px">
            Bulk approve option — {len(low)} LOW materiality, HIGH confidence accounts
          </div>
          <div style="font-size:12px;color:#1E293B;margin-bottom:10px">
            These accounts have posting amounts under $100,000 and HIGH agent confidence.
            You may approve them as a batch after reviewing the individual cards below.
          </div>
          <a href="{bulk_approve_url}"
             style="display:inline-block;padding:8px 16px;background:#0A7C42;
                    color:#FFFFFF;text-decoration:none;border-radius:5px;
                    font-weight:600;font-size:12px">
            Bulk Approve {len(low)} Low-Materiality Accounts
          </a>
        </div>"""

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#F8F9FC;font-family:'Helvetica Neue',Arial,sans-serif">
    <div style="max-width:680px;margin:0 auto;padding:24px 16px">

      <!-- Header -->
      <div style="background:#0F2044;border-radius:10px 10px 0 0;
                  padding:20px 24px;margin-bottom:0">
        <div style="font-size:10px;font-weight:600;color:rgba(255,255,255,0.5);
                    letter-spacing:.14em;text-transform:uppercase;margin-bottom:4px">
          BE Technology · GL Intelligence Platform
        </div>
        <div style="font-size:20px;font-weight:700;color:#FFFFFF">
          GL Mapping Review Required
        </div>
        <div style="font-size:12px;color:rgba(255,255,255,0.6);margin-top:4px">
          diplomatic75 · Company C006 · FY2023 · {datetime.now().strftime('%B %d, %Y')}
        </div>
      </div>

      <!-- Summary bar -->
      <div style="background:#1A56DB;padding:12px 24px;margin-bottom:20px;
                  display:flex;gap:24px">
        <div style="text-align:center">
          <div style="font-size:22px;font-weight:700;color:#FFFFFF">{len(decisions)}</div>
          <div style="font-size:10px;color:rgba(255,255,255,0.7);text-transform:uppercase">
            Pending
          </div>
        </div>
        <div style="text-align:center">
          <div style="font-size:22px;font-weight:700;color:#FFD0D0">{len(high)}</div>
          <div style="font-size:10px;color:rgba(255,255,255,0.7);text-transform:uppercase">
            High materiality
          </div>
        </div>
        <div style="text-align:center">
          <div style="font-size:22px;font-weight:700;color:#FFE4A0">{len(medium)}</div>
          <div style="font-size:10px;color:rgba(255,255,255,0.7);text-transform:uppercase">
            Medium
          </div>
        </div>
        <div style="text-align:center">
          <div style="font-size:22px;font-weight:700;color:#FFFFFF">${total_amount/1e6:.1f}M</div>
          <div style="font-size:10px;color:rgba(255,255,255,0.7);text-transform:uppercase">
            Total exposure
          </div>
        </div>
      </div>

      <!-- Instructions -->
      <div style="background:#EEF3FF;border-radius:8px;padding:14px 18px;
                  margin-bottom:20px;border-left:4px solid #1A56DB">
        <div style="font-size:12px;font-weight:600;color:#1A56DB;margin-bottom:4px">
          How to review
        </div>
        <div style="font-size:12px;color:#1E293B;line-height:1.7">
          Each card below shows one GL account the agent has classified.
          Review the reasoning and similar reference accounts, then click
          <strong>Approve</strong> to accept the agent's decision or
          <strong>Override</strong> to change the category.
          HIGH materiality accounts require individual review.
          LOW materiality HIGH confidence accounts may be bulk approved.
        </div>
      </div>

      {bulk_section}
      {cards_html}

      <!-- Footer -->
      <div style="border-top:1px solid #E2E8F4;padding-top:16px;margin-top:8px">
        <div style="font-size:10px;color:#94A3B8;line-height:1.7">
          BE Technology · GL Intelligence Platform · diplomatic75<br>
          ASU 2024-03 / ASC 220-40 · Autonomous GL Mapping Agent v1.0<br>
          All decisions require human approval before use in SEC disclosure.
        </div>
      </div>

    </div>
    </body>
    </html>"""


# ══════════════════════════════════════════════════════════════
# SECTION 4 — SEND EMAIL VIA GMAIL API
# ══════════════════════════════════════════════════════════════

def send_approval_email(decisions: list[dict]) -> bool:
    """Sends the approval email with all pending decisions."""
    if not decisions:
        log.info("No pending decisions to send.")
        return False

    log.info(f"Sending approval email for {len(decisions)} decisions to {TO_EMAIL}...")

    service = get_gmail_service()
    html_body = build_email_html(decisions)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = (
        f"[GL Intelligence] {len(decisions)} GL accounts require review — "
        f"${sum(float(d.get('posting_amount',0)) for d in decisions)/1e6:.1f}M exposure · "
        f"Company C006 FY2023"
    )
    msg['From']    = FROM_EMAIL
    msg['To']      = TO_EMAIL

    # Plain text fallback
    plain = f"""
GL Mapping Review Required — BE Technology GL Intelligence Platform

{len(decisions)} GL accounts are pending your review in diplomatic75.
Total exposure: ${sum(float(d.get('posting_amount',0)) for d in decisions):,.0f}

Please open this email in a browser that supports HTML to view the approval cards.

BE Technology · GL Intelligence Platform
"""
    msg.attach(MIMEText(plain, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(
        userId='me', body={'raw': raw}
    ).execute()

    log.info(f"✓ Approval email sent to {TO_EMAIL}")
    return True


# ══════════════════════════════════════════════════════════════
# SECTION 5 — PROCESS APPROVALS (Flask endpoint)
# ══════════════════════════════════════════════════════════════

def promote_to_gl_mapping(gl_account: str, reviewer: str,
                           override: dict = None) -> bool:
    """
    Promotes an approved pending_mapping to gl_dise_mapping.
    If override is provided, uses the reviewer's values instead of agent's.
    Updates the audit log.
    """
    # Fetch the pending record
    sql = f"""
    SELECT * FROM `{PROJECT}.{DATASET}.pending_mappings`
    WHERE gl_account = @gl_account
      AND status = 'PENDING'
    LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter('gl_account', 'STRING', gl_account)
        ]
    )
    rows = list(bq.query(sql, job_config=job_config).result())
    if not rows:
        log.error(f"No pending record found for {gl_account}")
        return False

    pending = dict(rows[0])
    now = datetime.now(timezone.utc).isoformat()

    # Use override values if provided, otherwise use agent's suggestion
    final_category = override.get('category', pending['suggested_category']) if override else pending['suggested_category']
    final_caption  = override.get('caption',  pending['suggested_caption'])  if override else pending['suggested_caption']
    final_citation = override.get('citation', pending['suggested_citation']) if override else pending['suggested_citation']
    human_agreed   = override is None
    event_type     = 'HUMAN_APPROVED' if human_agreed else 'HUMAN_OVERRIDDEN'

    # 1 — Insert into gl_dise_mapping
    insert_sql = f"""
    INSERT INTO `{PROJECT}.{DATASET}.gl_dise_mapping`
      (gl_account, description, dise_category, expense_caption,
       status, notes, reviewer, asc_citation)
    VALUES (
      @gl_account, @description, @dise_category, @expense_caption,
      'mapped', @notes, @reviewer, @asc_citation
    )
    """
    notes = (
        f"Approved by {reviewer} on {now[:10]}. "
        f"Agent reasoning: {pending['draft_reasoning'][:200]}..."
    )
    if override and override.get('reason'):
        notes += f" Override reason: {override['reason']}"

    bq.query(insert_sql, job_config=bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter('gl_account',    'STRING', gl_account),
            bigquery.ScalarQueryParameter('description',   'STRING', pending['description']),
            bigquery.ScalarQueryParameter('dise_category', 'STRING', final_category),
            bigquery.ScalarQueryParameter('expense_caption','STRING', final_caption),
            bigquery.ScalarQueryParameter('notes',         'STRING', notes),
            bigquery.ScalarQueryParameter('reviewer',      'STRING', reviewer),
            bigquery.ScalarQueryParameter('asc_citation',  'STRING', final_citation),
        ]
    )).result()

    # 2 — Update pending_mappings status
    update_sql = f"""
    UPDATE `{PROJECT}.{DATASET}.pending_mappings`
    SET status           = @status,
        reviewed_category = @category,
        reviewed_caption  = @caption,
        reviewed_citation = @citation,
        reviewer          = @reviewer,
        reviewed_at       = @reviewed_at,
        override_reason   = @override_reason
    WHERE gl_account = @gl_account
      AND status = 'PENDING'
    """
    bq.query(update_sql, job_config=bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter('status',         'STRING',    event_type.replace('HUMAN_','')),
            bigquery.ScalarQueryParameter('category',       'STRING',    final_category),
            bigquery.ScalarQueryParameter('caption',        'STRING',    final_caption),
            bigquery.ScalarQueryParameter('citation',       'STRING',    final_citation),
            bigquery.ScalarQueryParameter('reviewer',       'STRING',    reviewer),
            bigquery.ScalarQueryParameter('reviewed_at',    'TIMESTAMP', now),
            bigquery.ScalarQueryParameter('override_reason','STRING',    override.get('reason','') if override else ''),
            bigquery.ScalarQueryParameter('gl_account',     'STRING',    gl_account),
        ]
    )).result()

    # 3 — Write to audit log
    log_row = {
        'event_id':        str(uuid.uuid4()),
        'event_type':      event_type,
        'event_timestamp': now,
        'gl_account':      gl_account,
        'description':     pending['description'],
        'fiscal_year':     pending['fiscal_year'],
        'company_code':    pending['company_code'],
        'posting_amount':  float(pending.get('posting_amount', 0)),
        'agent_category':  pending['suggested_category'],
        'agent_caption':   pending['suggested_caption'],
        'agent_citation':  pending['suggested_citation'],
        'agent_confidence':float(pending.get('confidence_score', 0)),
        'agent_reasoning': pending['draft_reasoning'],
        'final_category':  final_category,
        'final_caption':   final_caption,
        'final_citation':  final_citation,
        'human_agreed':    human_agreed,
        'override_reason': override.get('reason', '') if override else '',
        'actor':           reviewer,
        'actor_type':      'HUMAN',
        'model_version':   pending.get('model_version', ''),
        'prompt_version':  pending.get('prompt_version', ''),
    }
    bq.insert_rows_json(f'{PROJECT}.{DATASET}.mapping_decisions_log', [log_row])

    log.info(f"✓ {gl_account} promoted to gl_dise_mapping as {final_category}")

    # 4 — Check if queue is clear and update T001
    check_and_update_t001()
    return True


def check_and_update_t001() -> None:
    """
    Checks if all pending mappings are approved.
    If yes, updates T001 in close_tasks to is_complete = TRUE.
    This is the moment the agentic loop closes — T001 goes green automatically.
    """
    sql = f"""
    SELECT COUNT(*) AS pending_count
    FROM `{PROJECT}.{DATASET}.pending_mappings`
    WHERE status = 'PENDING'
    """
    rows = list(bq.query(sql).result())
    pending_count = rows[0]['pending_count']

    if pending_count == 0:
        # Check total unmapped exposure
        exposure_sql = f"""
        SELECT COUNT(*) AS unmapped
        FROM `{PROJECT}.{DATASET}.pending_mappings`
        WHERE status NOT IN ('APPROVED', 'OVERRIDDEN')
        """
        unmapped = list(bq.query(exposure_sql).result())[0]['unmapped']

        if unmapped == 0:
            update_sql = f"""
            UPDATE `{PROJECT}.{DATASET}.close_tasks`
            SET is_complete  = TRUE,
                metric_value = '$0 unclassified — all accounts mapped and approved',
                detail       = 'All GL accounts mapped by GL_MAPPING_AGENT_v1 and approved by reviewer',
                last_checked_at = CURRENT_TIMESTAMP()
            WHERE task_id = 'T001'
            """
            bq.query(update_sql).result()
            log.info("✓ T001 updated to green — all accounts mapped and approved")
        else:
            log.info(f"T001 remains open — {unmapped} accounts still need review")
    else:
        log.info(f"T001 remains open — {pending_count} decisions still pending approval")


# ══════════════════════════════════════════════════════════════
# SECTION 6 — FLASK APPROVAL SERVER
# ══════════════════════════════════════════════════════════════

def start_approval_server():
    """
    Starts a local Flask server that handles approve/override clicks.
    In production deploy this to Cloud Run.
    For demo: run locally and use ngrok to expose the endpoint.
    """
    try:
        from flask import Flask, request, redirect, jsonify
    except ImportError:
        log.error("Flask not installed. Run: pip install flask")
        return

    app = Flask(__name__)

    @app.route('/approve/<gl_account>')
    def approve(gl_account):
        reviewer = request.args.get('reviewer', TO_EMAIL)
        success  = promote_to_gl_mapping(gl_account, reviewer)
        if success:
            return f"""
            <html><body style="font-family:Arial;text-align:center;padding:60px;background:#F8F9FC">
              <div style="background:#E8F5EE;border:1px solid #A8D5BA;border-radius:10px;
                          padding:30px;max-width:400px;margin:0 auto">
                <div style="font-size:48px">✓</div>
                <div style="font-size:20px;font-weight:600;color:#0A7C42;margin:12px 0">
                  Approved
                </div>
                <div style="font-size:14px;color:#1E293B">
                  GL account <strong>{gl_account}</strong> has been mapped
                  and added to gl_dise_mapping.
                </div>
                <div style="font-size:12px;color:#64748B;margin-top:12px">
                  The audit log has been updated. You can close this tab.
                </div>
              </div>
            </body></html>"""
        return "Error processing approval", 500

    @app.route('/override/<gl_account>', methods=['GET', 'POST'])
    def override(gl_account):
        if request.method == 'GET':
            # Show override form
            return f"""
            <html><body style="font-family:Arial;padding:40px;background:#F8F9FC;max-width:600px;margin:0 auto">
              <h2 style="color:#0F1729">Override mapping for {gl_account}</h2>
              <form method="POST">
                <div style="margin-bottom:16px">
                  <label style="font-weight:600;display:block;margin-bottom:4px">DISE Category</label>
                  <select name="category" style="width:100%;padding:8px;border-radius:4px;border:1px solid #C8D3E8">
                    <option>Purchases of inventory</option>
                    <option>Employee compensation</option>
                    <option>Depreciation</option>
                    <option>Intangible asset amortization</option>
                    <option>Other expenses</option>
                  </select>
                </div>
                <div style="margin-bottom:16px">
                  <label style="font-weight:600;display:block;margin-bottom:4px">Caption</label>
                  <select name="caption" style="width:100%;padding:8px;border-radius:4px;border:1px solid #C8D3E8">
                    <option>COGS</option>
                    <option>SG&A</option>
                    <option>R&D</option>
                    <option>Other income/expense</option>
                  </select>
                </div>
                <div style="margin-bottom:16px">
                  <label style="font-weight:600;display:block;margin-bottom:4px">ASC Citation</label>
                  <input name="citation" placeholder="e.g. ASC 220-40-50-6(c)"
                         style="width:100%;padding:8px;border-radius:4px;border:1px solid #C8D3E8">
                </div>
                <div style="margin-bottom:20px">
                  <label style="font-weight:600;display:block;margin-bottom:4px">
                    Override reason (required)
                  </label>
                  <textarea name="reason" rows="3" required
                            style="width:100%;padding:8px;border-radius:4px;border:1px solid #C8D3E8"
                            placeholder="Explain why the agent's suggestion was incorrect..."></textarea>
                </div>
                <button type="submit"
                        style="background:#0F2044;color:#FFF;padding:10px 24px;
                               border:none;border-radius:6px;font-size:14px;cursor:pointer">
                  Submit Override
                </button>
              </form>
            </body></html>"""

        # POST — process override
        override_data = {
            'category': request.form.get('category'),
            'caption':  request.form.get('caption'),
            'citation': request.form.get('citation'),
            'reason':   request.form.get('reason'),
        }
        reviewer = TO_EMAIL
        success  = promote_to_gl_mapping(gl_account, reviewer, override=override_data)
        if success:
            return f"""
            <html><body style="font-family:Arial;text-align:center;padding:60px;background:#F8F9FC">
              <div style="background:#FDF3DC;border:1px solid #DDB96A;border-radius:10px;
                          padding:30px;max-width:400px;margin:0 auto">
                <div style="font-size:48px">✎</div>
                <div style="font-size:20px;font-weight:600;color:#92580A;margin:12px 0">
                  Override recorded
                </div>
                <div style="font-size:14px;color:#1E293B">
                  GL account <strong>{gl_account}</strong> mapped as
                  <strong>{override_data['category']}</strong>.
                  Override reason saved to audit log.
                </div>
              </div>
            </body></html>"""
        return "Error processing override", 500

    @app.route('/bulk-approve-low')
    def bulk_approve_low():
        """Bulk approves all LOW materiality HIGH confidence pending decisions."""
        sql = f"""
        SELECT gl_account FROM `{PROJECT}.{DATASET}.pending_mappings`
        WHERE status = 'PENDING'
          AND materiality_flag = 'LOW'
          AND confidence_label = 'HIGH'
        """
        accounts = [dict(r)['gl_account'] for r in bq.query(sql).result()]
        approved = 0
        for gl_account in accounts:
            if promote_to_gl_mapping(gl_account, TO_EMAIL):
                approved += 1

        # Log bulk approval event
        bq.insert_rows_json(f'{PROJECT}.{DATASET}.mapping_decisions_log', [{
            'event_id':        str(uuid.uuid4()),
            'event_type':      'BULK_APPROVED',
            'event_timestamp': datetime.now(timezone.utc).isoformat(),
            'gl_account':      f'BULK:{len(accounts)} accounts',
            'description':     f'Bulk approval of {approved} LOW materiality HIGH confidence accounts',
            'actor':           TO_EMAIL,
            'actor_type':      'HUMAN',
        }])

        return f"""
        <html><body style="font-family:Arial;text-align:center;padding:60px;background:#F8F9FC">
          <div style="background:#E8F5EE;border:1px solid #A8D5BA;border-radius:10px;
                      padding:30px;max-width:400px;margin:0 auto">
            <div style="font-size:48px">✓</div>
            <div style="font-size:20px;font-weight:600;color:#0A7C42;margin:12px 0">
              {approved} accounts approved
            </div>
            <div style="font-size:14px;color:#1E293B">
              All LOW materiality HIGH confidence accounts have been mapped.
              Audit log updated.
            </div>
          </div>
        </body></html>"""

    @app.route('/status')
    def status():
        sql = f"""
        SELECT status, COUNT(*) AS count
        FROM `{PROJECT}.{DATASET}.pending_mappings`
        GROUP BY status
        """
        rows = {r['status']: r['count'] for r in bq.query(sql).result()}
        return jsonify(rows)

    log.info(f"Starting approval server on port 8080...")
    log.info(f"Approve URL format: {APPROVAL_BASE}/approve/{{gl_account}}")
    app.run(host='0.0.0.0', port=8080, debug=False)


# ══════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else 'help'

    if mode == 'setup':
        log.info("Setting up Gmail OAuth...")
        get_gmail_service()
        log.info("✓ Gmail authorised. token.json saved.")

    elif mode == 'send':
        decisions = get_pending_decisions()
        if decisions:
            send_approval_email(decisions)
        else:
            log.info("No pending decisions to send.")

    elif mode == 'server':
        start_approval_server()

    elif mode == 'check-t001':
        check_and_update_t001()

    else:
        print("Usage: python approval_system.py [setup|send|server|check-t001]")
        print("  setup      — authorise Gmail API (run once)")
        print("  send       — send approval email for all pending decisions")
        print("  server     — start approval endpoint server")
        print("  check-t001 — check if T001 should flip to green")
