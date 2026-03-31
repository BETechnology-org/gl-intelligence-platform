"""
BE Technology — GL Intelligence Platform
Demo Controller Server v1.0
────────────────────────────────────────
Single Flask server that:
  1. Serves the demo controller HTML page
  2. Runs the full demo sequence via API calls
  3. Handles approve/override clicks from emails
  4. Shows live status updates via server-sent events

Run: python demo_controller.py
Open: https://8080-cs-XXXXXX.cloudshell.dev/demo

One page. One button. Full demo.
"""

import os
import json
import uuid
import base64
import logging
import threading
import time
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Flask, Response, jsonify, request, stream_with_context
from google.cloud import bigquery
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import anthropic

# ── Configuration ──────────────────────────────────────────────
PROJECT       = os.environ.get('GOOGLE_CLOUD_PROJECT', 'diplomatic75')
DATASET       = os.environ.get('BQ_DATASET',           'dise_reporting')
FROM_EMAIL    = os.environ.get('FROM_EMAIL',            'noreply@betechnology.com')
TO_EMAIL      = os.environ.get('TO_EMAIL',              'demo@betechnology.org')
APPROVAL_BASE = os.environ.get('APPROVAL_BASE_URL',     'http://localhost:8080')
MODEL         = os.environ.get('CLAUDE_MODEL',          'claude-sonnet-4-20250514')
AGENT_ID      = 'GL_MAPPING_AGENT_v1'

# Demo account — realistic unmapped account for the demo
DEMO_ACCOUNT = {
    'gl_account':    '0000640090',
    'description':   'Depreciation Expense - Leasehold Improvements',
    'posting_amount': 387500,
    'fiscal_year':   '2023',
    'company_code':  'C006',
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s [%(name)s] %(message)s')
log = logging.getLogger('demo-controller')

try:
    bq = bigquery.Client(project=PROJECT)
except Exception as e:
    log.error(f"Failed to initialize BigQuery client: {e}")
    raise SystemExit(1)

api_key = os.environ.get('ANTHROPIC_API_KEY')
if not api_key:
    log.error("ANTHROPIC_API_KEY environment variable is not set.")
    raise SystemExit(1)
claude = anthropic.Anthropic(api_key=api_key)

app = Flask(__name__)

# Global demo state for SSE streaming
demo_events = []
demo_lock   = threading.Lock()


def push_event(event_type: str, data: dict):
    with demo_lock:
        demo_events.append({'type': event_type, 'data': data, 'ts': time.time()})


# ══════════════════════════════════════════════════════════════
# DEMO HTML PAGE
# ══════════════════════════════════════════════════════════════

DEMO_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BE Technology — GL Mapping Agent Demo</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Playfair+Display:wght@600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#F8F9FC;--white:#FFFFFF;--navy:#0F1729;--blue:#1A56DB;
  --green:#0A7C42;--amber:#92580A;--red:#C81A1A;
  --border:#E2E8F4;--text2:#3D4D6A;--text3:#7A8BA8;
  --mono:'JetBrains Mono',monospace;--serif:'Playfair Display',serif;
  --sans:'Inter',sans-serif;
}
html{background:var(--bg);color:var(--navy);font-family:var(--sans)}
body{min-height:100vh}
.shell{max-width:860px;margin:0 auto;padding:32px 24px 60px}

/* Header */
.hdr{margin-bottom:32px;padding-bottom:20px;border-bottom:1px solid var(--border)}
.hdr-eye{font-family:var(--mono);font-size:9px;letter-spacing:.16em;
          text-transform:uppercase;color:var(--blue);margin-bottom:6px}
.hdr-title{font-family:var(--serif);font-size:28px;font-weight:700;
            color:var(--navy);line-height:1.2}
.hdr-sub{font-size:13px;color:var(--text2);margin-top:6px;line-height:1.6}

/* Stage indicator */
.stages{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:28px}
.stage{background:var(--white);border:1px solid var(--border);border-radius:8px;
       padding:12px 10px;text-align:center;transition:all .3s}
