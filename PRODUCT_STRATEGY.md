# BL Intelligence — Product Strategy

> Last updated: 2026-05-02
>
> Source research: see Plan agent brief in `~/.claude/plans/woolly-petting-journal.md`
> and the WebSearch citations in this conversation. Refresh quarterly.

---

## TL;DR

**What it is**: an AI-agent platform that ingests GL data, classifies accounts
into FASB ASU disclosure categories with full audit trail, and outputs
10-K-ready footnotes and the supporting workpapers.

**Who it's for**: VP Tax / Tax Director and Corporate Controllers at
**$1B–$10B-revenue US public filers** on SAP ECC/S4 or Oracle EBS/Fusion,
multi-jurisdictional (3+ tax jurisdictions, 5+ legal entities).

**The wedge**: GL-account-level intelligence with reproducible, auditor-
defensible reasoning + multi-ERP ingestion + faster time-to-first-disclosure
(weeks, not months). **The audit trail is the product, not a feature.**

**Lead with DISE (ASU 2024-03)**, not ASU 2023-09 — Bloomberg Tax already
shipped a 2023-09 rate-rec module in Aug 2025; that wave has broken. DISE
becomes effective FY2027 (calendar) and budgets are forming **right now**.
**Bundle 2023-09 as a fast-follow** because the buyer overlaps.

**v1 ACV**: $75–150K (mid-cap), $250–400K ($5B+). Per legal entity + per
jurisdiction. **Avoid per-disclosure pricing** — boxes you in as DISE expands.

**Go-to-market**: Paid pilot ($25–50K) on customer's CY2025 actuals → 4-week
output of (a) DISE pivot + draft footnote and (b) ASU 2023-09 rate-rec table.
**Conversion 40–60%** vs. <5% on self-serve trials.

---

## Buyer persona & ICP

### Primary buyer
**VP Tax / Tax Director** at $1B–$10B-revenue PBE.
- Owns budget for tax-provision tools (~$150–500K signable below CFO).
- Has the calendar pain (10-K + 10-Q signoff).
- Will involve IT/Finance Transformation + InfoSec for SAP/Oracle access.
- 6–9 month first-deal cycle, compressing to 3–4 once you have logos.
- CFO sign-off above ~$250K.

### Secondary buyer
**Corporate Controller** for the DISE module.
- DISE is a controllership disclosure (under ASC 220-40), not tax.
- This matters for go-to-market: leading the DISE pitch through a tax
  director will misfire — go directly to the controller, with the tax
  director as expansion.

### Where to NOT sell (yet)
- **<$1B revenue**: cope with Excel + Big-4 outsource, won't pay six figures.
- **>$10B revenue**: entrenched in OneSource/CCH Tagetik with seven-figure
  multi-year contracts; CIO-led RFPs; multi-year migration risk. Not a v1
  buyer. Revisit once you have 5+ logos.

### Geography
**US public filers** (SEC). UK/EU equivalents (IFRS, S-1 SOX-like regimes)
are out of scope until v2.

### Urgency calendar
- **ASU 2023-09 (Income Tax)** — already effective for **CY 2025 PBEs**;
  10-Ks filing Q1 2026 (right now). **Wave has broken** — Bloomberg Tax
  shipped a built-in rate-rec product Aug 2025; OneSource and CCH followed.
  → **Don't lead with this**; bundle as fast-follow or displacement.
- **ASU 2024-03 (DISE)** — effective annual periods after Dec 15, 2026
  (FY2027 calendar filers); interim 2028. PBEs in **scoping/data-gap-
  assessment mode RIGHT NOW** (Q2-Q3 2026). **Lead here.**

---

## Incumbent landscape

### Established platforms (defend on)

| Vendor | Strength | Gap | List price |
|---|---|---|---|
| **Workiva** (NYSE: WK, $7B mcap) | XBRL, 10-K assembly, Wdesk audit trail | Not a calc engine — depends on tax provision feeding it. AI is doc-level, not GL-level | $60K avg, $100–300K mid-cap, $1M+ F100 |
| **Bloomberg Tax Provision** | Built-in 2023-09 rate-rec (Aug 2025); deep tax-law DB | Tax-only; no DISE; no controller workflow | Quote, ~$75–200K |
| **Thomson Reuters ONESOURCE** | Most complete tax suite; SAP cert | Heavy implementation; per-entity pricing balloons; rigid templates | $200K–$1M+ |
| **CCH Tagetik (Wolters Kluwer)** | CPM consolidation; enterprise | Tax-provision module is new (2024); enterprise-only | $300K+ |
| **BlackLine / Trintech** | Account recon, close orchestration | No disclosure generation | $100–500K |
| **Auditboard** | SOX/controls-evidence; internal audit | Complementary not competitive — feed audit log INTO it | $50–150K |

### AI-native challengers (attack from below)

| Vendor | Wedge | Their frontier |
|---|---|---|
| **Numeric** ($51M Series B, Nov 2025) | Close-management → "compound" finance platform | Close orchestration; not in PBE tax-disclosure |
| **Trullion** (FSV launched 2025) | AI for lease/rev-rec/audit | Lease-first; not GL-classification-first |
| **Concourse** | Zero-day close | Close speed; not disclosure |
| **Truewind** | SMB/startup books | Below our ICP |

