import { useState, useMemo, useCallback, useEffect } from "react";

const DISE_CATEGORIES = [
  {
    id: "inventory",
    label: "Purchases of Inventory",
    code: "ASC 330",
    color: "#16A34A",
    bg: "#DCFCE7",
    border: "#86EFAC",
    description: "Costs to acquire raw materials or finished goods from third parties. Includes freight-in, tariffs, sales taxes per ASC 330-10-30-1.",
    keywords: ["inventory", "raw material", "purchase", "freight-in", "material", "goods", "supply", "procurement", "tariff"],
    bqField: "purchases_of_inventory",
    sapSource: "ACDOCA (filter: KTOSL = inventory GR/IR posting keys)",
  },
  {
    id: "compensation",
    label: "Employee Compensation",
    code: "ASC 220-40",
    color: "#2563EB",
    bg: "#DBEAFE",
    border: "#93C5FD",
    description: "All wages, salaries, bonuses, equity/stock comp, benefits, pension, post-retirement, and termination benefits for services rendered.",
    keywords: ["salary", "salaries", "wage", "bonus", "compensation", "payroll", "benefit", "pension", "stock comp", "equity", "hr", "labor", "employee", "termination", "headcount"],
    bqField: "employee_compensation",
    sapSource: "ACDOCA join HR PA/PY (cost center KOSTL, all wage types)",
  },
  {
    id: "depreciation",
    label: "Depreciation",
    code: "ASC 360",
    color: "#D97706",
    bg: "#FEF3C7",
    border: "#FCD34D",
    description: "PP&E depreciation only per ASC 360-10-50-1(a). Does NOT include amortization of intangibles — that is a separate category.",
    keywords: ["depreciation", "pp&e", "fixed asset", "equipment", "machinery", "building", "furniture", "vehicle", "property"],
    bqField: "depreciation",
    sapSource: "ANLC.NAFAB (FI-AA, filter ANLKL for tangible asset classes)",
  },
  {
    id: "amortization",
    label: "Intangible Asset Amortization",
    code: "ASC 350",
    color: "#7C3AED",
    bg: "#EDE9FE",
    border: "#C4B5FD",
    description: "Amortization of finite-lived intangibles per ASC 350-30-50-2(a)(2). Includes capitalized software under ASC 985-20.",
    keywords: ["amortization", "intangible", "patent", "trademark", "license", "customer list", "software", "goodwill", "ip", "intellectual property"],
    bqField: "intangible_amortization",
    sapSource: "ANLC.NAFAB (FI-AA, filter ANLKL for intangible asset classes)",
  },
  {
    id: "dda",
    label: "DD&A (Extractive Industries)",
    code: "ASC 932",
    color: "#0891B2",
    bg: "#CFFAFE",
    border: "#67E8F9",
    description: "Depletion, Depreciation & Amortization for extractive industries only (oil & gas, mining). Not applicable to most entities.",
    keywords: ["depletion", "dd&a", "extractive", "oil", "gas", "mining", "mineral", "reserve"],
    bqField: "dda_extractive",
    sapSource: "IS-OIL / IS-MIN specific posting keys in ACDOCA",
  },
  {
    id: "other",
    label: "Other",
    code: "Catch-all",
    color: "#DC2626",
    bg: "#FEE2E2",
    border: "#FCA5A5",
    description: "Amounts within a relevant expense caption that don't fall into any of the 5 natural categories above. Common examples: rent, advertising, professional fees, insurance.",
    keywords: ["rent", "lease", "advertising", "marketing", "legal", "professional", "insurance", "travel", "utilities", "subscription", "consulting"],
    bqField: "other_expenses",
    sapSource: "ACDOCA (residual GL accounts per relevant caption)",
  },
];

