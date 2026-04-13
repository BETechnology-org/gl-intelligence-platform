"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState, type ReactNode } from "react";

const HeroPlates = dynamic(() => import("./HeroPlates"), { ssr: false });
import {
  motion,
  useInView,
  AnimatePresence,
} from "framer-motion";
import {
  ArrowRight,
  ArrowUpRight,
  Menu,
  X,
  Sun,
  Moon,
  Shield,
  Lock,
  Users,
  Search,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  Globe,
  Building2,
  BarChart3,
  PieChart,
  Activity,
} from "lucide-react";

/* ═══════════════════════════════════════
   UTILS
   ═══════════════════════════════════════ */

function Reveal({
  children,
  className = "",
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 28 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.7, delay, ease: [0.25, 0.1, 0.25, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

function Counter({
  target,
  prefix = "",
  suffix = "",
}: {
  target: number;
  prefix?: string;
  suffix?: string;
}) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  useEffect(() => {
    if (!inView) return;
    let v = 0;
    const step = target / 80;
    const id = setInterval(() => {
      v += step;
      if (v >= target) {
        setCount(target);
        clearInterval(id);
      } else setCount(Math.floor(v));
    }, 16);
    return () => clearInterval(id);
  }, [inView, target]);
  return (
    <span ref={ref}>
      {prefix}
      {count}
      {suffix}
    </span>
  );
}

/* ═══════════════════════════════════════
   NAV
   ═══════════════════════════════════════ */
function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const [dark, setDark] = useState(true);

  // Read saved theme on mount and apply it
  useEffect(() => {
    const saved = localStorage.getItem("theme");
    const isDark = saved ? saved === "dark" : true;
    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
  }, []);

  function toggleTheme() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  }

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-all duration-500 ${
        scrolled
          ? "bg-white/90 dark:bg-[#08090C]/90 backdrop-blur-xl border-b border-[#E4E4E7] dark:border-[#222326] shadow-[0_1px_0_rgba(0,0,0,0.04),0_4px_20px_rgba(0,0,0,0.04)] dark:shadow-none"
          : "bg-transparent"
      }`}
    >
      <div className="max-w-[1400px] mx-auto px-6 md:px-10 h-[72px] flex items-center justify-between">
        <a href="#" className="flex items-center gap-3">
          <div className="relative w-8 h-8">
            <div className="absolute inset-0 rounded-[7px] bg-[#C8A660]/20" />
            <div className="absolute inset-[2px] rounded-[5px] bg-[#111] flex items-center justify-center text-[#C8A660] text-[13px] font-mono font-bold">
              tf
            </div>
          </div>
          <span className="text-[15px] tracking-[-0.02em] font-medium">
            <span className="text-[#111] dark:text-white">truffles</span>
            <span className="text-[#C8A660]">.ai</span>
          </span>
        </a>
        <nav className="hidden md:flex items-center gap-8">
          {["Platform", "Modules", "Security"].map((item) => (
            <a
              key={item}
              href={`#${item.toLowerCase()}`}
              className="text-[13px] text-[#6B6B6B] hover:text-[#111] dark:hover:text-white transition-colors duration-300"
            >
              {item}
            </a>
          ))}
        </nav>
        <div className="hidden md:flex items-center gap-4">
          <button
            onClick={toggleTheme}
            className="w-8 h-8 flex items-center justify-center rounded-full text-[#71717A] hover:text-[#111] dark:text-[#6B6B6B] dark:hover:text-white transition-colors duration-300"
            title={dark ? "Switch to light mode" : "Switch to dark mode"}
          >
            {dark ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          <a
            href="https://gl-intelligence-462410669395.us-central1.run.app/app"
            className="text-[13px] text-[#6B6B6B] hover:text-[#111] dark:hover:text-white transition-colors"
          >
            Sign in
          </a>
          <a
            href="#cta"
            className="text-[13px] font-medium text-white bg-[#111] hover:bg-[#C8A660] dark:text-[#08090C] dark:bg-white dark:hover:bg-[#C8A660] px-5 py-2 rounded-full transition-all duration-300"
          >
            Request access
          </a>
        </div>
        <div className="md:hidden flex items-center gap-3">
          <button
            onClick={toggleTheme}
            className="w-8 h-8 flex items-center justify-center rounded-full text-[#71717A] dark:text-[#6B6B6B] transition-colors"
            title={dark ? "Switch to light mode" : "Switch to dark mode"}
          >
            {dark ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          <button
            className="text-[#6B6B6B] dark:text-[#6B6B6B]"
            onClick={() => setOpen(!open)}
          >
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>
      {open && (
        <nav className="md:hidden bg-white dark:bg-[#111214] border-t border-[#E4E4E7] dark:border-[#222326] px-6 py-6 flex flex-col gap-4">
          {["Platform", "Modules", "Security", "Customers"].map((item) => (
            <a
              key={item}
              href={`#${item.toLowerCase()}`}
              onClick={() => setOpen(false)}
              className="text-sm text-[#6B6B6B] hover:text-[#111] dark:hover:text-white"
            >
              {item}
            </a>
          ))}
          <a
            href="#cta"
            className="mt-2 text-center text-sm font-medium bg-[#111] dark:bg-white text-white dark:text-[#08090C] py-2.5 rounded-full"
          >
            Request access
          </a>
        </nav>
      )}
    </header>
  );
}

/* ═══════════════════════════════════════
   HERO — Hebbia-style monumental type
   ═══════════════════════════════════════ */