**None of them play in PBE tax-disclosure today.** Their wedge is "AI agents
replace junior accountant labor in close" — that's a different problem from
"AI classifies GL accounts for FASB disclosure with audit defensibility."
**That gap is your opening.**

### Don't compete on
- 10-K assembly / XBRL formatting → **Workiva moat**.
- Tax-law content / editorial → **Bloomberg / CCH** decades of editorial.
- SOX evidence framework → **Auditboard**.
- Close orchestration → **BlackLine**.

**Bad framing**: "Workiva but AI" — you'll lose.
**Right framing**: "the AI classification engine that feeds Workiva" —
output formatted JSON + Word + Excel that drops into the customer's
existing 10-K pipeline.

---

## The wedge — what BL Intelligence wins on

### 1. GL-account-level intelligence
Incumbents map COA via static rules; you classify with **agents that
explain reasoning, cite ASC sections deterministically, and learn from
controller corrections**.

### 2. Multi-ERP ingestion in one tenant
SAP + Oracle + Salesforce + finance-datasets — incumbents mostly assume
one source-of-truth. Real customers have post-M&A entities on different
ERPs.

### 3. DISE-first
A category nobody has shipped a real product for yet. Bloomberg/OneSource
are tax-org tools; DISE is a controllership disclosure. **First-mover
window: roughly 12 months.**

### 4. Time-to-first-disclosure
- BL Intelligence pilot: **4 weeks** to a draft footnote.
- OneSource implementation: **6+ months**.
- Workiva onboarding: 3+ months.

### 5. Auditor-defensible AI
Every classification has:
- Source GL ID
- Reproducible prompt + model version
- Frozen model snapshot per close
- Human reviewer signoff (controller / reviewer / cfo)
- Append-only audit log (`audit_log` table, blocked from UPDATE/DELETE
  via DB trigger)

This is exactly what PCAOB inspection priorities (2025-2026, GenAI-focused)
expect to see for ICFR.

---

## What v1 must do (vs. defer)

### v1 — minimum credible offering for first paying customer
1. SAP + finance-datasets ingest (Oracle in v1.5 if a paying customer
   demands it).
2. ASU 2023-09 rate-rec auto-population with controller review,
   jurisdictional disagg, cash-tax-paid (already 95% built in legacy
   `gl_intelligence/agents/tax_agent.py`).
3. **DISE natural-category classifier** on a real expense caption with
   confidence scores + audit trail.
4. Export to Workiva (CSV/JSON), Word, Excel.
5. **SOC 2 Type II + immutable agent-action log.**
6. Single-tenant Supabase per customer (RLS already enforced; multi-tenant
   from day 1 architecturally — just don't sell shared-tenant in v1).

### Defer to v2 / v3
- Segment reporting (ASU 2023-07) — can be sold but DISE comes first.
- Lease accounting (ASC 842) — Trullion will defend this; not a v1 fight.
- XBRL US GAAP tagging — buyer accepts CSV+Word for v1; v2 plays here.
- Multi-tenant auditor portal (Big-4 access) — the moment you have 3+
  customers, this becomes table stakes. Not before.
- Self-serve trial — never. This is a buy-on-data, not a try-it product.

### Demo-to-deal path
**Paid pilot, $25–50K, 4 weeks**:
1. Customer ships a CY2025 trial balance + chart of accounts.
2. We load via `infra/load_finance_datasets.py` (or a custom SAP extract
   for live customers).
3. Agent classifies; controller reviews via the Next.js dashboard.
4. We deliver: (a) DISE pivot + draft footnote, (b) ASU 2023-09 rate-rec
   table + cash-tax-paid disaggregation, (c) audit log export for their
   external auditor.
5. They compare to their own internal numbers. If we tie within 1%, we
   convert to annual. If we don't, we do a root-cause analysis (usually
   chart-of-account mapping issues we then fix and push to v2).

**Conversion target: 50%.** Pilots that don't tie → fix, retry, learn.
Pilots that tie → annual at 5–10× the pilot fee.

---

## Pricing benchmarks

| Tier | Vendor | Price | What's included |
|---|---|---|---|
| **Floor** | Workiva | $60K avg, $100–300K mid-cap | XBRL + 10-K assembly only |
| **AI-native challenger** | Numeric, Trullion | Custom-quoted, per-entity + transaction volume | Close + AI |
| **BL Intelligence v1** | (us) | **$75–150K mid-cap, $250–400K $5B+** | DISE + 2023-09 + audit log + 1 ERP |
| **Tax-only enterprise** | Bloomberg / OneSource / CCH | $75K–$1M+ | Provision module |
| **Suite** | OneSource Tax+Workiva+Auditboard combined | $500K–$2M+ | Everything but disjoint |

**Pricing unit**: per legal entity + per jurisdiction. Not per disclosure
(boxes you in). Not per user (customer wants their whole tax team to log
in). **Pilot $25–50K → annual $75–150K** is the v1 contract shape.

---

## Risk / disqualifying objections