const SAMPLE_ACCOUNTS = [
  { id: 1, code: "5010", desc: "Raw Material Purchases", caption: "COGS", category: "inventory", confidence: "high", status: "mapped", rationale: "ASC 330-10-30-1: direct purchase of raw materials" },
  { id: 2, code: "5020", desc: "Freight-In on Purchases", caption: "COGS", category: "inventory", confidence: "high", status: "mapped", rationale: "ASC 330-10-30-1: costs to bring asset to condition/location" },
  { id: 3, code: "5110", desc: "Direct Labor - Production", caption: "COGS", category: "compensation", confidence: "high", status: "mapped", rationale: "ASC 220-40: cash consideration for services rendered" },
  { id: 4, code: "5120", desc: "Employee Benefits - Production", caption: "COGS", category: "compensation", confidence: "high", status: "mapped", rationale: "ASC 220-40: medical, pension benefits" },
  { id: 5, code: "5210", desc: "Depreciation - Manufacturing Equipment", caption: "COGS", category: "depreciation", confidence: "high", status: "mapped", rationale: "ASC 360-10-50-1(a): PP&E depreciation" },
  { id: 6, code: "5220", desc: "Amortization - Production Patents", caption: "COGS", category: "amortization", confidence: "high", status: "mapped", rationale: "ASC 350-30: finite-lived intangible amortization" },
  { id: 7, code: "6010", desc: "Salaries - Sales Force", caption: "SG&A", category: "compensation", confidence: "high", status: "mapped", rationale: "ASC 220-40: wages and salaries" },
  { id: 8, code: "6030", desc: "Stock Compensation Expense", caption: "SG&A", category: "compensation", confidence: "high", status: "mapped", rationale: "ASC 220-40: share-based payment arrangements explicitly included" },
  { id: 9, code: "6110", desc: "Depreciation - Office Equipment", caption: "SG&A", category: "depreciation", confidence: "high", status: "mapped", rationale: "ASC 360-10-50-1(a): PP&E depreciation" },
  { id: 10, code: "6120", desc: "Amortization - Customer Lists", caption: "SG&A", category: "amortization", confidence: "high", status: "mapped", rationale: "ASC 350-30: finite-lived intangible" },
  { id: 11, code: "6210", desc: "Advertising & Promotions", caption: "SG&A", category: "other", confidence: "high", status: "mapped", rationale: "No natural category applies; also part of selling expense narrative total" },
  { id: 12, code: "6310", desc: "Operating Lease - Office Rent", caption: "SG&A", category: "other", confidence: "high", status: "mapped", rationale: "ASC 842 lease cost; NOT PP&E depreciation — maps to Other" },
  { id: 13, code: "7010", desc: "R&D Labor", caption: "R&D", category: "compensation", confidence: "high", status: "mapped", rationale: "ASC 220-40: wages for R&D employees" },
  { id: 14, code: "7020", desc: "R&D Materials & Supplies", caption: "R&D", category: "", confidence: "", status: "review", rationale: "Confirm: expensed per ASC 730 (Other) vs. capitalized to inventory (Inventory)" },
  { id: 15, code: "8010", desc: "Interest Expense", caption: "Interest Expense", category: "", confidence: "", status: "exclude", rationale: "NOT a relevant caption — no prescribed natural category present" },
  { id: 16, code: "9010", desc: "Income Tax Expense", caption: "Income Tax", category: "", confidence: "", status: "exclude", rationale: "NOT a relevant caption — explicitly excluded" },
];

const CONFIDENCE_OPTS = ["high", "medium", "low"];
const STATUS_OPTS = ["mapped", "review", "gap", "exclude"];
const CAPTION_OPTS = ["COGS", "Cost of Services", "SG&A", "R&D", "Other Operating", "Interest Expense", "Income Tax"];

const statusStyle = {
  mapped:  { bg: "#DCFCE7", color: "#15803D", label: "Mapped" },
  review:  { bg: "#FEF9C3", color: "#A16207", label: "Needs Review" },
  gap:     { bg: "#FEE2E2", color: "#B91C1C", label: "Gap" },
  exclude: { bg: "#F1F5F9", color: "#64748B", label: "Excluded" },
};

const confStyle = {
  high:   { color: "#15803D", dot: "#22C55E" },
  medium: { color: "#A16207", dot: "#EAB308" },
  low:    { color: "#B91C1C", dot: "#EF4444" },
};

function Badge({ status }) {
  const s = statusStyle[status] || statusStyle.review;
  return (
    <span style={{ background: s.bg, color: s.color, fontSize: 11, fontWeight: 700,
      padding: "2px 8px", borderRadius: 20, letterSpacing: "0.03em", whiteSpace: "nowrap" }}>
      {s.label}
    </span>
  );
}

function ConfDot({ conf }) {
  const s = confStyle[conf] || {};
  if (!conf) return null;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, color: s.color, fontWeight: 600 }}>
      <span style={{ width: 7, height: 7, borderRadius: "50%", background: s.dot, display: "inline-block" }} />
      {conf.charAt(0).toUpperCase() + conf.slice(1)}
    </span>
  );
}

function CatPill({ catId }) {
  const cat = DISE_CATEGORIES.find(c => c.id === catId);
  if (!cat) return <span style={{ color: "#94A3B8", fontSize: 12 }}>— Unassigned —</span>;
  return (
    <span style={{ background: cat.bg, color: cat.color, border: `1px solid ${cat.border}`,
      fontSize: 11, fontWeight: 700, padding: "2px 10px", borderRadius: 20, whiteSpace: "nowrap" }}>
      {cat.label}
    </span>
  );
}

// Generate unique IDs safely
let _nextId = 100;
function generateId() {
  return ++_nextId;
}