function Hero() {
  return (
    <section className="relative min-h-screen bg-[#F7F5F0] dark:bg-[#08090C] overflow-hidden flex items-center text-[#111] dark:text-white">
      {/* Gradient orbs */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-[-20%] right-[-10%] w-[800px] h-[800px] rounded-full bg-[#C8A660]/[0.08] dark:bg-[#C8A660]/[0.04] blur-[140px]" />
        <div className="absolute bottom-[-10%] left-[-5%] w-[600px] h-[600px] rounded-full bg-[#818CF8]/[0.06] dark:bg-[#818CF8]/[0.03] blur-[100px]" />
      </div>
      {/* Subtle grid */}
      <div
        className="absolute inset-0 opacity-[0.018]"
        style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.15) 1px, transparent 1px)`,
          backgroundSize: "80px 80px",
        }}
      />

      {/* 3D plates — right side */}
      <HeroPlates opacity={0.55} />

      {/* Fade plates — left, top, bottom all bleed into hero bg */}
      <div className="absolute inset-y-0 right-0 w-[72%] pointer-events-none z-[5]"
        style={{ background: "linear-gradient(to right, rgb(var(--hero-bg-rgb)) 0%, rgb(var(--hero-bg-rgb)) 18%, rgb(var(--hero-bg-rgb) / 0.6) 48%, transparent 70%)" }}
      />
      <div className="absolute top-0 right-0 w-[72%] h-48 pointer-events-none z-[5]"
        style={{ background: "linear-gradient(to bottom, rgb(var(--hero-bg-rgb)) 0%, transparent 100%)" }}
      />
      <div className="absolute bottom-0 right-0 w-[72%] h-48 pointer-events-none z-[5]"
        style={{ background: "linear-gradient(to top, rgb(var(--hero-bg-rgb)) 0%, transparent 100%)" }}
      />

      <div className="max-w-[1400px] mx-auto w-full px-6 md:px-10 pt-32 pb-20 relative z-10">
        {/* Eyebrow */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="mb-10"
        >
          <div className="inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full border border-[#C8A660]/25 bg-[#C8A660]/[0.07]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#C8A660] live-dot shrink-0" />
            <span className="text-[11px] font-mono text-[#C8A660]/90 uppercase tracking-[0.2em]">
              AI for Financial Reporting
            </span>
          </div>
        </motion.div>

        {/* Massive headline — Hebbia style */}
        <motion.h1
          initial={{ opacity: 0, y: 50 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, delay: 0.3, ease: [0.25, 0.1, 0.25, 1] }}
          className="text-[clamp(60px,11vw,148px)] font-normal tracking-[-0.05em] leading-[0.88] mb-8 max-w-[900px]"
          style={{ fontFamily: "var(--font-instrument-serif), Georgia, serif" }}
        >
          Disclosure{" "}
          <br className="hidden md:block" />
          <span className="italic text-[#C8A660]">intelligence.</span>
        </motion.h1>

        {/* Sub */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.6 }}
          className="text-[17px] text-[#6B6B6B] leading-[1.75] max-w-[480px] mb-12"
        >
          Purpose-built AI trusted by leading accounting firms and Fortune 500
          companies for high-stakes FASB compliance. From ERP journal entry to
          signed 10-K.
        </motion.p>

        {/* CTAs */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.8 }}
          className="flex items-center gap-6"
        >
          <a
            href="#cta"
            className="group inline-flex items-center gap-3 px-8 py-3.5 text-[14px] font-medium text-[#08090C] bg-white rounded-full hover:bg-[#C8A660] hover:shadow-[0_0_32px_rgba(200,166,96,0.35)] transition-all duration-300"
          >
            Request a demo{" "}
            <ArrowRight
              size={15}
              className="group-hover:translate-x-0.5 transition-transform"
            />
          </a>
          <a
            href="#platform"
            className="inline-flex items-center gap-2 text-[14px] text-[#6B6B6B] hover:text-[#111] dark:hover:text-white transition-colors duration-300"
          >
            See it work <ArrowRight size={14} />
          </a>
        </motion.div>

        {/* Live tag */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.2, duration: 0.6 }}
          className="mt-20"
        >
          <div className="inline-flex items-center gap-2.5 px-3.5 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 live-dot shrink-0" />
            <span className="text-[11px] font-mono text-emerald-400/80 tracking-wide">
              Processing FY2025 filings under ASU 2023-09
            </span>
          </div>
        </motion.div>
      </div>
    </section>
  );
}


/* ═══════════════════════════════════════
   USE CASE TICKER — Harvey-style giant serif
   ═══════════════════════════════════════ */
function UseCaseTicker() {
  const [active, setActive] = useState(0);
  const cases = [
    "Rate Reconciliation",
    "Jurisdictional Disaggregation",
    "Deferred Tax Schedules",
    "Compliance Validation",
    "10-K Footnote Generation",
    "XBRL Tagging",
  ];

  useEffect(() => {
    const id = setInterval(
      () => setActive((prev) => (prev + 1) % cases.length),
      2500
    );
    return () => clearInterval(id);
  }, [cases.length]);

  return (
    <section className="py-28 md:py-36 bg-[#FAFAFA] overflow-hidden">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-12">
          {/* Left label */}
          <div className="md:w-[260px] shrink-0 pt-2">
            <span className="text-[11px] font-mono text-[#C8A660] uppercase tracking-[0.2em]">
              Capabilities
            </span>
            <p className="text-[14px] text-[#71717A] mt-3 leading-relaxed">
              Tax teams use Truffles for end-to-end disclosure automation.
            </p>
            <a
              href="#platform"
              className="inline-flex items-center gap-2 text-[13px] font-medium text-foreground mt-6 hover:text-[#C8A660] transition-colors"
            >
              Explore Platform <ArrowRight size={13} />
            </a>
          </div>

          {/* Right — giant text list */}
          <div className="flex-1 space-y-1">
            {cases.map((c, i) => (
              <motion.div
                key={c}
                animate={{ opacity: i === active ? 1 : 0.1 }}
                transition={{ duration: 0.5 }}
                className={`cursor-pointer py-1 pl-3 border-l-2 transition-colors duration-500 ${i === active ? "border-[#C8A660]" : "border-transparent"}`}
                onClick={() => setActive(i)}
              >
                <span
                  className="text-[clamp(28px,4.5vw,58px)] tracking-[-0.03em] leading-[1.1] text-foreground block transition-colors duration-500"
                  style={{
                    fontFamily:
                      "var(--font-instrument-serif), Georgia, serif",
                  }}
                >
                  {c}
                </span>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════
   STICKY TABS — Hebbia split layout
   ═══════════════════════════════════════ */
function StickyTabs() {
  const [activeTab, setActiveTab] = useState(0);

  const tabs = [
    {
      label: "Connect your ERP",
      desc: "Ingest GL journal entries from SAP, Oracle, or any ERP, enriched through Google Cloud Cortex and BigQuery.",
      visual: "connect",
    },
    {
      label: "AI Agents analyze",
      desc: "Five specialized agents run in parallel: mapping accounts, computing provisions, and reconciling across jurisdictions.",
      visual: "analyze",
    },
    {
      label: "Compliance checks",
      desc: "Every output validated against ASU 2023-09, ASC 740, and SEC comment letter patterns. 11 automated checks per filing.",
      visual: "compliance",
    },
    {
      label: "File with confidence",
      desc: "Generate audit-ready 10-K footnotes, XBRL tags, and workpapers. Reviewed and signed in hours, not weeks.",
      visual: "file",
    },
  ];

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveTab((prev) => (prev + 1) % tabs.length);
    }, 4000);
    return () => clearInterval(interval);
  }, [tabs.length]);

  return (
    <section id="platform" className="py-28 bg-[#F7F5F0] dark:bg-[#08090C] relative overflow-hidden">
      <HeroPlates opacity={0.10} className="absolute inset-y-0 right-[-22%] w-[60%]" />
      <div className="max-w-[1400px] mx-auto px-6 md:px-10 relative z-10">
        <Reveal>
          <div className="mb-16">
            <span className="text-[11px] font-mono text-[#C8A660]/60 uppercase tracking-[0.2em]">
              How it works
            </span>
            <h2
              className="text-[clamp(32px,4.5vw,52px)] font-normal tracking-[-0.035em] leading-[1.05] text-[#111] dark:text-white mt-4"
              style={{
                fontFamily: "var(--font-instrument-serif), Georgia, serif",
              }}
            >
              Source to 10-K.{" "}
              <span className="italic text-[#C8A660]">Four steps.</span>
            </h2>
          </div>
        </Reveal>

        <div className="grid md:grid-cols-[320px_1fr] gap-12 md:gap-16">
          {/* Left — tab labels */}
          <div className="flex flex-col gap-1">
            {tabs.map((tab, i) => (
              <button
                key={tab.label}
                onClick={() => setActiveTab(i)}
                className="text-left"
              >
                <div className="flex gap-4 py-5 pl-1 pr-4">
                  {/* Step number + connector line */}
                  <div className="flex flex-col items-center shrink-0 pt-0.5">
                    <span
                      className={`text-[10px] font-mono tabular-nums transition-colors duration-500 ${
                        i === activeTab ? "text-[#C8A660]" : "text-[#6B6B6B]/30"
                      }`}
                    >
                      0{i + 1}
                    </span>
                    {i < tabs.length - 1 && (
                      <div className="w-px flex-1 mt-2 bg-[#D4D4D8] dark:bg-[#2A2B2E]" style={{ minHeight: 24 }} />
                    )}
                  </div>

                  {/* Label + desc */}
                  <div className="flex-1">
                    <span
                      className={`text-[17px] tracking-[-0.01em] block transition-colors duration-500 ${
                        i === activeTab ? "text-[#111] dark:text-white font-medium" : "text-[#6B6B6B]/60 dark:text-[#6B6B6B]/50 font-normal"
                      }`}
                    >
                      {tab.label}
                    </span>
                    <AnimatePresence>
                      {i === activeTab && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          transition={{ duration: 0.35 }}
                          className="overflow-hidden"
                        >
                          <p className="text-[13px] text-[#6B6B6B] leading-relaxed mt-2">
                            {tab.desc}
                          </p>
                          <div className="mt-3 h-[2px] bg-[#E4E4E7] dark:bg-[#222326] rounded-full overflow-hidden">
                            <motion.div
                              key={`progress-${activeTab}`}
                              initial={{ width: "0%" }}
                              animate={{ width: "100%" }}
                              transition={{ duration: 4, ease: "linear" }}
                              className="h-full bg-[#C8A660]/60 rounded-full"
                            />
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>
              </button>
            ))}
          </div>

          {/* Right — product panel */}
          <div className="relative min-h-[520px]">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 16, scale: 0.985 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -16, scale: 0.985 }}
                transition={{ duration: 0.45 }}
                className="absolute inset-0"
              >
                {activeTab === 0 && <TabConnect />}
                {activeTab === 1 && <TabAnalyze />}
                {activeTab === 2 && <TabCompliance />}
                {activeTab === 3 && <TabFile />}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </section>
  );
}

/* Shared light panel chrome — kore.ai style */
function Panel({
  title,
  badge,
  badgeColor = "#34D399",
  children,
}: {
  title: string;
  badge?: string;
  badgeColor?: string;
  children: ReactNode;
}) {
  return (
    <div className="h-full flex flex-col rounded-2xl overflow-hidden bg-[#E8EEF6] shadow-[0_8px_40px_rgba(0,0,0,0.18)]">
      {/* Title bar */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-[#D4DCE8] bg-white shrink-0">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#FF5F57]" />
          <span className="w-2.5 h-2.5 rounded-full bg-[#FFBD2E]" />
          <span className="w-2.5 h-2.5 rounded-full bg-[#27C840]" />
        </div>
        <span className="text-[11px] font-mono text-[#9CA3AF] flex-1 text-center -ml-10">
          {title}
        </span>
        {badge && (
          <span
            className="text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full border"
            style={{
              color: badgeColor,
              borderColor: `${badgeColor}40`,
              background: `${badgeColor}15`,
            }}
          >
            {badge}
          </span>
        )}
      </div>
      <div className="flex-1 overflow-hidden">{children}</div>
    </div>
  );
}

/* Shared sidebar used by all tabs */
function PanelSidebar({ items, active = 0, extra }: { items: string[]; active?: number; extra?: ReactNode }) {
  return (
    <div className="w-[130px] border-r border-[#D4DCE8] bg-white flex flex-col py-1 shrink-0">
      {items.map((item, i) => (
        <div
          key={item}
          className={`px-4 py-2.5 text-[11px] font-mono cursor-pointer transition-colors ${
            i === active
              ? "text-[#111] bg-[#EEF3FA] border-l-2 border-[#C8A660] font-medium"
              : "text-[#9CA3AF] hover:text-[#555] hover:bg-[#F5F7FA]"
          }`}
        >
          {item}
        </div>
      ))}
      {extra && <div className="mt-auto">{extra}</div>}
    </div>
  );
}

function TabConnect() {
  const sources = [
    { name: "SAP S/4HANA",      logo: "/logo-sap.jpg",        rows: "1,204", status: "Live" },
    { name: "Oracle EBS",        logo: "/logo-oracle.png",     rows: "847",   status: "Live" },
    { name: "Salesforce",        logo: "/logo-salesforce.jpg", rows: "796",   status: "Syncing" },
    { name: "Google BigQuery",   logo: "/logo-bigquery.png",   rows: "512",   status: "Syncing" },
    { name: "NetSuite",          logo: "/logo-netsuite.jpg",   rows: "—",     status: "Queued" },
    { name: "Snowflake",         logo: "/logo-snowflake.jpg",  rows: "—",     status: "Queued" },
  ];
  const statusColor: Record<string, string> = { Live: "#059669", Syncing: "#C8A660", Queued: "#D1D5DB" };

  return (
    <Panel title="truffles — data sources" badge="2,847 rows" badgeColor="#059669">
      <div className="flex h-full">
        <PanelSidebar items={["Sources", "Mappings", "Schedule", "Logs"]} />
        <div className="flex-1 overflow-y-auto bg-white">
          <div className="flex items-center px-4 py-2 border-b border-[#F0F0F2] bg-[#FAFAFA]">
            <span className="text-[9px] font-mono text-[#C4C4C4] uppercase tracking-widest w-9" />
            <span className="text-[9px] font-mono text-[#C4C4C4] uppercase tracking-widest flex-1">Source</span>
            <span className="text-[9px] font-mono text-[#C4C4C4] uppercase tracking-widest w-16 text-right">Rows</span>
            <span className="text-[9px] font-mono text-[#C4C4C4] uppercase tracking-widest w-16 text-right">Status</span>
          </div>
          {sources.map((s, i) => (
            <motion.div
              key={s.name}
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.06, duration: 0.35 }}
              className="flex items-center px-4 py-3 border-b border-[#F5F5F7] hover:bg-[#FAFAFA] transition-colors group"
            >
              <div className="w-9 shrink-0 flex items-center">
                <div className="w-7 h-7 rounded-md border border-[#F0F0F2] bg-white flex items-center justify-center overflow-hidden">
                  <img src={s.logo} alt={s.name} className="w-6 h-6 object-contain" />
                </div>
              </div>
              <span className="text-[12px] text-[#374151] flex-1 group-hover:text-[#111] transition-colors">
                {s.name}
              </span>
              <span className="text-[11px] font-mono text-[#9CA3AF] w-16 text-right">{s.rows}</span>
              <div className="w-16 flex justify-end items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: statusColor[s.status] }} />
                <span className="text-[10px] font-mono" style={{ color: statusColor[s.status] }}>{s.status}</span>
              </div>
            </motion.div>
          ))}
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}
            className="px-4 py-3 flex items-center gap-2 text-[#C4C4C4] hover:text-[#9CA3AF] cursor-pointer transition-colors"
          >
            <span className="w-5 h-5 rounded border border-dashed border-[#D1D5DB] flex items-center justify-center text-[11px]">+</span>
            <span className="text-[11px]">Add data source</span>
          </motion.div>
        </div>
      </div>
    </Panel>
  );
}

function TabAnalyze() {
  const agents = [
    { name: "Mapping Agent", desc: "Classifying 500+ GL accounts", icon: Search, progress: 87, color: "#818CF8", state: "Running" },
    { name: "Tax Agent", desc: "Computing provisions, 10 jurisdictions", icon: BarChart3, progress: 64, color: "#C8A660", state: "Running" },
    { name: "Reconciliation Agent", desc: "Current vs. deferred tax balances", icon: Activity, progress: 45, color: "#34D399", state: "Running" },
    { name: "Compliance Agent", desc: "ASU 2023-09 requirement validation", icon: Shield, progress: 32, color: "#A78BFA", state: "Queued" },
  ];

  return (
    <Panel title="truffles — agent pipeline" badge="Running" badgeColor="#C8A660">
      <div className="flex h-full">
        <PanelSidebar
          items={["Pipeline", "Logs", "Config", "History"]}
          extra={
            <div className="px-4 pb-4">
              <div className="text-[9px] font-mono text-[#C4C4C4] uppercase tracking-wider mb-1">Run time</div>
              <motion.div
                className="text-[13px] font-mono text-[#C8A660]"
                animate={{ opacity: [1, 0.4, 1] }}
                transition={{ duration: 1.4, repeat: Infinity }}
              >
                00:02:41
              </motion.div>
            </div>
          }
        />
        {/* Steps — kore.ai connected card list */}
        <div className="flex-1 py-5 px-5 overflow-y-auto bg-[#E8EEF6]">
          {agents.map((a, i) => (
            <motion.div
              key={a.name}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1, duration: 0.4 }}
              className="flex gap-3"
            >
              {/* Node + line */}
              <div className="flex flex-col items-center shrink-0 pt-3">
                <div
                  className="w-8 h-8 rounded-full border-2 bg-white flex items-center justify-center shrink-0 shadow-sm"
                  style={{ borderColor: a.color }}
                >
                  <a.icon size={13} style={{ color: a.color }} />
                </div>
                {i < agents.length - 1 && (
                  <div className="w-px bg-[#C8D3E0] flex-1 my-1" style={{ minHeight: 20 }} />
                )}
              </div>
              {/* White card */}
              <div className="flex-1 mb-3 bg-white rounded-xl shadow-sm border border-[#E4EAF2] p-4 hover:shadow-md transition-shadow">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[13px] font-medium text-[#111]">{a.name}</span>
                  <span
                    className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full"
                    style={{ color: a.color, background: `${a.color}15` }}
                  >
                    {a.state}
                  </span>
                </div>
                <p className="text-[11px] text-[#6B7280] mb-3">{a.desc}</p>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1.5 bg-[#EEF3FA] rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${a.progress}%` }}
                      transition={{ delay: i * 0.1 + 0.3, duration: 1, ease: "easeOut" }}
                      className="h-full rounded-full"
                      style={{ background: a.color }}
                    />
                  </div>
                  <span className="text-[10px] font-mono shrink-0 tabular-nums" style={{ color: a.color }}>
                    {a.progress}%
                  </span>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function TabCompliance() {
  const checks = [
    { text: "Rate reconciliation, 8 categories", rule: "ASU 2023-09 §c1", ok: true },
    { text: "Dual format disclosure (% and $)", rule: "ASU 2023-09 §c2", ok: true },
    { text: "Cash taxes paid per-jurisdiction", rule: "ASU 2023-09 §d", ok: true },
    { text: "Jurisdictions above 5% disaggregated", rule: "ASU 2023-09 §e", ok: true },
    { text: "Carryforward schedules complete", rule: "ASC 740-10-50-3", ok: true },
    { text: "Valuation allowance item, in review", rule: "ASC 740-10-30-2", ok: false },
  ];

  return (
    <Panel title="truffles — compliance review" badge="10/11 passed" badgeColor="#C8A660">
      <div className="flex h-full">
        <PanelSidebar
          items={["Checks", "Findings", "History", "Export"]}
          extra={
            <div className="px-4 pb-4">
              <div className="text-[9px] font-mono text-[#C4C4C4] uppercase tracking-wider mb-1">Score</div>
              <div className="text-[26px] font-normal text-emerald-500 leading-none"
                style={{ fontFamily: "var(--font-instrument-serif), Georgia, serif" }}>
                91%
              </div>
            </div>
          }
        />
        <div className="flex-1 overflow-y-auto bg-white">
          <div className="flex items-center px-4 py-2 border-b border-[#F0F0F2] bg-[#FAFAFA]">
            <span className="text-[9px] font-mono text-[#C4C4C4] uppercase tracking-widest flex-1">Check</span>
            <span className="text-[9px] font-mono text-[#C4C4C4] uppercase tracking-widest w-28 text-right hidden md:block">Rule</span>
            <span className="text-[9px] font-mono text-[#C4C4C4] uppercase tracking-widest w-12 text-center">Pass</span>
          </div>
          {checks.map((c, i) => (
            <motion.div
              key={c.text}
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.07, duration: 0.35 }}
              className="flex items-center px-4 py-3 border-b border-[#F5F5F7] hover:bg-[#FAFAFA] transition-colors group"
            >
              <span className="text-[12px] text-[#374151] flex-1 group-hover:text-[#111] transition-colors">{c.text}</span>
              <span className="text-[10px] font-mono text-[#C4C4C4] w-28 text-right hidden md:block">{c.rule}</span>
              <div className="w-12 flex justify-center">
                {c.ok
                  ? <CheckCircle2 size={15} className="text-emerald-500" />
                  : <AlertCircle size={15} className="text-amber-400" />}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function TabFile() {
  const narrative =
    "The Company recorded income tax expense of $75.0M for fiscal year 2025, reflecting an effective tax rate of 25.3%, compared to the U.S. federal statutory rate of 21.0%. The increase was primarily attributable to state and local taxes and the jurisdictional mix of earnings...";
  const [typed, setTyped] = useState("");
  useEffect(() => {
    setTyped("");
    let i = 0;
    const id = setInterval(() => {
      i += 2;
      if (i >= narrative.length) { setTyped(narrative); clearInterval(id); }
      else setTyped(narrative.slice(0, i));
    }, 22);
    return () => clearInterval(id);
  }, [narrative]);

  const outputs = [
    { icon: Globe, label: "XBRL Tags", value: "142", color: "#3B82F6" },
    { icon: Shield, label: "Workpapers", value: "12", color: "#A78BFA" },
    { icon: CheckCircle2, label: "SEC Ready", value: "Yes", color: "#059669" },
  ];

  return (
    <Panel title="truffles — 10-K footnote generator" badge="Generated" badgeColor="#059669">
      <div className="flex h-full">
        <PanelSidebar
          items={["Note 8", "Note 9", "Note 10", "XBRL", "Export"]}
        />
        <div className="flex-1 flex flex-col overflow-hidden bg-white">
          {/* Doc tab bar */}
          <div className="flex items-center border-b border-[#F0F0F2] bg-[#FAFAFA] px-2">
            <div className="px-3 py-2 text-[11px] font-mono text-[#111] border-b-2 border-[#C8A660] bg-white">
              income-taxes.md
            </div>
            <div className="px-3 py-2 text-[11px] font-mono text-[#C4C4C4]">
              rate-recon.xlsx
            </div>
          </div>
          {/* Document body */}
          <div className="flex-1 overflow-y-auto p-5">
            <div className="text-[10px] font-mono text-[#C4C4C4] mb-2 uppercase tracking-wider">
              Note 8. Income Taxes
            </div>
            <p className="text-[12px] text-[#374151] font-mono leading-[1.95]">
              {typed}
              {typed.length < narrative.length && (
                <span
                  className="inline-block w-px h-[13px] bg-[#C8A660] ml-0.5 align-middle"
                  style={{ animation: "blink-cursor 0.8s infinite" }}
                />
              )}
            </p>
          </div>
          {/* Status bar */}
          <div className="border-t border-[#F0F0F2] bg-[#FAFAFA] px-4 py-2.5 flex items-center gap-5">
            {outputs.map((o, i) => (
              <motion.div
                key={o.label}
                initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                transition={{ delay: 0.4 + i * 0.1 }}
                className="flex items-center gap-1.5"
              >
                <o.icon size={11} style={{ color: o.color }} />
                <span className="text-[10px] font-mono text-[#9CA3AF]">
                  {o.label}: <span style={{ color: o.color }}>{o.value}</span>
                </span>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </Panel>
  );
}

/* ═══════════════════════════════════════
   PRODUCT SHOWCASE — Stripe-style floating cards
   ═══════════════════════════════════════ */
function ProductShowcase() {
  const reconRows = [
    { item: "Federal statutory rate", rate: "+21.00%", pos: false },
    { item: "State & local", rate: "+2.10%", pos: false },
    { item: "Ireland — 12.5%", rate: "−1.09%", pos: true },
    { item: "R&D credit — IRC §41", rate: "−0.90%", pos: true },
    { item: "Other adjustments", rate: "+0.59%", pos: false },
  ];

  return (
    <section className="py-28 bg-[#FAFAFA] overflow-hidden">
      <div className="max-w-[1200px] mx-auto px-6 md:px-10">
        <Reveal>
          <div className="text-center mb-16">
            <span className="text-[10px] font-mono text-[#C8A660] uppercase tracking-[0.2em]">
              Live Platform
            </span>
            <h2
              className="text-[clamp(28px,3.5vw,44px)] font-normal tracking-[-0.03em] leading-[1.1] mt-3"
              style={{
                fontFamily: "var(--font-instrument-serif), Georgia, serif",
              }}
            >
              See what your agents{" "}
              <span className="italic text-[#C8A660]">produce.</span>
            </h2>
          </div>
        </Reveal>

        {/* Free-floating cards — no browser chrome */}
        <div className="grid md:grid-cols-[1fr_300px] gap-5">
          {/* Main — Rate Recon */}
          <Reveal>
            <motion.div
              whileHover={{ y: -5, boxShadow: "0 24px 64px rgba(0,0,0,0.07)" }}
              transition={{ duration: 0.3 }}
              className="relative bg-white rounded-2xl border border-[#E4E4E7] p-7 shadow-[0_4px_20px_rgba(0,0,0,0.04)]"
            >
              <div className="absolute top-0 inset-x-0 h-[2px] rounded-t-2xl bg-gradient-to-r from-transparent via-[#C8A660]/70 to-transparent" />
              <div className="grid grid-cols-4 gap-3 mb-6">
                {[
                  { label: "ETR", value: "25.3%", accent: "text-[#C8A660]" },
                  { label: "Provision", value: "$75.0M", accent: "text-[#111]" },
                  { label: "Jurisdictions", value: "10", accent: "text-[#111]" },
                  { label: "Compliance", value: "91%", accent: "text-emerald-600" },
                ].map((kpi) => (
                  <div
                    key={kpi.label}
                    className="bg-[#F8F8F8] rounded-xl p-3.5 border border-[#E4E4E7]/60"
                  >
                    <div className="text-[9px] font-mono text-[#71717A] uppercase tracking-wider mb-1.5">
                      {kpi.label}
                    </div>
                    <div
                      className={`text-[22px] font-normal tracking-tight ${kpi.accent}`}
                      style={{
                        fontFamily:
                          "var(--font-instrument-serif), Georgia, serif",
                      }}
                    >
                      {kpi.value}
                    </div>
                  </div>
                ))}
              </div>
              <div className="bg-[#F8F8F8] rounded-xl border border-[#E4E4E7]/60 overflow-hidden">
                <div className="px-4 py-3 border-b border-[#E4E4E7]/50 flex items-center justify-between">
                  <span className="text-[9px] font-mono text-[#71717A] uppercase tracking-wider">
                    Rate Reconciliation
                  </span>
                  <span className="text-[9px] font-mono text-[#C8A660]/70">
                    FY2025
                  </span>
                </div>
                {reconRows.map((row) => (
                  <div
                    key={row.item}
                    className="flex items-center justify-between px-4 py-2.5 border-b border-[#E4E4E7]/30 last:border-0"
                  >
                    <span className="text-[12px] font-mono text-[#71717A]">
                      {row.item}
                    </span>
                    <span
                      className={`text-[12px] font-mono ${
                        row.pos ? "text-emerald-600" : "text-[#555]"
                      }`}
                    >
                      {row.rate}
                    </span>
                  </div>
                ))}
                <div className="flex items-center justify-between px-4 py-3 bg-[#C8A660]/[0.05]">
                  <span className="text-[12px] font-mono font-medium text-[#111]">
                    Effective tax rate
                  </span>
                  <span className="text-[14px] font-mono font-semibold text-[#C8A660]">
                    25.30%
                  </span>
                </div>
              </div>
            </motion.div>
          </Reveal>

          {/* Side column */}
          <div className="flex flex-col gap-4">
            <Reveal delay={0.1}>
              <motion.div
                whileHover={{ y: -4 }}
                transition={{ duration: 0.3 }}
                className="bg-white rounded-2xl border border-[#E4E4E7] p-5 shadow-[0_4px_20px_rgba(0,0,0,0.04)]"
              >
                <div className="text-[9px] font-mono text-[#71717A] uppercase tracking-wider mb-3">
                  ASU 2023-09
                </div>
                {[
                  { text: "Rate recon, 8 categories", ok: true },
                  { text: "Dual format (% and $)", ok: true },
                  { text: "Cash taxes per-jurisdiction", ok: true },
                  { text: "Jurisdictions ≥5%", ok: true },
                  { text: "VA item in review", ok: false },
                ].map((c) => (
                  <div key={c.text} className="flex items-center gap-2.5 py-2">
                    {c.ok ? (
                      <CheckCircle2
                        size={14}
                        className="text-emerald-500 shrink-0"
                      />
                    ) : (
                      <AlertCircle
                        size={14}
                        className="text-amber-500 shrink-0"
                      />
                    )}
                    <span className="text-[11px] text-[#71717A]">{c.text}</span>
                  </div>
                ))}
              </motion.div>
            </Reveal>

            <Reveal delay={0.15}>
              <motion.div
                whileHover={{ y: -4 }}
                transition={{ duration: 0.3 }}
                className="bg-white rounded-2xl border border-[#E4E4E7] p-5 shadow-[0_4px_20px_rgba(0,0,0,0.04)]"
              >
                <div className="text-[9px] font-mono text-[#71717A] uppercase tracking-wider mb-3">
                  Tax Rate Waterfall
                </div>
                <div className="flex items-end gap-1.5 h-[80px]">
                  {[
                    { h: 64, color: "#818CF8", label: "21%" },
                    { h: 12, color: "#34D399", label: "+2.1" },
                    { h: 18, color: "#EF4444", label: "−2.0" },
                    { h: 8, color: "#FBBF24", label: "+0.7" },
                    { h: 24, color: "#EF4444", label: "−3.5" },
                    { h: 70, color: "#C8A660", label: "25.3%" },
                  ].map((bar, i) => (
                    <div
                      key={i}
                      className="flex-1 flex flex-col items-center gap-1 justify-end"
                    >
                      <div
                        className="w-full rounded-sm opacity-70"
                        style={{ height: bar.h, background: bar.color }}
                      />
                      <span
                        className={`text-[8px] font-mono ${
                          i === 5 ? "text-[#C8A660]" : "text-[#71717A]/40"
                        }`}
                      >
                        {bar.label}
                      </span>
                    </div>
                  ))}
                </div>
              </motion.div>
            </Reveal>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════
   METRICS — Floating numbers on dark canvas
   ═══════════════════════════════════════ */
function Metrics() {
  return (
    <section className="py-28 bg-[#FAFAFA] dark:bg-[#08090C] relative overflow-hidden">
      <HeroPlates opacity={0.08} className="absolute inset-y-0 left-[-22%] w-[60%]" />
      {/* Gold ambient glow — center-top */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: "radial-gradient(ellipse 70% 55% at 50% 0%, rgba(200,166,96,0.12) 0%, rgba(200,166,96,0.04) 50%, transparent 75%)",
        }}
      />
      {/* Concentric circle pattern */}
      <div className="absolute inset-0 pointer-events-none flex items-center justify-center opacity-[0.025]">
        {[...Array(10)].map((_, i) => (
          <div
            key={i}
            className="absolute rounded-full border border-white"
            style={{
              width: `${(i + 1) * 140}px`,
              height: `${(i + 1) * 140}px`,
            }}
          />
        ))}
      </div>

      <div className="max-w-[1400px] mx-auto px-6 md:px-10 relative z-10">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-12 md:gap-0">
          {[
            {
              target: 85,
              suffix: "%",
              label: "Faster disclosure prep",
              sub: "Weeks → hours",
            },
            {
              target: 6,
              suffix: "",
              label: "FASB standards",
              sub: "ASC 740 · 842 · 280 · 606 · 326 · DISE",
            },
            {
              target: 100,
              suffix: "%",
              label: "ASU 2023-09 compliant",
              sub: "Validated against SEC patterns",
            },
            {
              target: 11,
              suffix: "",
              label: "Automated checks",
              sub: "Per filing cycle",
            },
          ].map((m, i) => (
            <Reveal key={m.label} delay={i * 0.1} className="text-center">
              <div
                className="text-[clamp(52px,6.5vw,88px)] font-normal tracking-[-0.04em] leading-none mb-3 metric-num-gradient"
                style={{
                  fontFamily: "var(--font-instrument-serif), Georgia, serif",
                }}
              >
                <Counter target={m.target} suffix={m.suffix} />
              </div>
              <div className="text-[14px] font-medium text-[#555] dark:text-white/60 mb-1">
                {m.label}
              </div>
              <div className="text-[11px] font-mono text-[#6B6B6B]/50">
                {m.sub}
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════
   MODULES — Elevated bento grid
   ═══════════════════════════════════════ */
function Modules() {
  return (
    <section id="modules" className="py-28 max-w-[1400px] mx-auto px-6 md:px-10">
      <Reveal>
        <div className="text-center mb-16">
          <h2
            className="text-[clamp(32px,4.5vw,52px)] font-normal tracking-[-0.035em] leading-[1.05]"
            style={{
              fontFamily: "var(--font-instrument-serif), Georgia, serif",
            }}
          >
            Every critical{" "}
            <span className="italic text-[#C8A660]">FASB standard.</span>
          </h2>
        </div>
      </Reveal>

      <div className="grid md:grid-cols-3 gap-[1px] bg-[#E4E4E7] rounded-2xl overflow-hidden">
        {/* DISE — flagship, spans 2 cols */}
        <Reveal className="md:col-span-2 bg-white p-8 group cursor-pointer relative overflow-hidden transition-colors duration-500 hover:bg-[#FAFAF8]">
          <div className="relative z-10">
            <div className="flex items-center gap-3 mb-5">
              <span className="text-[10px] font-mono text-teal-500 uppercase tracking-widest">
                Flagship
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full border border-red-400/30 text-red-400/80">
                Required by SEC
              </span>
            </div>
            <h3
              className="text-[28px] font-normal tracking-[-0.02em] mb-3"
              style={{ fontFamily: "var(--font-instrument-serif), Georgia, serif" }}
            >
              DISE Mandate
            </h3>
            <p className="text-[14px] text-[#71717A] leading-[1.7] max-w-[420px] mb-6">
              Evidence mapping, gap analysis, and SEC comment risk scoring. The DISE framework sits at the center of every critical FASB standard your team must comply with.
            </p>
            <div className="flex flex-wrap gap-2">
              {["Evidence Map", "Gap Detection", "SEC Risk Score", "Comment Letter AI"].map((t) => (
                <span key={t} className="text-[10px] font-mono px-2.5 py-1 rounded-full border border-teal-500/20 text-teal-500/70">
                  {t}
                </span>
              ))}
            </div>
          </div>
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-teal-400 to-teal-400/0" />
        </Reveal>

        {/* Income Tax */}
        <Reveal className="bg-white p-8 group cursor-pointer relative overflow-hidden transition-colors duration-500 hover:bg-[#FAFAF8]">
          <div className="flex items-center gap-2 mb-5">
            <BarChart3 size={16} className="text-[#C8A660]" />
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full border border-[#C8A660]/25 text-[#C8A660]/60">
              ASC 740
            </span>
          </div>
          <h3
            className="text-[20px] font-normal tracking-[-0.02em] mb-2"
            style={{ fontFamily: "var(--font-instrument-serif), Georgia, serif" }}
          >
            Income Tax Provision
          </h3>
          <p className="text-[13px] text-[#71717A] leading-[1.7]">
            Full ASU 2023-09 compliance: rate reconciliation, jurisdictional disaggregation, and AI-generated footnotes.
          </p>
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-[#C8A660] to-[#C8A660]/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
        </Reveal>

        {/* Segments */}
        <Reveal className="bg-white p-8 group cursor-pointer relative overflow-hidden transition-colors duration-500 hover:bg-[#FAFAF8]">
          <PieChart size={16} className="text-blue-500 mb-5" />
          <span className="text-[10px] font-mono text-[#71717A]/40 block mb-2">ASC 280</span>
          <h3
            className="text-[20px] font-normal tracking-[-0.02em] mb-2"
            style={{ fontFamily: "var(--font-instrument-serif), Georgia, serif" }}
          >
            Segment Reporting
          </h3>
          <p className="text-[13px] text-[#71717A] leading-[1.7]">
            CODM identification and ASU 2023-07 interim disclosures.
          </p>
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-blue-400 to-blue-400/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
        </Reveal>

        {/* Leases */}
        <Reveal className="bg-white p-8 group cursor-pointer relative overflow-hidden transition-colors duration-500 hover:bg-[#FAFAF8]">
          <Building2 size={16} className="text-purple-500 mb-5" />
          <span className="text-[10px] font-mono text-[#71717A]/40 block mb-2">ASC 842</span>
          <h3
            className="text-[20px] font-normal tracking-[-0.02em] mb-2"
            style={{ fontFamily: "var(--font-instrument-serif), Georgia, serif" }}
          >
            Lease Accounting
          </h3>
          <p className="text-[13px] text-[#71717A] leading-[1.7]">
            ROU assets, classification, maturity schedules.
          </p>
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-purple-400 to-purple-400/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
        </Reveal>

        {/* Revenue */}
        <Reveal className="bg-white p-8 group cursor-pointer relative overflow-hidden transition-colors duration-500 hover:bg-[#FAFAF8]">
          <TrendingUp size={16} className="text-emerald-500 mb-5" />
          <span className="text-[10px] font-mono text-[#71717A]/40 block mb-2">ASC 606</span>
          <h3
            className="text-[20px] font-normal tracking-[-0.02em] mb-2"
            style={{ fontFamily: "var(--font-instrument-serif), Georgia, serif" }}
          >
            Revenue
          </h3>
          <p className="text-[13px] text-[#71717A] leading-[1.7]">
            Five-step model compliance and performance obligations.
          </p>
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-emerald-400 to-emerald-400/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
        </Reveal>

        {/* Credit Losses — full width bottom row */}
        <Reveal className="md:col-span-3 bg-white p-8 group cursor-pointer relative overflow-hidden transition-colors duration-500 hover:bg-[#FAFAF8]">
          <div className="flex items-start justify-between">
            <div>
              <Activity size={16} className="text-amber-500 mb-5" />
              <span className="text-[10px] font-mono text-[#71717A]/40 block mb-2">ASC 326</span>
              <h3
                className="text-[20px] font-normal tracking-[-0.02em] mb-2"
                style={{ fontFamily: "var(--font-instrument-serif), Georgia, serif" }}
              >
                Credit Losses
              </h3>
              <p className="text-[13px] text-[#71717A] leading-[1.7] max-w-[420px]">
                CECL modeling, allowance calculation, vintage analysis.
              </p>
            </div>
            <span className="text-[10px] font-mono text-[#71717A]/30 hidden md:block">CECL · ASU 2016-13</span>
          </div>
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-amber-400 to-amber-400/0 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
        </Reveal>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════
   INTEGRATION GRID — Hebbia-style dark card wall
   ═══════════════════════════════════════ */
function IntegrationGrid() {
  const integrations = [
    {
      name: "SAP",
      desc: "S/4HANA, ECC, BPC",
      logo: "/logo-sap.jpg",
    },
    {
      name: "Oracle",
      desc: "EBS, Fusion, HFM",
      logo: "/logo-oracle.png",
    },
    {
      name: "Salesforce",
      desc: "Revenue Cloud, CPQ",
      logo: "/logo-salesforce.jpg",
    },
  ];

  return (
    <section className="py-28 bg-[#F5F5F7]">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <Reveal>
          <div className="text-center mb-16">
            <span className="text-[11px] font-mono text-[#C8A660] uppercase tracking-[0.2em]">
              Connectors
            </span>
            <h2
              className="text-[clamp(28px,3.5vw,44px)] font-normal tracking-[-0.03em] leading-[1.1] text-[#111] mt-4"
              style={{
                fontFamily: "var(--font-instrument-serif), Georgia, serif",
              }}
            >
              The full picture,{" "}
              <span className="italic text-[#C8A660]">always in reach.</span>
            </h2>
            <p className="text-[15px] text-[#71717A] mt-4 max-w-[480px] mx-auto leading-relaxed">
              Connect your ERP and CRM data directly to your disclosure workflows.
            </p>
          </div>
        </Reveal>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 max-w-[860px] mx-auto">
          {integrations.map((item, i) => (
            <Reveal key={item.name} delay={i * 0.08}>
              <motion.div
                whileHover={{ y: -4, boxShadow: "0 20px 48px rgba(0,0,0,0.08)" }}
                transition={{ duration: 0.25 }}
                className="bg-white border border-[#E4E4E7] rounded-2xl p-8 flex flex-col items-center gap-5 cursor-pointer group hover:border-[#C8A660]/40 hover:shadow-[0_8px_32px_rgba(200,166,96,0.10),0_2px_8px_rgba(0,0,0,0.05)] transition-all duration-300"
              >
                <div className="w-full h-14 flex items-center justify-center">
                  <img
                    src={item.logo}
                    alt={item.name}
                    className="max-h-10 max-w-[140px] w-auto object-contain grayscale group-hover:grayscale-0 transition-all duration-300"
                  />
                </div>
                <div className="text-center">
                  <div className="text-[13px] font-medium text-[#555] group-hover:text-[#111] transition-colors duration-300">
                    {item.name}
                  </div>
                  <div className="text-[11px] font-mono text-[#A1A1AA] mt-1">
                    {item.desc}
                  </div>
                </div>
              </motion.div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}


/* ═══════════════════════════════════════
   SECURITY
   ═══════════════════════════════════════ */
function Security() {
  return (
    <section id="security" className="py-28 bg-white border-y border-[#E4E4E7]">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <Reveal>
          <div className="text-center mb-16">
            <h2
              className="text-[clamp(32px,4.5vw,52px)] font-normal tracking-[-0.035em] leading-[1.05]"
              style={{
                fontFamily: "var(--font-instrument-serif), Georgia, serif",
              }}
            >
              Built for teams that{" "}
              <span className="italic text-[#C8A660]">
                can&apos;t get it wrong.
              </span>
            </h2>
          </div>
        </Reveal>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
          {[
            { icon: Shield, title: "SOC 2 Type II", sub: "Certification in progress", color: "#818CF8" },
            { icon: Lock, title: "AES-256 + TLS 1.3", sub: "End-to-end encrypted", color: "#34D399" },
            { icon: Users, title: "Big 4 Compatible", sub: "Audit-ready exports", color: "#C8A660" },
          ].map((card, i) => (
            <Reveal key={card.title} delay={i * 0.08}>
              <div className="group flex flex-col items-center text-center p-8 rounded-2xl border border-[#E8E8EA] bg-gradient-to-b from-[#FAFAFA] to-white hover:border-[#E0E0E2] hover:shadow-[0_12px_40px_rgba(0,0,0,0.07),0_1px_3px_rgba(0,0,0,0.04)] hover:-translate-y-1.5 transition-all duration-300">
                <div
                  className="w-14 h-14 rounded-2xl flex items-center justify-center mb-5 group-hover:scale-110 transition-transform duration-300"
                  style={{ background: `${card.color}12` }}
                >
                  <card.icon size={24} style={{ color: card.color }} />
                </div>
                <div className="text-[15px] font-semibold mb-1">
                  {card.title}
                </div>
                <div className="text-[12px] text-[#71717A] font-mono">
                  {card.sub}
                </div>
              </div>
            </Reveal>
          ))}
        </div>

      </div>
    </section>
  );
}

/* ═══════════════════════════════════════
   Cloud Infrastructure
   ═══════════════════════════════════════ */
function CloudInfra() {
  const clouds = [
    {
      src: "/logo-aws.jpg",
      name: "Amazon Web Services",
      services: ["ECS / EKS", "Lambda", "RDS · S3"],
    },
    {
      src: "/logo-gcp.png",
      name: "Google Cloud",
      services: ["Cloud Run", "BigQuery", "GKE · GCS"],
    },
    {
      src: "/logo-azure.png",
      name: "Microsoft Azure",
      services: ["AKS · Functions", "Azure SQL", "Blob Storage"],
    },
  ];

  return (
    <section className="py-20 bg-[#F7F5F0] dark:bg-[#08090C] border-t border-[#E4E4E7] dark:border-white/[0.06]">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <Reveal>
          <div className="flex flex-col md:flex-row items-start md:items-center gap-12 md:gap-20">
            {/* Text */}
            <div className="md:w-[38%] shrink-0">
              <p className="text-[11px] font-mono tracking-[0.18em] text-[#C8A660] uppercase mb-4">
                Infrastructure
              </p>
              <h2
                className="text-[clamp(24px,2.8vw,34px)] font-normal tracking-[-0.03em] leading-[1.1] text-[#111] dark:text-white mb-4"
                style={{ fontFamily: "var(--font-instrument-serif), Georgia, serif" }}
              >
                Deploy on the cloud{" "}
                <span className="italic text-[#C8A660]">you already trust.</span>
              </h2>
              <p className="text-[13px] text-[#52525B] leading-relaxed">
                Runs on the infrastructure you already use. One deployment, any cloud, fully within your own environment.
              </p>
            </div>

            {/* Logos */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-8 sm:gap-0 divide-y sm:divide-y-0 sm:divide-x divide-[#E4E4E7] dark:divide-white/[0.06] flex-1">
              {clouds.map((cloud) => (
                <div
                  key={cloud.name}
                  className="flex flex-row sm:flex-col items-center sm:items-center gap-5 sm:gap-4 flex-1 px-0 sm:px-8 first:pl-0 last:pr-0"
                >
                  <div className="shrink-0 rounded-xl bg-white w-[160px] h-[64px] flex items-center justify-center shadow-[0_2px_12px_rgba(0,0,0,0.08)] ring-1 ring-black/[0.05]">
                    <img
                      src={cloud.src}
                      alt={cloud.name}
                      className="max-h-10 max-w-[130px] w-auto h-auto object-contain"
                    />
                  </div>
                  <div className="sm:text-center">
                    <p className="text-[13px] font-medium text-[#555] dark:text-white/70 mb-1.5">{cloud.name}</p>
                    <div className="flex flex-col gap-0.5">
                      {cloud.services.map((s) => (
                        <span key={s} className="text-[11px] font-mono text-[#3F3F46]">
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════
   CTA — Cinematic dark
   ═══════════════════════════════════════ */
function CTA() {
  return (
    <section
      id="cta"
      className="py-36 bg-white dark:bg-[#08090C] relative overflow-hidden"
    >
      <HeroPlates opacity={0.08} className="absolute inset-y-0 right-[-20%] w-[55%]" />
      {/* Animated shimmer line */}
      <div className="absolute top-1/2 left-0 right-0 h-px">
        <div className="w-full h-full bg-[#E4E4E7] dark:bg-[#1A1B1E] relative overflow-hidden">
          <motion.div
            animate={{ x: ["-100%", "100%"] }}
            transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
            className="absolute inset-y-0 w-1/4 bg-gradient-to-r from-transparent via-[#C8A660]/25 to-transparent"
          />
        </div>
      </div>

      <div className="max-w-[1400px] mx-auto px-6 md:px-10 relative z-10">
        <Reveal>
          <div className="text-center">
            <h2
              className="text-[clamp(44px,8vw,96px)] font-normal tracking-[-0.04em] leading-[0.9] mb-8 text-[#111] dark:text-white"
              style={{
                fontFamily: "var(--font-instrument-serif), Georgia, serif",
              }}
            >
              <span className="cta-gradient-heading">Close faster.</span>
              <br />
              File <span className="italic text-[#C8A660]">smarter.</span>
            </h2>
            <p className="text-[16px] text-[#6B6B6B] leading-[1.7] mb-12 max-w-[400px] mx-auto">
              See how Truffles reduces disclosure prep from weeks to hours.
            </p>
            <div className="flex items-center justify-center gap-6">
              <a
                href="mailto:hello@truffles.ai"
                className="group inline-flex items-center gap-3 px-8 py-3.5 text-[14px] font-medium text-white bg-[#111] dark:text-[#08090C] dark:bg-white hover:bg-[#C8A660] dark:hover:bg-[#C8A660] hover:text-white rounded-full transition-all duration-300"
              >
                Request a demo{" "}
                <ArrowRight
                  size={15}
                  className="group-hover:translate-x-0.5 transition-transform"
                />
              </a>
              <a
                href="mailto:hello@truffles.ai"
                className="group inline-flex items-center gap-2 text-[14px] text-[#6B6B6B] hover:text-[#111] dark:hover:text-white transition-colors duration-300"
              >
                hello@truffles.ai{" "}
                <ArrowUpRight
                  size={14}
                  className="opacity-0 group-hover:opacity-100 transition-opacity"
                />
              </a>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════
   FOOTER — Rich multi-column
   ═══════════════════════════════════════ */
function Footer() {
  const columns = [
    {
      title: "Platform",
      links: ["Overview", "AI Agents", "Data Pipeline", "Compliance Engine"],
    },
    {
      title: "Modules",
      links: [
        "ASC 740: Income Tax",
        "DISE Mandate",
        "ASC 280: Segments",
        "ASC 842: Leases",
        "ASC 606: Revenue",
        "ASC 326: Credit Losses",
      ],
    },
    {
      title: "Company",
      links: ["About", "Careers", "Security", "Newsroom"],
    },
    {
      title: "Resources",
      links: ["Blog", "Documentation", "API Reference", "Help Center"],
    },
  ];

  return (
    <footer className="bg-[#F5F5F7] dark:bg-[#08090C] border-t border-[#E4E4E7] dark:border-[#1A1B1E] relative overflow-hidden">
      <HeroPlates opacity={0.07} className="absolute inset-y-0 left-[-25%] w-[55%]" />
      <div className="max-w-[1400px] mx-auto px-6 md:px-10 py-16 relative z-10">
        <div className="grid md:grid-cols-[1.5fr_1fr_1fr_1fr_1fr] gap-10 mb-14">
          {/* Brand column */}
          <div>
            <div className="flex items-center gap-3 mb-4">
              <div className="relative w-7 h-7">
                <div className="absolute inset-0 rounded-[6px] bg-[#C8A660]/20" />
                <div className="absolute inset-[2px] rounded-[4px] bg-[#08090C] flex items-center justify-center text-[#C8A660] text-[10px] font-mono font-bold">
                  tf
                </div>
              </div>
              <span className="text-[14px] tracking-[-0.02em] font-medium">
                <span className="text-[#111] dark:text-white">truffles</span>
                <span className="text-[#C8A660]">.ai</span>
              </span>
            </div>
            <p className="text-[13px] text-[#6B6B6B] leading-relaxed max-w-[240px]">
              Purpose-built AI for financial disclosure. From ERP to 10-K, automated.
            </p>
            <div className="flex gap-4 mt-6">
              {["LinkedIn", "X (Twitter)"].map((social) => (
                <a
                  key={social}
                  href="#"
                  className="text-[11px] font-mono text-[#6B6B6B]/40 hover:text-[#6B6B6B] transition-colors"
                >
                  {social}
                </a>
              ))}
            </div>
          </div>

          {/* Link columns */}
          {columns.map((col) => (
            <div key={col.title}>
              <div className="text-[11px] font-mono text-[#6B6B6B]/35 uppercase tracking-widest mb-4">
                {col.title}
              </div>
              <div className="flex flex-col gap-2.5">
                {col.links.map((link) => (
                  <a
                    key={link}
                    href="#"
                    className="text-[13px] text-[#6B6B6B] hover:text-[#111] dark:hover:text-white transition-colors duration-200"
                  >
                    {link}
                  </a>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="pt-8 border-t border-[#E4E4E7] dark:border-[#1A1B1E] flex flex-col sm:flex-row justify-between items-center gap-4">
          <span className="text-[11px] font-mono text-[#71717A] dark:text-[#6B6B6B]/30">
            &copy; 2026 BE Technology Corp. All rights reserved.
          </span>
          <div className="flex gap-6">
            {["Privacy", "Terms", "Security", "Cookies"].map((link) => (
              <a
                key={link}
                href="#"
                className="text-[11px] font-mono text-[#71717A] dark:text-[#6B6B6B]/30 hover:text-[#111] dark:hover:text-[#6B6B6B] transition-colors"
              >
                {link}
              </a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}

/* ═══════════════════════════════════════
   PAGE
   ═══════════════════════════════════════ */
export default function Home() {
  return (
    <>
      <Nav />
      <Hero />
      <UseCaseTicker />
      <StickyTabs />
      <ProductShowcase />
      <Metrics />
      <Modules />
      <IntegrationGrid />
      <Security />
      <CloudInfra />
      <CTA />
      <Footer />
    </>
  );
}