### Big-4 stance on AI-generated disclosures
- **PwC** ($1.5B AI investment, 2025), **EY**, **Deloitte (Omnia)**,
  **KPMG (Clara)** all use AI internally.
- The CAQ/PCAOB position (Sept 2025) is **"humans remain responsible"** —
  auditors will accept AI-classified outputs *if* every classification has
  reproducible reason, source GL ID, and human reviewer signoff.
- **Mitigation**: our `audit_log` table + RLS-enforced reviewer assignment
  + immutable trigger blocks UPDATE/DELETE. Frozen model versions per
  close. ITGCs over the prompt versioning.

### SOX / PCAOB 2025-2026 inspection priorities
- Explicitly include **GenAI use in ICFR**.
- Need ITGCs over the model: deterministic prompt versioning, frozen
  model versions per close, evidence of human-in-the-loop, change-
  management for prompts.
- **Mitigation**: `prompt_version` + `model_version` in every audit_log
  row + every approved mapping. Our migration freezes these as NOT NULL.

### SEC rulemaking risk
- Low for ASU 2024-03 (FASB rule, already final).
- **XBRL DISE Taxonomy Implementation Guide** was in comment July-Sept
  2025 — taxonomy may shift but core categories won't. v2 problem.

### Bad strategies to avoid
1. ❌ Competing with Workiva on report formatting (they'll defend).
2. ❌ Selling self-serve to tax directors (they don't buy that way).
3. ❌ Leading with 2023-09 in 2026 (wave broke; Bloomberg already shipped).
4. ❌ Pricing per-disclosure.
5. ❌ Salesforce GL connector in v1 (Salesforce isn't a GL system for
   SEC filers — it's a sub-ledger; SAP/Oracle is where the money lives).

---

## Implications for the codebase

The product strategy directly shapes priorities:

1. **DISE module ships before Tax module** — flipped from the original
   plan. Tax module is largely retrofit of legacy `gl_intelligence/`;
   DISE is the differentiator.
2. **Audit log is the product** — already shipped (append-only with
   trigger; nightly BQ export). Surface this aggressively in the UI.
3. **Multi-ERP from day 1** — finance-datasets ingestion (done) +
   `api/src/db/cortex.py` BigQuery client (ready) + Oracle in v1.5.
4. **Workiva integration > XBRL generation** — output JSON + CSV +
   Word, not native XBRL, until v2.
5. **No multi-tenant ops in v1** — single-tenant Supabase project per
   customer (we already have one for the demo: `uljbbwfnldikdathtkbh`).
   Multi-tenant RLS code path is there architecturally; don't sell it.
6. **The pilot is the demo is the product** — keep
   `infra/load_finance_datasets.py` as the canonical "load a customer's
   trial balance" path. Replace with SAP extract per-customer when they
   have a real ERP feed.

---

## Sources

- [KPMG: DISE handbook](https://kpmg.com/us/en/frv/reference-library/2025/disaggregation-income-statement-expenses.html)
- [Deloitte: ASU 2024-03 FAQ (Dec 2025)](https://dart.deloitte.com/USDART/home/publications/deloitte/accounting-spotlight/2025/asu-2024-03-faq-disaggregation-income-statement-expense)
- [PwC Viewpoint: 3.11 DISE](https://viewpoint.pwc.com/dt/us/en/pwc/accounting_guides/financial_statement_/financial_statement___18_US/chapter_3_income_sta_US/311_disaggregation_of.html)
- [EY: DISE detailed guide (July 2025)](https://www.ey.com/content/dam/ey-unified-site/ey-com/en-us/technical/accountinglink/documents/ey-frd27503-251us-07-09-2025.pdf)
- [Deloitte: ASU 2023-09 disclosure considerations](https://dart.deloitte.com/USDART/home/publications/deloitte/heads-up/2025/income-tax-disclosure-considerations-related-adoption-asu-2023-09)
- [Bloomberg Tax: built-in 2023-09 rate-rec (Aug 2025)](https://www.prnewswire.com/news-releases/bloomberg-tax-the-only-provision-software-now-with-built-in-asu-2023-09-rate-reconciliation-302523249.html)
- [Wolters Kluwer: CCH Tagetik Tax Provision (2024)](https://www.wolterskluwer.com/en/news/pr-2024-wolters-kluwer-launches-cch-tagetik-tax-provision-and-reporting-solution)
- [Numeric Series B announcement (Nov 2025)](https://www.prnewswire.com/news-releases/numeric-raises-51m-series-b-expanding-from-close-management-to-comprehensive-finance-platform-302619774.html)
- [Trullion AI accounting platform](https://trullion.com/)
- [Workiva pricing benchmarks (Vendr 2025)](https://www.vendr.com/buyer-guides/workiva)
- [PCAOB inspection priorities 2025](https://pcaobus.org/oversight/standards/auditing-standards)
- [FASB DISE Taxonomy Implementation Guide (July 2025)](https://xbrl.fasb.org/impguidance/DISE_TIG/Proposed%20Taxonomy%20Implementation%20Guide%20Disaggregation%20of%20Income%20Statement%20Expenses%20Subtopic%20220-40.pdf)