export default function DISEMapper() {
  // Load from localStorage if available, otherwise use sample data
  const [accounts, setAccounts] = useState(() => {
    try {
      const saved = localStorage.getItem('dise_mapper_accounts');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch { /* ignore parse errors */ }
    return SAMPLE_ACCOUNTS;
  });
  const [activeTab, setActiveTab] = useState("mapper");
  const [editingId, setEditingId] = useState(null);
  const [newAccount, setNewAccount] = useState({ code: "", desc: "", caption: "", category: "", confidence: "", status: "review", rationale: "" });
  const [filter, setFilter] = useState({ caption: "", status: "", category: "" });
  const [suggestFor, setSuggestFor] = useState(null);
  const [showAdd, setShowAdd] = useState(false);

  // Persist to localStorage on changes
  useEffect(() => {
    try { localStorage.setItem('dise_mapper_accounts', JSON.stringify(accounts)); }
    catch { /* ignore quota errors */ }
  }, [accounts]);

  const filtered = useMemo(() => accounts.filter(a =>
    (!filter.caption || a.caption === filter.caption) &&
    (!filter.status  || a.status  === filter.status)  &&
    (!filter.category|| a.category=== filter.category)
  ), [accounts, filter]);

  const coverage = useMemo(() => {
    const mapped    = accounts.filter(a => a.status === "mapped").length;
    const review    = accounts.filter(a => a.status === "review").length;
    const gap       = accounts.filter(a => a.status === "gap").length;
    const excluded  = accounts.filter(a => a.status === "exclude").length;
    const total     = accounts.length;
    const catCounts = {};
    DISE_CATEGORIES.forEach(c => {
      catCounts[c.id] = {
        mapped: accounts.filter(a => a.category === c.id && a.status === "mapped").length,
        review: accounts.filter(a => a.category === c.id && a.status === "review").length,
        gap:    accounts.filter(a => a.category === c.id && a.status === "gap").length,
      };
    });
    return { mapped, review, gap, excluded, total, catCounts };
  }, [accounts]);

  function autoSuggest(desc) {
    const lower = desc.toLowerCase();
    for (const cat of DISE_CATEGORIES) {
      if (cat.keywords.some(k => lower.includes(k))) return cat.id;
    }
    return "";
  }

  function updateAccount(id, field, value) {
    setAccounts(prev => prev.map(a => a.id === id ? { ...a, [field]: value } : a));
  }

  function addAccount() {
    if (!newAccount.code || !newAccount.desc) return;
    const suggested = autoSuggest(newAccount.desc);
    setAccounts(prev => [...prev, {
      ...newAccount,
      id: generateId(),
      category: newAccount.category || suggested,
      status: newAccount.status || "review",
    }]);
    setNewAccount({ code: "", desc: "", caption: "", category: "", confidence: "", status: "review", rationale: "" });
    setShowAdd(false);
  }

  function removeAccount(id) {
    const acct = accounts.find(a => a.id === id);
    const label = acct ? `${acct.code} — ${acct.desc}` : `ID ${id}`;
    if (!window.confirm(`Remove GL account ${label}? This cannot be undone.`)) return;
    setAccounts(prev => prev.filter(a => a.id !== id));
  }

  const tabs = [
    { id: "mapper",    label: "🗺  Category Mapper" },
    { id: "coverage",  label: "📊  Coverage Dashboard" },
    { id: "bqmap",     label: "🔗  BigQuery Field Map" },
    { id: "preview",   label: "📋  Disclosure Preview" },
  ];

  return (
    <div style={{ fontFamily: "'IBM Plex Sans', 'Segoe UI', sans-serif", background: "#0F172A", minHeight: "100vh", color: "#E2E8F0" }}>
      {/* Header */}
      <div style={{ background: "linear-gradient(135deg, #1E3A5F 0%, #1B2A4A 60%, #0F172A 100%)", borderBottom: "1px solid #334155", padding: "20px 28px 0" }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 16 }}>
          <div style={{ background: "#2563EB", width: 44, height: 44, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22, flexShrink: 0 }}>🗂</div>
          <div>
            <div style={{ fontSize: 20, fontWeight: 800, color: "#F1F5F9", letterSpacing: "-0.02em" }}>FASB ASU 2024-03 DISE Mapping Tool</div>
            <div style={{ fontSize: 12, color: "#94A3B8", marginTop: 2 }}>Expense Disaggregation · Google Cortex + BigQuery + Vertex AI · MVP Validation</div>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 8, flexWrap: "wrap" }}>
            <div style={{ background: "#1E293B", border: "1px solid #334155", borderRadius: 8, padding: "6px 12px", fontSize: 11, color: "#94A3B8" }}>
              <span style={{ color: "#22C55E", fontWeight: 700 }}>{coverage.mapped}</span> Mapped &nbsp;
              <span style={{ color: "#EAB308", fontWeight: 700 }}>{coverage.review}</span> Review &nbsp;
              <span style={{ color: "#EF4444", fontWeight: 700 }}>{coverage.gap}</span> Gap
            </div>
            <div style={{ background: "#2563EB", borderRadius: 8, padding: "6px 12px", fontSize: 11, color: "#DBEAFE", fontWeight: 700 }}>
              {coverage.total > 0 ? Math.round((coverage.mapped / (coverage.total - coverage.excluded)) * 100) : 0}% Coverage
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 2 }}>
          {tabs.map(t => (
            <button key={t.id} onClick={() => setActiveTab(t.id)}
              style={{ background: activeTab === t.id ? "#0F172A" : "transparent",
                color: activeTab === t.id ? "#F1F5F9" : "#64748B",
                border: "none", borderRadius: "8px 8px 0 0", padding: "10px 16px",
                fontSize: 13, fontWeight: 600, cursor: "pointer",
                borderBottom: activeTab === t.id ? "2px solid #2563EB" : "2px solid transparent",
                transition: "all 0.15s" }}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ padding: "24px 28px" }}>

        {/* ── TAB: MAPPER ──────────────────────────────────────────────────── */}
        {activeTab === "mapper" && (
          <div>
            {/* Category legend */}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 20 }}>
              {DISE_CATEGORIES.map(cat => (
                <div key={cat.id} style={{ background: "#1E293B", border: `1px solid ${cat.border}`,
                  borderRadius: 8, padding: "6px 12px", display: "flex", flexDirection: "column", gap: 2, minWidth: 170 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ width: 9, height: 9, borderRadius: "50%", background: cat.color, flexShrink: 0 }} />
                    <span style={{ fontSize: 11, fontWeight: 700, color: cat.color }}>{cat.label}</span>
                  </div>
                  <span style={{ fontSize: 10, color: "#64748B" }}>{cat.code} · BQ: {cat.bqField}</span>
                </div>
              ))}
            </div>

            {/* Filters */}
            <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
              <span style={{ fontSize: 12, color: "#64748B", fontWeight: 600 }}>FILTER:</span>
              {["caption", "status", "category"].map(field => (
                <select key={field} value={filter[field]}
                  onChange={e => setFilter(f => ({ ...f, [field]: e.target.value }))}
                  style={{ background: "#1E293B", border: "1px solid #334155", color: "#CBD5E1",
                    borderRadius: 6, padding: "5px 10px", fontSize: 12, cursor: "pointer" }}>
                  <option value="">All {field.charAt(0).toUpperCase() + field.slice(1)}s</option>
                  {field === "caption" && CAPTION_OPTS.map(o => <option key={o} value={o}>{o}</option>)}
                  {field === "status"  && STATUS_OPTS.map(o  => <option key={o} value={o}>{statusStyle[o]?.label}</option>)}
                  {field === "category"&& DISE_CATEGORIES.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
                </select>
              ))}
              <button onClick={() => setFilter({ caption: "", status: "", category: "" })}
                style={{ background: "#334155", border: "none", color: "#94A3B8", borderRadius: 6,
                  padding: "5px 12px", fontSize: 12, cursor: "pointer" }}>Clear</button>
              <button onClick={() => setShowAdd(v => !v)}
                style={{ marginLeft: "auto", background: "#2563EB", border: "none", color: "white",
                  borderRadius: 6, padding: "6px 14px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                + Add GL Account
              </button>
            </div>

            {/* Add form */}
            {showAdd && (
              <div style={{ background: "#1E293B", border: "1px solid #2563EB", borderRadius: 10, padding: 16, marginBottom: 16 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: "#93C5FD", marginBottom: 12 }}>Add GL Account</div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10 }}>
                  {[["code","Account #"],["desc","Description"],["caption","IS Caption"]].map(([field, label]) => (
                    <div key={field}>
                      <div style={{ fontSize: 11, color: "#64748B", marginBottom: 4 }}>{label}</div>
                      {field === "caption" ? (
                        <select value={newAccount.caption} onChange={e => setNewAccount(a => ({ ...a, caption: e.target.value }))}
                          style={{ width: "100%", background: "#0F172A", border: "1px solid #334155", color: "#CBD5E1", borderRadius: 6, padding: "6px 8px", fontSize: 12 }}>
                          <option value="">Select...</option>
                          {CAPTION_OPTS.map(o => <option key={o} value={o}>{o}</option>)}
                        </select>
                      ) : (
                        <input value={newAccount[field]}
                          onChange={e => {
                            const v = e.target.value;
                            setNewAccount(a => ({ ...a, [field]: v,
                              category: field === "desc" ? autoSuggest(v) : a.category }));
                          }}
                          placeholder={label}
                          style={{ width: "100%", background: "#0F172A", border: "1px solid #334155", color: "#E2E8F0",
                            borderRadius: 6, padding: "6px 8px", fontSize: 12, boxSizing: "border-box" }} />
                      )}
                    </div>
                  ))}
                  <div>
                    <div style={{ fontSize: 11, color: "#64748B", marginBottom: 4 }}>DISE Category
                      {newAccount.desc && autoSuggest(newAccount.desc) &&
                        <span style={{ color: "#22C55E", marginLeft: 4 }}>✦ AI Suggested</span>}
                    </div>
                    <select value={newAccount.category} onChange={e => setNewAccount(a => ({ ...a, category: e.target.value }))}
                      style={{ width: "100%", background: "#0F172A", border: "1px solid #334155", color: "#CBD5E1", borderRadius: 6, padding: "6px 8px", fontSize: 12 }}>
                      <option value="">— Unassigned —</option>
                      {DISE_CATEGORIES.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
                    </select>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: "#64748B", marginBottom: 4 }}>Confidence</div>
                    <select value={newAccount.confidence} onChange={e => setNewAccount(a => ({ ...a, confidence: e.target.value }))}
                      style={{ width: "100%", background: "#0F172A", border: "1px solid #334155", color: "#CBD5E1", borderRadius: 6, padding: "6px 8px", fontSize: 12 }}>
                      <option value="">Select...</option>
                      {CONFIDENCE_OPTS.map(o => <option key={o} value={o}>{o.charAt(0).toUpperCase()+o.slice(1)}</option>)}
                    </select>
                  </div>
                </div>
                <div style={{ marginTop: 10 }}>
                  <div style={{ fontSize: 11, color: "#64748B", marginBottom: 4 }}>Mapping Rationale (cite ASC paragraph)</div>
                  <input value={newAccount.rationale} onChange={e => setNewAccount(a => ({ ...a, rationale: e.target.value }))}
                    placeholder="e.g. ASC 330-10-30-1: costs to purchase raw materials..."
                    style={{ width: "100%", background: "#0F172A", border: "1px solid #334155", color: "#E2E8F0",
                      borderRadius: 6, padding: "6px 10px", fontSize: 12, boxSizing: "border-box" }} />
                </div>
                <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                  <button onClick={addAccount}
                    style={{ background: "#2563EB", border: "none", color: "white", borderRadius: 6,
                      padding: "7px 18px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>Add Account</button>
                  <button onClick={() => setShowAdd(false)}
                    style={{ background: "#334155", border: "none", color: "#94A3B8", borderRadius: 6,
                      padding: "7px 14px", fontSize: 12, cursor: "pointer" }}>Cancel</button>
                </div>
              </div>
            )}

            {/* Table */}
            <div style={{ background: "#1E293B", borderRadius: 12, border: "1px solid #334155", overflow: "hidden" }}>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: "#0F172A" }}>
                      {["GL #", "Description", "IS Caption", "DISE Category", "Confidence", "Status", "Mapping Rationale", ""].map((h, i) => (
                        <th key={i} style={{ padding: "10px 12px", textAlign: "left", color: "#64748B",
                          fontWeight: 700, fontSize: 11, borderBottom: "1px solid #334155",
                          whiteSpace: "nowrap", letterSpacing: "0.05em" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((acct, idx) => (
                      <tr key={acct.id}
                        style={{ borderBottom: "1px solid #1E293B",
                          background: idx % 2 === 0 ? "#1E293B" : "#182032",
                          transition: "background 0.1s" }}
                        onMouseEnter={e => e.currentTarget.style.background = "#243050"}
                        onMouseLeave={e => e.currentTarget.style.background = idx % 2 === 0 ? "#1E293B" : "#182032"}>
                        <td style={{ padding: "8px 12px", fontWeight: 700, color: "#93C5FD", whiteSpace: "nowrap" }}>{acct.code}</td>
                        <td style={{ padding: "8px 12px", color: "#CBD5E1", maxWidth: 200 }}>{acct.desc}</td>
                        <td style={{ padding: "8px 12px" }}>
                          <span style={{ background: "#0F172A", border: "1px solid #334155",
                            color: "#94A3B8", fontSize: 11, padding: "2px 8px", borderRadius: 4 }}>
                            {acct.caption || "—"}
                          </span>
                        </td>
                        <td style={{ padding: "8px 12px" }}>
                          {editingId === acct.id ? (
                            <select value={acct.category}
                              onChange={e => updateAccount(acct.id, "category", e.target.value)}
                              style={{ background: "#0F172A", border: "1px solid #2563EB", color: "#CBD5E1",
                                borderRadius: 6, padding: "4px 8px", fontSize: 11 }}>
                              <option value="">— Unassigned —</option>
                              {DISE_CATEGORIES.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
                            </select>
                          ) : (
                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                              <CatPill catId={acct.category} />
                              {!acct.category && acct.desc && autoSuggest(acct.desc) && (
                                <button onClick={() => updateAccount(acct.id, "category", autoSuggest(acct.desc))}
                                  style={{ background: "#1D4ED8", border: "none", color: "#BFDBFE",
                                    fontSize: 10, padding: "2px 6px", borderRadius: 4, cursor: "pointer" }}>
                                  ✦ Suggest
                                </button>
                              )}
                            </div>
                          )}
                        </td>
                        <td style={{ padding: "8px 12px" }}>
                          {editingId === acct.id ? (
                            <select value={acct.confidence}
                              onChange={e => updateAccount(acct.id, "confidence", e.target.value)}
                              style={{ background: "#0F172A", border: "1px solid #334155", color: "#CBD5E1",
                                borderRadius: 6, padding: "4px 8px", fontSize: 11 }}>
                              <option value="">—</option>
                              {CONFIDENCE_OPTS.map(o => <option key={o} value={o}>{o}</option>)}
                            </select>
                          ) : <ConfDot conf={acct.confidence} />}
                        </td>
                        <td style={{ padding: "8px 12px" }}>
                          {editingId === acct.id ? (
                            <select value={acct.status}
                              onChange={e => updateAccount(acct.id, "status", e.target.value)}
                              style={{ background: "#0F172A", border: "1px solid #334155", color: "#CBD5E1",
                                borderRadius: 6, padding: "4px 8px", fontSize: 11 }}>
                              {STATUS_OPTS.map(o => <option key={o} value={o}>{statusStyle[o]?.label}</option>)}
                            </select>
                          ) : <Badge status={acct.status} />}
                        </td>
                        <td style={{ padding: "8px 12px", color: "#64748B", fontSize: 11, maxWidth: 280 }}>
                          {editingId === acct.id ? (
                            <input value={acct.rationale}
                              onChange={e => updateAccount(acct.id, "rationale", e.target.value)}
                              style={{ width: "100%", background: "#0F172A", border: "1px solid #334155",
                                color: "#E2E8F0", borderRadius: 6, padding: "4px 8px", fontSize: 11, boxSizing: "border-box" }} />
                          ) : <span style={{ color: "#64748B" }}>{acct.rationale}</span>}
                        </td>
                        <td style={{ padding: "8px 8px", whiteSpace: "nowrap" }}>
                          <button onClick={() => setEditingId(editingId === acct.id ? null : acct.id)}
                            style={{ background: editingId === acct.id ? "#15803D" : "#334155",
                              border: "none", color: "white", borderRadius: 5,
                              padding: "4px 10px", fontSize: 11, cursor: "pointer", marginRight: 4 }}>
                            {editingId === acct.id ? "✓" : "Edit"}
                          </button>
                          <button onClick={() => removeAccount(acct.id)}
                            style={{ background: "transparent", border: "1px solid #334155",
                              color: "#EF4444", borderRadius: 5, padding: "4px 8px", fontSize: 11, cursor: "pointer" }}>✕</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div style={{ marginTop: 10, fontSize: 11, color: "#475569" }}>
              Showing {filtered.length} of {accounts.length} accounts &nbsp;·&nbsp; ✦ Suggest button uses keyword-based AI auto-classification
            </div>
          </div>
        )}

        {/* ── TAB: COVERAGE ────────────────────────────────────────────────── */}
        {activeTab === "coverage" && (
          <div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 16, marginBottom: 24 }}>
              {[
                { label: "Total GL Accounts", value: coverage.total, color: "#94A3B8" },
                { label: "Fully Mapped", value: coverage.mapped, color: "#22C55E" },
                { label: "Needs Review", value: coverage.review, color: "#EAB308" },
                { label: "Gaps", value: coverage.gap, color: "#EF4444" },
                { label: "Excluded", value: coverage.excluded, color: "#64748B" },
                { label: "Coverage Rate",
                  value: coverage.total > 0 ? `${Math.round((coverage.mapped / (coverage.total - coverage.excluded)) * 100)}%` : "0%",
                  color: "#2563EB" },
              ].map(stat => (
                <div key={stat.label} style={{ background: "#1E293B", border: "1px solid #334155", borderRadius: 12, padding: 20 }}>
                  <div style={{ fontSize: 11, color: "#64748B", fontWeight: 600, letterSpacing: "0.06em", marginBottom: 8 }}>{stat.label.toUpperCase()}</div>
                  <div style={{ fontSize: 32, fontWeight: 800, color: stat.color }}>{stat.value}</div>
                </div>
              ))}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              {DISE_CATEGORIES.map(cat => {
                const counts = coverage.catCounts[cat.id] || { mapped: 0, review: 0, gap: 0 };
                const total = counts.mapped + counts.review + counts.gap;
                const pct = total > 0 ? Math.round((counts.mapped / total) * 100) : 100;
                return (
                  <div key={cat.id} style={{ background: "#1E293B", border: `1px solid ${cat.border}`, borderRadius: 12, padding: 18 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
                      <div>
                        <div style={{ fontWeight: 700, color: cat.color, fontSize: 13 }}>{cat.label}</div>
                        <div style={{ fontSize: 11, color: "#475569", marginTop: 2 }}>{cat.code} · BQ: <code style={{ color: "#93C5FD" }}>{cat.bqField}</code></div>
                      </div>
                      <div style={{ fontSize: 22, fontWeight: 800, color: pct === 100 ? "#22C55E" : pct > 60 ? "#EAB308" : "#EF4444" }}>{pct}%</div>
                    </div>
                    <div style={{ background: "#0F172A", borderRadius: 6, height: 8, overflow: "hidden", marginBottom: 10 }}>
                      <div style={{ width: `${pct}%`, height: "100%", background: cat.color, borderRadius: 6, transition: "width 0.5s" }} />
                    </div>
                    <div style={{ display: "flex", gap: 12, fontSize: 11 }}>
                      <span style={{ color: "#22C55E" }}>✓ {counts.mapped} mapped</span>
                      <span style={{ color: "#EAB308" }}>⚠ {counts.review} review</span>
                      <span style={{ color: "#EF4444" }}>✕ {counts.gap} gap</span>
                    </div>
                    <div style={{ marginTop: 10, fontSize: 11, color: "#475569", lineHeight: 1.5 }}>{cat.description}</div>
                  </div>
                );
              })}
            </div>

            <div style={{ background: "#1E293B", border: "1px solid #F59E0B", borderRadius: 12, padding: 18, marginTop: 16 }}>
              <div style={{ fontWeight: 700, color: "#F59E0B", fontSize: 13, marginBottom: 8 }}>⚠ Guardrails & Common Mistakes</div>
              {[
                "Interest Expense and Income Tax Expense are NEVER relevant captions — do not disaggregate them.",
                "Selling expenses is a FUNCTIONAL disclosure (narrative total + definition) — it is NOT one of the 5 natural categories in the tabular table.",
                "ASC 842 operating lease cost (ROU asset) → Other. The ROU asset depreciation → Depreciation. These are different accounts.",
                "If an entire IS caption is already a single natural category (e.g., a standalone 'Depreciation' line) — no further disaggregation required.",
                "DD&A only applies to extractive industries (oil & gas, mining). Mark all other entities as N/A for this category.",
                "One-time employee termination benefits (ASC 420) must be separately disclosed within Employee Compensation.",
              ].map((note, i) => (
                <div key={i} style={{ display: "flex", gap: 8, marginBottom: 6, fontSize: 12, color: "#CBD5E1" }}>
                  <span style={{ color: "#F59E0B", flexShrink: 0 }}>›</span> {note}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── TAB: BQ FIELD MAP ────────────────────────────────────────────── */}
        {activeTab === "bqmap" && (
          <div>
            <div style={{ background: "#1E293B", border: "1px solid #334155", borderRadius: 12, overflow: "hidden" }}>
              <div style={{ padding: "14px 18px", borderBottom: "1px solid #334155", background: "#0F172A" }}>
                <div style={{ fontWeight: 700, color: "#F1F5F9", fontSize: 14 }}>BigQuery Target Schema — Cortex Framework Extension</div>
                <div style={{ fontSize: 12, color: "#64748B", marginTop: 3 }}>Dataset: <code style={{ color: "#93C5FD" }}>dise_reporting</code> · Table: <code style={{ color: "#93C5FD" }}>fact_expense_disagg</code></div>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: "#1E293B" }}>
                      {["DISE Category","BQ Field Name","BQ Type","Source System","Source Table","Source Field","Transformation Logic","Validation Test"].map((h, i) => (
                        <th key={i} style={{ padding: "10px 12px", textAlign: "left", color: "#64748B",
                          fontWeight: 700, fontSize: 11, borderBottom: "1px solid #334155", whiteSpace: "nowrap" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {DISE_CATEGORIES.map((cat, idx) => (
                      <tr key={cat.id} style={{ background: idx % 2 === 0 ? "#1E293B" : "#182032", borderBottom: "1px solid #1E293B" }}>
                        <td style={{ padding: "10px 12px" }}><CatPill catId={cat.id} /></td>
                        <td style={{ padding: "10px 12px" }}><code style={{ color: "#93C5FD", fontSize: 12 }}>{cat.bqField}</code></td>
                        <td style={{ padding: "10px 12px" }}><code style={{ color: "#86EFAC", fontSize: 11 }}>NUMERIC</code></td>
                        <td style={{ padding: "10px 12px", color: "#CBD5E1" }}>SAP S/4HANA</td>
                        <td style={{ padding: "10px 12px", color: "#CBD5E1", fontSize: 11 }}>{cat.sapSource.split("(")[0].trim()}</td>
                        <td style={{ padding: "10px 12px" }}><code style={{ color: "#FCD34D", fontSize: 11 }}>DMBTR / NAFAB</code></td>
                        <td style={{ padding: "10px 12px", color: "#64748B", fontSize: 11, maxWidth: 220 }}>{cat.sapSource}</td>
                        <td style={{ padding: "10px 12px", color: "#64748B", fontSize: 11 }}>Reconcile to relevant caption total; NULL check; non-negative for most fields</td>
                      </tr>
                    ))}
                    <tr style={{ background: "#0F172A", borderTop: "2px solid #334155" }}>
                      <td style={{ padding: "10px 12px", color: "#94A3B8", fontWeight: 700 }}>Metadata Fields</td>
                      <td colSpan={7} style={{ padding: "10px 12px", color: "#64748B", fontSize: 11 }}>
                        fiscal_year, fiscal_period, expense_caption, cost_center, profit_center, company_code, currency_key, inventory_basis_election, estimation_flag, load_timestamp
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div style={{ background: "#1E293B", border: "1px solid #334155", borderRadius: 12, padding: 20, marginTop: 16 }}>
              <div style={{ fontWeight: 700, color: "#F1F5F9", fontSize: 13, marginBottom: 14 }}>Transformation Logic Template (BigQuery SQL)</div>
              <pre style={{ background: "#0F172A", border: "1px solid #334155", borderRadius: 8, padding: 16,
                fontSize: 11, color: "#86EFAC", overflowX: "auto", lineHeight: 1.6, margin: 0 }}>
{`-- Cortex Framework DISE Transformation — fact_expense_disagg
-- Source: ACDOCA (SAP Universal Journal) via Cortex Finance data model

CREATE OR REPLACE TABLE \`dise_reporting.fact_expense_disagg\` AS

WITH base AS (
  SELECT
    GJAHR                          AS fiscal_year,
    POPER                          AS fiscal_period,
    BUKRS                          AS company_code,
    KOSTL                          AS cost_center,
    RACCT                          AS gl_account,
    WAERS                          AS currency_key,
    SUM(DMBTR)                     AS amount_local_currency

  FROM \`cortex_sap.acdoca\`
  WHERE GJAHR = @fiscal_year
    AND BLART NOT IN ('AA')        -- exclude asset postings (use ANLC instead)
  GROUP BY 1,2,3,4,5,6
),

mapped AS (
  SELECT
    b.*,
    m.expense_caption,
    m.dise_category,
    m.inventory_basis_election,
    m.estimation_flag
  FROM base b
  JOIN \`dise_reporting.gl_dise_mapping\` m  -- <-- This is your mapping output
    ON b.gl_account = m.gl_account
  WHERE m.status = 'mapped'
)

SELECT
  fiscal_year,
  fiscal_period,
  company_code,
  expense_caption,
  SUM(CASE WHEN dise_category = 'inventory'     THEN amount_local_currency ELSE 0 END) AS purchases_of_inventory,
  SUM(CASE WHEN dise_category = 'compensation'  THEN amount_local_currency ELSE 0 END) AS employee_compensation,
  SUM(CASE WHEN dise_category = 'depreciation'  THEN amount_local_currency ELSE 0 END) AS depreciation,
  SUM(CASE WHEN dise_category = 'amortization'  THEN amount_local_currency ELSE 0 END) AS intangible_amortization,
  SUM(CASE WHEN dise_category = 'dda'           THEN amount_local_currency ELSE 0 END) AS dda_extractive,
  SUM(CASE WHEN dise_category = 'other'         THEN amount_local_currency ELSE 0 END) AS other_expenses,
  SUM(amount_local_currency)                                                             AS total_caption_expense,
  CURRENT_TIMESTAMP()                                                                    AS load_timestamp
FROM mapped
GROUP BY 1,2,3,4
ORDER BY 1,2,3,4;`}
              </pre>
            </div>
          </div>
        )}

        {/* ── TAB: DISCLOSURE PREVIEW ──────────────────────────────────────── */}
        {activeTab === "preview" && (
          <div>
            <div style={{ background: "#1E293B", border: "1px solid #334155", borderRadius: 12, overflow: "hidden", marginBottom: 16 }}>
              <div style={{ padding: "14px 20px", borderBottom: "1px solid #334155", background: "#0F172A" }}>
                <div style={{ fontWeight: 700, color: "#F1F5F9", fontSize: 14 }}>Note X — Disaggregation of Income Statement Expenses</div>
                <div style={{ fontSize: 12, color: "#64748B", marginTop: 2 }}>ASC 220-40 (ASU 2024-03) · Simulated Tabular Footnote Disclosure · Amounts in $000s</div>
              </div>
              <div style={{ overflowX: "auto", padding: 20 }}>
                <div style={{ fontSize: 12, color: "#94A3B8", marginBottom: 16, lineHeight: 1.6 }}>
                  The following table disaggregates the Company's relevant income statement expense captions into the natural expense categories required by ASC 220-40 for the fiscal year ended [DATE].
                </div>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr>
                      <th style={{ padding: "10px 14px", textAlign: "left", background: "#0F172A",
                        color: "#F1F5F9", fontWeight: 700, border: "1px solid #334155", fontSize: 12 }}>Natural Expense Category</th>
                      {["Cost of Products Sold", "Cost of Services", "SG&A", "R&D Expense", "Total"].map(h => (
                        <th key={h} style={{ padding: "10px 14px", textAlign: "right", background: "#0F172A",
                          color: "#F1F5F9", fontWeight: 700, border: "1px solid #334155", fontSize: 12 }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { cat: DISE_CATEGORIES[0], vals: [1000, 0, 0, 50] },
                      { cat: DISE_CATEGORIES[1], vals: [800, 600, 1200, 400] },
                      { cat: DISE_CATEGORIES[2], vals: [150, 80, 120, 20] },
                      { cat: DISE_CATEGORIES[3], vals: [60, 40, 90, 30] },
                      { cat: DISE_CATEGORIES[4], vals: [0, 0, 0, 0] },
                      { cat: DISE_CATEGORIES[5], vals: [200, 180, 450, 80] },
                    ].map(({ cat, vals }, idx) => {
                      const total = vals.reduce((a, b) => a + b, 0);
                      return (
                        <tr key={cat.id} style={{ background: idx % 2 === 0 ? "#1E293B" : "#182032" }}>
                          <td style={{ padding: "9px 14px", border: "1px solid #334155" }}>
                            <CatPill catId={cat.id} />
                          </td>
                          {vals.map((v, i) => (
                            <td key={i} style={{ padding: "9px 14px", textAlign: "right",
                              border: "1px solid #334155", color: v === 0 ? "#334155" : "#E2E8F0",
                              fontWeight: v === 0 ? 400 : 500 }}>
                              {v === 0 ? "—" : v.toLocaleString()}
                            </td>
                          ))}
                          <td style={{ padding: "9px 14px", textAlign: "right",
                            border: "1px solid #334155", color: "#93C5FD", fontWeight: 700 }}>
                            {total === 0 ? "—" : total.toLocaleString()}
                          </td>
                        </tr>
                      );
                    })}
                    <tr style={{ background: "#0F172A", borderTop: "2px solid #2563EB" }}>
                      <td style={{ padding: "10px 14px", border: "1px solid #334155", fontWeight: 700, color: "#F1F5F9" }}>Total Relevant Expenses</td>
                      {[1000+800+150+60+200, 600+80+40+180, 1200+120+90+450, 50+400+20+30+80].map((t, i) => (
                        <td key={i} style={{ padding: "10px 14px", textAlign: "right",
                          border: "1px solid #334155", fontWeight: 700, color: "#2563EB" }}>
                          {t.toLocaleString()}
                        </td>
                      ))}
                      <td style={{ padding: "10px 14px", textAlign: "right",
                        border: "1px solid #334155", fontWeight: 800, color: "#2563EB", fontSize: 13 }}>
                        {(1000+800+150+60+200+600+80+40+180+1200+120+90+450+50+400+20+30+80).toLocaleString()}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div style={{ background: "#1E293B", border: "1px solid #F59E0B", borderRadius: 12, padding: 18 }}>
              <div style={{ fontWeight: 700, color: "#F59E0B", fontSize: 13, marginBottom: 10 }}>Selling Expense Narrative Disclosure (Annual Periods Only)</div>
              <div style={{ background: "#0F172A", borderRadius: 8, padding: 14, fontSize: 12, color: "#CBD5E1", lineHeight: 1.7, border: "1px dashed #475569" }}>
                <em>The Company defines "selling expenses" as costs directly associated with the promotion and sale of its products and services, including advertising and trade promotions, sales force compensation, sales commissions, and outbound shipping costs. Total selling expenses for the fiscal year ended [DATE] were <strong style={{ color: "#F1F5F9" }}>$[XXX]</strong> thousand.</em>
              </div>
              <div style={{ marginTop: 10, fontSize: 11, color: "#64748B" }}>
                Note: Selling expenses is a functional disclosure separate from the tabular natural expense disaggregation above. It is not one of the 5 prescribed natural categories.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