.stage.active{border-color:var(--blue);background:#EEF3FF}
.stage.done{border-color:#A8D5BA;background:#E8F5EE}
.stage.done .s-icon{color:var(--green)}
.stage.active .s-icon{color:var(--blue)}
.s-icon{font-size:20px;margin-bottom:4px}
.s-label{font-family:var(--mono);font-size:9px;text-transform:uppercase;
          letter-spacing:.06em;color:var(--text3);line-height:1.4}
.stage.active .s-label{color:var(--blue)}
.stage.done .s-label{color:var(--green)}

/* Big launch button */
.launch-wrap{text-align:center;margin-bottom:28px}
.launch-btn{
  display:inline-flex;align-items:center;gap:10px;
  padding:16px 40px;border-radius:8px;border:none;cursor:pointer;
  background:var(--navy);color:#FFFFFF;font-size:15px;font-weight:600;
  font-family:var(--sans);transition:all .2s;
}
.launch-btn:hover{background:#1A2B4A;transform:translateY(-1px);
                   box-shadow:0 4px 20px rgba(15,23,41,0.2)}
.launch-btn:disabled{background:#94A3B8;cursor:not-allowed;transform:none;box-shadow:none}
.launch-btn .btn-icon{font-size:18px}
.reset-btn{
  display:inline-flex;align-items:center;gap:6px;margin-left:12px;
  padding:16px 20px;border-radius:8px;border:1px solid var(--border);
  background:var(--white);color:var(--text2);font-size:13px;
  font-family:var(--sans);cursor:pointer;transition:all .2s;
}
.reset-btn:hover{border-color:var(--navy);color:var(--navy)}

/* Live feed */
.feed-wrap{background:var(--white);border:1px solid var(--border);
           border-radius:10px;overflow:hidden;margin-bottom:24px}
.feed-head{padding:12px 16px;background:#F1F4F9;border-bottom:1px solid var(--border);
           display:flex;align-items:center;justify-content:space-between}
.feed-title{font-family:var(--mono);font-size:10px;letter-spacing:.1em;
             text-transform:uppercase;color:var(--blue)}
.feed-dot{width:7px;height:7px;border-radius:50%;background:#94A3B8}
.feed-dot.live{background:var(--green);animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
.feed-body{padding:16px;min-height:120px;max-height:320px;overflow-y:auto}
.feed-empty{font-family:var(--mono);font-size:11px;color:var(--text3);
             text-align:center;padding:20px}

/* Event rows */
.ev{display:flex;align-items:flex-start;gap:10px;margin-bottom:10px;
    animation:slideIn .3s ease}
@keyframes slideIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.ev-icon{width:28px;height:28px;border-radius:50%;flex-shrink:0;
          display:flex;align-items:center;justify-content:center;font-size:13px}
.ev-icon.info{background:#EEF3FF;color:var(--blue)}
.ev-icon.success{background:#E8F5EE;color:var(--green)}
.ev-icon.warn{background:#FDF3DC;color:var(--amber)}
.ev-icon.agent{background:#F3F0FF;color:#5B34DA}
.ev-body{flex:1}
.ev-title{font-size:13px;font-weight:500;color:var(--navy);line-height:1.4}
.ev-detail{font-family:var(--mono);font-size:10px;color:var(--text3);
            margin-top:2px;line-height:1.5}
.ev-time{font-family:var(--mono);font-size:9px;color:var(--text3);
          flex-shrink:0;margin-top:3px}

/* Decision card */
.decision-card{background:var(--white);border:1px solid var(--border);
               border-left:4px solid var(--green);border-radius:8px;
               padding:16px;margin-bottom:16px;display:none}
.decision-card.visible{display:block;animation:slideIn .4s ease}
.dc-head{display:flex;align-items:center;justify-content:space-between;
          margin-bottom:12px}
.dc-account{font-family:var(--mono);font-size:12px;font-weight:600;color:var(--navy)}
.dc-desc{font-size:14px;font-weight:500;color:var(--navy);margin-top:2px}
.dc-badges{display:flex;gap:6px}
.badge{font-size:9px;font-weight:600;padding:3px 7px;border-radius:3px;
       font-family:var(--mono);white-space:nowrap}
.badge-green{background:#E8F5EE;color:var(--green)}
.badge-blue{background:#EEF3FF;color:var(--blue)}
.badge-amber{background:#FDF3DC;color:var(--amber)}
.dc-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:12px}
.dc-field{background:#F8F9FC;border-radius:6px;padding:8px 10px}
.dc-field-label{font-family:var(--mono);font-size:9px;text-transform:uppercase;
                  letter-spacing:.06em;color:var(--text3);margin-bottom:3px}
.dc-field-val{font-size:12px;font-weight:600;color:var(--navy)}
.dc-reasoning{background:#FFFBF0;border-left:3px solid #C9A84C;
               padding:10px 12px;border-radius:0 6px 6px 0;
               font-size:12px;color:var(--text2);line-height:1.7;margin-bottom:12px}
.dc-actions{display:flex;gap:8px}
.dc-approve{flex:1;padding:10px;background:var(--green);color:#FFFFFF;
             border:none;border-radius:6px;font-weight:600;font-size:13px;
             cursor:pointer;transition:all .15s}
.dc-approve:hover{background:#086835}
.dc-override{padding:10px 16px;background:var(--white);color:var(--navy);
              border:1px solid var(--border);border-radius:6px;font-size:13px;
              cursor:pointer;transition:all .15s}
.dc-override:hover{border-color:var(--navy)}

/* Result panel */
.result-panel{display:none;background:#E8F5EE;border:1px solid #A8D5BA;
               border-radius:10px;padding:20px;text-align:center;margin-bottom:24px}
.result-panel.visible{display:block;animation:slideIn .4s ease}
.result-icon{font-size:40px;margin-bottom:8px}
.result-title{font-family:var(--serif);font-size:20px;font-weight:600;
               color:var(--green);margin-bottom:8px}
.result-detail{font-size:13px;color:var(--text2);line-height:1.7}

/* Audit trail */
.audit-wrap{display:none;background:var(--white);border:1px solid var(--border);
             border-radius:10px;overflow:hidden;margin-bottom:24px}
.audit-wrap.visible{display:block;animation:slideIn .4s ease}
.audit-head{padding:10px 16px;background:#F1F4F9;border-bottom:1px solid var(--border)}
.audit-title{font-family:var(--mono);font-size:10px;letter-spacing:.1em;
              text-transform:uppercase;color:var(--blue)}
.audit-table{width:100%;border-collapse:collapse;font-size:11px}
.audit-table th{padding:8px 12px;text-align:left;font-family:var(--mono);
                 font-size:9px;letter-spacing:.06em;text-transform:uppercase;
                 color:var(--text3);border-bottom:1px solid var(--border)}
.audit-table td{padding:8px 12px;border-bottom:1px solid #F1F4F9;
                 color:var(--text2);font-family:var(--mono)}
.audit-table td.strong{color:var(--navy);font-weight:500}

/* T001 indicator */
.t001-wrap{display:none;background:var(--white);border:1px solid #A8D5BA;
            border-radius:10px;padding:16px 20px;
            display:none;align-items:center;gap:14px}
.t001-wrap.visible{display:flex;animation:slideIn .4s ease}
.t001-orb{width:40px;height:40px;border-radius:50%;background:#E8F5EE;
           border:2px solid #A8D5BA;display:flex;align-items:center;
           justify-content:center;font-size:18px;flex-shrink:0}
.t001-info{}
.t001-label{font-family:var(--mono);font-size:9px;text-transform:uppercase;
             letter-spacing:.08em;color:var(--text3);margin-bottom:3px}
.t001-status{font-size:14px;font-weight:600;color:var(--green)}
.t001-metric{font-family:var(--mono);font-size:11px;color:var(--text2);margin-top:2px}
</style>
</head>
<body>
<div class="shell">

  <!-- Header -->
  <div class="hdr">
    <div class="hdr-eye">BE Technology · GL Intelligence Platform</div>
    <div class="hdr-title">Autonomous GL Mapping Agent</div>
    <div class="hdr-sub">
      Watch the agent detect an unmapped account, reason using ASC 220-40,
      draft a mapping decision, and deliver a one-click approval email —
      all without a human touching a spreadsheet.
    </div>
  </div>

  <!-- Stage indicators -->
  <div class="stages" id="stages">
    <div class="stage" id="stage-0">
      <div class="s-icon">🔍</div>
      <div class="s-label">Detect unmapped account</div>
    </div>
    <div class="stage" id="stage-1">
      <div class="s-icon">🧠</div>
      <div class="s-label">Find similar accounts</div>
    </div>
    <div class="stage" id="stage-2">
      <div class="s-icon">⚡</div>
      <div class="s-label">Claude reasons & drafts</div>
    </div>
    <div class="stage" id="stage-3">
      <div class="s-icon">📧</div>
      <div class="s-label">Email sent to controller</div>
    </div>
    <div class="stage" id="stage-4">
      <div class="s-icon">✓</div>
      <div class="s-label">Approved & promoted</div>
    </div>
  </div>

  <!-- Launch button -->
  <div class="launch-wrap">
    <button class="launch-btn" id="launch-btn" onclick="startDemo()">
      <span class="btn-icon">▶</span>
      Run Live Demo
    </button>
    <button class="reset-btn" onclick="resetDemo()">↺ Reset</button>
  </div>

  <!-- Live event feed -->
  <div class="feed-wrap">
    <div class="feed-head">
      <div class="feed-title">Live Agent Feed</div>
      <div class="feed-dot" id="feed-dot"></div>
    </div>
    <div class="feed-body" id="feed-body">
      <div class="feed-empty">Click "Run Live Demo" to start</div>
    </div>
  </div>

  <!-- Decision card (shown after agent drafts) -->
  <div class="decision-card" id="decision-card">
    <div class="dc-head">
      <div>
        <div class="dc-account" id="dc-account"></div>
        <div class="dc-desc" id="dc-desc"></div>
      </div>
      <div class="dc-badges">
        <span class="badge badge-green" id="dc-conf"></span>
        <span class="badge badge-amber" id="dc-mat"></span>
      </div>
    </div>
    <div class="dc-grid">
      <div class="dc-field">
        <div class="dc-field-label">DISE Category</div>
        <div class="dc-field-val" id="dc-cat"></div>
      </div>
      <div class="dc-field">
        <div class="dc-field-label">IS Caption</div>
        <div class="dc-field-val" id="dc-caption"></div>
      </div>
      <div class="dc-field">
        <div class="dc-field-label">ASC Citation</div>
        <div class="dc-field-val" id="dc-cite"></div>
      </div>
    </div>
    <div class="dc-reasoning" id="dc-reasoning"></div>
    <div class="dc-actions">
      <button class="dc-approve" onclick="approveFromDemo()">
        ✓ Approve Decision
      </button>
      <button class="dc-override" onclick="window.open('/override/0000640090','_blank')">
        ✎ Override
      </button>
    </div>
  </div>

  <!-- Result panel -->
  <div class="result-panel" id="result-panel">
    <div class="result-icon">✓</div>
    <div class="result-title">Mapping Approved & Promoted</div>
    <div class="result-detail" id="result-detail"></div>
  </div>

  <!-- Audit trail -->
  <div class="audit-wrap" id="audit-wrap">
    <div class="audit-head">
      <div class="audit-title">Audit Trail — mapping_decisions_log</div>
    </div>
    <table class="audit-table">
      <thead>
        <tr>
          <th>Event</th><th>GL Account</th><th>Agent Decision</th>
          <th>Human Agreed</th><th>Actor</th><th>Timestamp</th>
        </tr>
      </thead>
      <tbody id="audit-tbody"></tbody>
    </table>
  </div>

  <!-- T001 status -->
  <div class="t001-wrap" id="t001-wrap">
    <div class="t001-orb">✓</div>
    <div class="t001-info">
      <div class="t001-label">T001 · Close Tracker</div>
      <div class="t001-status" id="t001-status">Loading...</div>
      <div class="t001-metric" id="t001-metric"></div>
    </div>
  </div>

</div>

<script>
let currentDecision = null;
let eventSource = null;

function addEvent(icon, iconClass, title, detail, time) {
  const feed = document.getElementById('feed-body');
  const empty = feed.querySelector('.feed-empty');
  if (empty) empty.remove();

  const now = time || new Date().toLocaleTimeString('en-US', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
  const ev = document.createElement('div');
  ev.className = 'ev';
  ev.innerHTML = `
    <div class="ev-icon ${iconClass}">${icon}</div>
    <div class="ev-body">
      <div class="ev-title">${title}</div>
      ${detail ? `<div class="ev-detail">${detail}</div>` : ''}
    </div>
    <div class="ev-time">${now}</div>`;
  feed.appendChild(ev);
  feed.scrollTop = feed.scrollHeight;
}

function setStage(n, done=false) {
  for (let i = 0; i < 5; i++) {
    const el = document.getElementById(`stage-${i}`);
    el.classList.remove('active','done');
    if (i < n || (done && i <= n)) el.classList.add('done');
    else if (i === n) el.classList.add('active');
  }
}

async function startDemo() {
  document.getElementById('launch-btn').disabled = true;
  document.getElementById('feed-dot').classList.add('live');
  document.getElementById('decision-card').classList.remove('visible');
  document.getElementById('result-panel').classList.remove('visible');
  document.getElementById('audit-wrap').classList.remove('visible');
  document.getElementById('t001-wrap').classList.remove('visible');

  try {
    // Stage 0 — detect
    setStage(0);
    addEvent('🔍','info','Scanning for unmapped GL accounts...',
      'Querying CORTEX_SAP_CDC.bkpf / bseg vs gl_dise_mapping');
    await sleep(1200);

    const detectRes = await fetch('/demo/detect', {method:'POST'});
    const detected  = await detectRes.json();

    addEvent('⚠️','warn',
      `Unmapped account detected — ${detected.gl_account}`,
      `${detected.description} · $${Number(detected.posting_amount).toLocaleString()} · ${detected.materiality_flag} materiality`);
    await sleep(800);

    // Stage 1 — similarity
    setStage(1);
    addEvent('🔎','info','Finding similar approved accounts...',
      'Jaccard similarity search across 86 approved mappings');
    await sleep(1000);

    const simRes  = await fetch('/demo/similar', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({description: detected.description})
    });
    const similar = await simRes.json();

    similar.slice(0,3).forEach(s => {
      addEvent('📎','info',
        `Reference: ${s.description}`,
        `${s.dise_category} · ${s.expense_caption} · similarity ${s.similarity_score}`);
    });
    await sleep(600);

    // Stage 2 — Claude
    setStage(2);
    addEvent('⚡','agent','Claude reasoning with ASC 220-40 context...',
      `Model: ${detected.model_version || 'claude-sonnet-4-20250514'} · Prompt v1.0`);

    const agentRes  = await fetch('/demo/agent', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account: detected, similar})
    });
    const decision  = await agentRes.json();
    currentDecision = decision;

    addEvent('✓','success',
      `Decision: ${decision.suggested_category} · ${decision.suggested_caption}`,
      `${decision.suggested_citation} · ${decision.confidence_label} confidence ${Math.round(decision.confidence_score*100)}%`);
    await sleep(400);

    // Show decision card
    document.getElementById('dc-account').textContent  = detected.gl_account;
    document.getElementById('dc-desc').textContent     = detected.description;
    document.getElementById('dc-cat').textContent      = decision.suggested_category;
    document.getElementById('dc-caption').textContent  = decision.suggested_caption;
    document.getElementById('dc-cite').textContent     = decision.suggested_citation;
    document.getElementById('dc-conf').textContent     = `${decision.confidence_label} ${Math.round(decision.confidence_score*100)}%`;
    document.getElementById('dc-mat').textContent      = `${detected.materiality_flag} MATERIALITY`;
    document.getElementById('dc-reasoning').textContent= decision.draft_reasoning;
    document.getElementById('decision-card').classList.add('visible');

    // Stage 3 — email
    setStage(3);
    const emailRes = await fetch('/demo/email', {method:'POST'});
    const emailResult = await emailRes.json();

    addEvent('📧','info',
      `Approval email sent to ${emailResult.to}`,
      `Subject: ${emailResult.subject}`);

    addEvent('⏳','info','Waiting for controller approval...',
      'Click "Approve Decision" above or approve via email');

  } catch(e) {
    addEvent('❌','warn', 'Error: ' + e.message, 'Check Cloud Shell logs');
    document.getElementById('launch-btn').disabled = false;
    document.getElementById('feed-dot').classList.remove('live');
  }
}

async function approveFromDemo() {
  if (!currentDecision) return;

  document.querySelector('.dc-approve').disabled = true;
  document.querySelector('.dc-approve').textContent = 'Processing...';

  const res    = await fetch('/approve/0000640090');
  const result = await res.json();

  setStage(4, true);
  addEvent('✓','success','Account approved and promoted to gl_dise_mapping',
    `${currentDecision.suggested_category} · ${currentDecision.suggested_caption} · reviewer: mr@betechnology.org`);

  addEvent('📋','success','Audit log written — mapping_decisions_log',
    'event_type: HUMAN_APPROVED · human_agreed: true · immutable record created');

  document.getElementById('decision-card').classList.remove('visible');

  document.getElementById('result-panel').classList.add('visible');
  document.getElementById('result-detail').innerHTML =
    `GL account <strong>0000640090</strong> mapped as 
     <strong>${currentDecision.suggested_category}</strong> · ${currentDecision.suggested_caption}<br>
     ASC citation: ${currentDecision.suggested_citation} · Reviewer: mr@betechnology.org<br>
     Audit trail complete · gl_dise_mapping updated · T001 checking...`;

  // Load audit trail
  await sleep(600);
  const auditRes = await fetch('/demo/audit');
  const audit    = await auditRes.json();
  const tbody    = document.getElementById('audit-tbody');
  tbody.innerHTML = audit.map(r => `
    <tr>
      <td class="strong">${r.event_type}</td>
      <td style="font-family:var(--mono)">${r.gl_account}</td>
      <td>${r.final_category || r.agent_category}</td>
      <td style="color:${r.human_agreed?'var(--green)':'var(--amber)'}">${r.human_agreed?'✓ Yes':'✗ No'}</td>
      <td>${r.actor}</td>
      <td style="color:var(--text3)">${new Date(r.event_timestamp).toLocaleTimeString()}</td>
    </tr>`).join('');
  document.getElementById('audit-wrap').classList.add('visible');

  // Load T001
  await sleep(400);
  const t001Res = await fetch('/demo/t001');
  const t001    = await t001Res.json();
  document.getElementById('t001-status').textContent = t001.is_complete ? '✓ Complete — T001 Green' : 'Open';
  document.getElementById('t001-metric').textContent  = t001.metric_value || '';
  document.getElementById('t001-wrap').classList.add('visible');

  if (t001.is_complete) {
    addEvent('✓','success','T001 auto-updated — Close tracker green',
      t001.metric_value);
  }

  document.getElementById('feed-dot').classList.remove('live');
}

async function resetDemo() {
  await fetch('/demo/reset', {method:'POST'});
  document.getElementById('feed-body').innerHTML = '<div class="feed-empty">Click "Run Live Demo" to start</div>';
  document.getElementById('decision-card').classList.remove('visible');
  document.getElementById('result-panel').classList.remove('visible');
  document.getElementById('audit-wrap').classList.remove('visible');
  document.getElementById('t001-wrap').classList.remove('visible');
  document.getElementById('launch-btn').disabled = false;
  document.getElementById('feed-dot').classList.remove('live');
  for (let i=0;i<5;i++) {
    const el = document.getElementById(`stage-${i}`);
    el.classList.remove('active','done');
  }
  currentDecision = null;
}

function sleep(ms){ return new Promise(r=>setTimeout(r,ms)) }
</script>
</body>
</html>'''


# ══════════════════════════════════════════════════════════════
# FLASK ROUTES
# ══════════════════════════════════════════════════════════════

@app.route('/demo')
def demo_page():
    return DEMO_HTML


@app.route('/demo/detect', methods=['POST'])
def demo_detect():
    """Stage 0 — inject and return the demo account."""
    # Clean up any previous demo run
    for table in ['pending_mappings']:
        try:
            bq.query(f"DELETE FROM `{PROJECT}.{DATASET}.{table}` WHERE gl_account='0000640090'").result()
        except:
            pass
    try:
        bq.query(f"DELETE FROM `{PROJECT}.{DATASET}.gl_dise_mapping` WHERE gl_account='0000640090'").result()
    except:
        pass

    account = dict(DEMO_ACCOUNT)
    account['materiality_flag'] = 'MEDIUM'
    account['model_version']    = MODEL
    return jsonify(account)


@app.route('/demo/similar', methods=['POST'])
def demo_similar():
    """Stage 1 — find similar approved accounts."""
    description = request.json.get('description', '')
    sql = f"""
    WITH
    test_words AS (
      SELECT DISTINCT word
      FROM UNNEST(SPLIT(LOWER(REGEXP_REPLACE(@desc, r'[-/&,.]', ' ')), ' ')) AS word
      WHERE LENGTH(TRIM(word)) > 2
    ),
    approved_tokens AS (
      SELECT gl_account, description, dise_category, expense_caption, asc_citation,
             LOWER(REGEXP_REPLACE(description, r'[-/&,.]', ' ')) AS desc_clean
      FROM `{PROJECT}.{DATASET}.gl_dise_mapping`
      WHERE status='mapped' AND description IS NOT NULL
    ),
    test_word_count AS (SELECT COUNT(DISTINCT word) AS cnt FROM test_words),
    scored AS (
      SELECT a.gl_account, a.description, a.dise_category, a.expense_caption,
             a.asc_citation, a.desc_clean,
             COUNT(DISTINCT t.word) AS matching_words,
             MAX(twc.cnt) AS test_word_cnt,
             ARRAY_LENGTH(SPLIT(TRIM(REGEXP_REPLACE(a.desc_clean, r'\\s+', ' ')), ' ')) AS account_word_cnt
      FROM approved_tokens a CROSS JOIN test_words t CROSS JOIN test_word_count twc
      WHERE STRPOS(a.desc_clean, t.word) > 0
      GROUP BY 1,2,3,4,5,6
    )
    SELECT gl_account, description, dise_category, expense_caption, asc_citation,
           ROUND(matching_words/(test_word_cnt+account_word_cnt-matching_words),3) AS similarity_score
    FROM scored WHERE matching_words > 0
    ORDER BY similarity_score DESC LIMIT 5
    """
    rows = list(bq.query(sql, job_config=bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter('desc','STRING',description)]
    )).result())
    return jsonify([dict(r) for r in rows])


@app.route('/demo/agent', methods=['POST'])
def demo_agent():
    """Stage 2 — call Claude to draft the mapping decision."""
    data    = request.json
    account = data['account']
    similar = data['similar']

    similar_text = "\n\nSIMILAR APPROVED ACCOUNTS:\n"
    for i, s in enumerate(similar[:3], 1):
        similar_text += (f"{i}. GL {s['gl_account']} — \"{s['description']}\"\n"
                        f"   Category: {s['dise_category']} | Caption: {s['expense_caption']}\n"
                        f"   Citation: {s['asc_citation']} | Similarity: {s['similarity_score']}\n")

    system = """You are the GL Mapping Agent for BE Technology. Classify GL accounts into ASC 220-40 DISE categories.
Five categories: Purchases of inventory (ASC 220-40-50-6(b)), Employee compensation (ASC 220-40-50-6(a)),
Depreciation (ASC 220-40-50-6(c)) — tangible assets only, Intangible asset amortization (ASC 220-40-50-6(d)),
Other expenses (ASC 220-40-50-6(e)). Respond ONLY with raw JSON, no markdown."""

    prompt = f"""Classify: GL {account['gl_account']} — "{account['description']}" — ${float(account['posting_amount']):,.0f}
{similar_text}
Return JSON: {{"suggested_category":"...","suggested_caption":"...","suggested_citation":"...","confidence_score":0.0,"confidence_label":"HIGH|MEDIUM|LOW","draft_reasoning":"..."}}"""

    response = claude.messages.create(model=MODEL, max_tokens=500,
                                       system=system,
                                       messages=[{'role':'user','content':prompt}])
    raw = response.content[0].text.strip()
    if raw.startswith('```'):
        raw = raw.split('```')[1]
        if raw.startswith('json'): raw = raw[4:]

    decision = json.loads(raw.strip())

    # Write to pending_mappings
    row = {
        'gl_account': account['gl_account'], 'description': account['description'],
        'posting_amount': float(account['posting_amount']),
        'fiscal_year': '2023', 'company_code': 'C006',
        'suggested_category': decision['suggested_category'],
        'suggested_caption':  decision['suggested_caption'],
        'suggested_citation': decision['suggested_citation'],
        'draft_reasoning':    decision['draft_reasoning'],
        'confidence_score':   float(decision['confidence_score']),
        'confidence_label':   decision['confidence_label'],
        'similar_accounts':   json.dumps(similar[:3]),
        'materiality_flag':   'MEDIUM', 'status': 'PENDING',
        'drafted_by': AGENT_ID, 'drafted_at': datetime.now(timezone.utc).isoformat(),
        'model_version': MODEL, 'prompt_version': 'v1.0',
    }
    bq.insert_rows_json(f'{PROJECT}.{DATASET}.pending_mappings', [row])

    # Write agent draft to audit log
    bq.insert_rows_json(f'{PROJECT}.{DATASET}.mapping_decisions_log', [{
        'event_id': str(uuid.uuid4()), 'event_type': 'AGENT_DRAFT',
        'event_timestamp': datetime.now(timezone.utc).isoformat(),
        'gl_account': account['gl_account'], 'description': account['description'],
        'fiscal_year': '2023', 'company_code': 'C006',
        'posting_amount': float(account['posting_amount']),
        'agent_category': decision['suggested_category'],
        'agent_caption':  decision['suggested_caption'],
        'agent_citation': decision['suggested_citation'],
        'agent_confidence': float(decision['confidence_score']),
        'agent_reasoning':  decision['draft_reasoning'],
        'actor': AGENT_ID, 'actor_type': 'AGENT',
        'model_version': MODEL, 'prompt_version': 'v1.0',
    }])

    return jsonify(decision)


@app.route('/demo/email', methods=['POST'])
def demo_email():
    """Stage 3 — send approval email."""
    from approval_system import get_gmail_service, build_email_html
    decisions = list(bq.query(
        f"SELECT * FROM `{PROJECT}.{DATASET}.pending_mappings` WHERE status='PENDING' AND gl_account='0000640090'"
    ).result())

    if not decisions:
        return jsonify({'error': 'No pending decisions'}), 400

    decisions_dict = [dict(d) for d in decisions]
    service  = get_gmail_service()
    html     = build_email_html(decisions_dict)
    subject  = f"[GL Intelligence] 1 GL account requires review — $387,500 · Company C006 FY2023"

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = FROM_EMAIL
    msg['To']      = TO_EMAIL
    msg.attach(MIMEText(html, 'html'))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId='me', body={'raw': raw}).execute()

    return jsonify({'to': TO_EMAIL, 'subject': subject})


@app.route('/approve/<gl_account>')
def approve(gl_account):
    """Process approval — called from demo page or email button."""
    from approval_system import promote_to_gl_mapping
    success = promote_to_gl_mapping(gl_account, TO_EMAIL)
    if request.headers.get('Accept','').startswith('application/json') or request.args.get('json'):
        return jsonify({'success': success, 'gl_account': gl_account})
    # Email click — show confirmation page
    return f"""<html><body style="font-family:Inter,sans-serif;text-align:center;padding:60px;background:#F8F9FC">
      <div style="background:#E8F5EE;border:1px solid #A8D5BA;border-radius:10px;
                  padding:30px;max-width:400px;margin:0 auto">
        <div style="font-size:40px">✓</div>
        <div style="font-size:20px;font-weight:600;color:#0A7C42;margin:10px 0">Approved</div>
        <div style="font-size:13px;color:#1E293B">
          GL account <strong>{gl_account}</strong> has been mapped and added to gl_dise_mapping.<br>
          Audit log updated. You can close this tab.
        </div>
      </div></body></html>"""


@app.route('/override/<gl_account>', methods=['GET','POST'])
def override(gl_account):
    if request.method == 'GET':
        return f"""<html><body style="font-family:Inter,sans-serif;padding:40px;background:#F8F9FC;max-width:500px;margin:0 auto">
          <h2 style="color:#0F1729;margin-bottom:20px">Override: {gl_account}</h2>
          <form method="POST">
            <div style="margin-bottom:14px">
              <label style="font-weight:600;display:block;margin-bottom:4px;font-size:13px">DISE Category</label>
              <select name="category" style="width:100%;padding:8px;border-radius:4px;border:1px solid #C8D3E8;font-size:13px">
                <option>Purchases of inventory</option><option>Employee compensation</option>
                <option>Depreciation</option><option>Intangible asset amortization</option>
                <option>Other expenses</option>
              </select></div>
            <div style="margin-bottom:14px">
              <label style="font-weight:600;display:block;margin-bottom:4px;font-size:13px">Caption</label>
              <select name="caption" style="width:100%;padding:8px;border-radius:4px;border:1px solid #C8D3E8;font-size:13px">
                <option>COGS</option><option>SG&A</option><option>R&D</option><option>Other income/expense</option>
              </select></div>
            <div style="margin-bottom:14px">
              <label style="font-weight:600;display:block;margin-bottom:4px;font-size:13px">ASC Citation</label>
              <input name="citation" placeholder="e.g. ASC 220-40-50-6(c)"
                     style="width:100%;padding:8px;border-radius:4px;border:1px solid #C8D3E8;font-size:13px"></div>
            <div style="margin-bottom:20px">
              <label style="font-weight:600;display:block;margin-bottom:4px;font-size:13px">Override reason</label>
              <textarea name="reason" rows="3" required
                        style="width:100%;padding:8px;border-radius:4px;border:1px solid #C8D3E8;font-size:13px"></textarea></div>
            <button type="submit" style="background:#0F2044;color:#FFF;padding:10px 24px;border:none;
                                          border-radius:6px;font-size:14px;cursor:pointer">Submit Override</button>
          </form></body></html>"""
    from approval_system import promote_to_gl_mapping
    promote_to_gl_mapping(gl_account, TO_EMAIL, override={
        'category': request.form.get('category'),
        'caption':  request.form.get('caption'),
        'citation': request.form.get('citation'),
        'reason':   request.form.get('reason'),
    })
    return "<html><body style='font-family:Inter,sans-serif;text-align:center;padding:60px'>Override recorded. Close this tab.</body></html>"


@app.route('/demo/audit')
def demo_audit():
    rows = list(bq.query(
        f"SELECT event_type, gl_account, agent_category, final_category, human_agreed, actor, event_timestamp "
        f"FROM `{PROJECT}.{DATASET}.mapping_decisions_log` "
        f"WHERE gl_account='0000640090' ORDER BY event_timestamp DESC LIMIT 5"
    ).result())
    return jsonify([dict(r) for r in rows])


@app.route('/demo/t001')
def demo_t001():
    rows = list(bq.query(
        f"SELECT task_id, is_complete, metric_value FROM `{PROJECT}.{DATASET}.close_tasks` WHERE task_id='T001'"
    ).result())
    return jsonify(dict(rows[0]) if rows else {})


@app.route('/demo/reset', methods=['POST'])
def demo_reset():
    for q in [
        f"DELETE FROM `{PROJECT}.{DATASET}.pending_mappings` WHERE gl_account='0000640090'",
        f"DELETE FROM `{PROJECT}.{DATASET}.gl_dise_mapping` WHERE gl_account='0000640090'",
        f"DELETE FROM `{PROJECT}.{DATASET}.mapping_decisions_log` WHERE gl_account='0000640090'",
    ]:
        try: bq.query(q).result()
        except: pass
    return jsonify({'reset': True})


@app.route('/status')
def status():
    return jsonify({'server': 'running', 'project': PROJECT})


if __name__ == '__main__':
    log.info(f"Demo controller starting on port 8080")
    log.info(f"Open: {APPROVAL_BASE}/demo")
    app.run(host='0.0.0.0', port=8080, debug=False)
