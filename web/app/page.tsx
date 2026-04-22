"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  motion,
  useInView,
  AnimatePresence,
  useReducedMotion,
} from "framer-motion";
import {
  ArrowRight,
  ArrowUpRight,
  Menu,
  X,
  Sun,
  Moon,
  Shield,
  Search,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  Globe,
  Building2,
  BarChart3,
  PieChart,
  Activity,
  FileCheck,
  Clock,
  Lock,
  Plus,
  Minus,
} from "lucide-react";

const HeroPlates = dynamic(() => import("./HeroPlates"), { ssr: false });

/* ═══════════════════════════════════════════════════════════════
   CONSTANTS
   ═══════════════════════════════════════════════════════════════ */
const APP_URL = "https://gl-intelligence-462410669395.us-central1.run.app/app";
const CONTACT_EMAIL = "hello@truffles.ai";
const CAREERS_EMAIL = "careers@truffles.ai";
const SECURITY_EMAIL = "security@truffles.ai";
const SERIF: React.CSSProperties = {
  fontFamily: "var(--font-instrument-serif), Georgia, serif",
};

/* ═══════════════════════════════════════════════════════════════
   SHARED UI
   ═══════════════════════════════════════════════════════════════ */
function Reveal({
  children,
  className = "",
  delay = 0,
  y = 24,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  y?: number;
}) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  const reduce = useReducedMotion();
  return (
    <motion.div
      ref={ref}
      initial={reduce ? { opacity: 1 } : { opacity: 0, y }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.65, delay, ease: [0.25, 0.1, 0.25, 1] }}
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
  duration = 1.3,
}: {
  target: number;
  prefix?: string;
  suffix?: string;
  duration?: number;
}) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const reduce = useReducedMotion();

  useEffect(() => {
    if (!inView) return;
    if (reduce) {
      setCount(target);
      return;
    }
    const start = performance.now();
    const total = duration * 1000;
    let raf = 0;
    const step = (now: number) => {
      const t = Math.min((now - start) / total, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setCount(Math.floor(target * eased));
      if (t < 1) raf = requestAnimationFrame(step);
      else setCount(target);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [inView, target, duration, reduce]);

  return (
    <span ref={ref} className="tabular-nums">
      {prefix}
      {count.toLocaleString()}
      {suffix}
    </span>
  );
}

function SectionEyebrow({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.22em] text-[#C8A660]">
      <span className="inline-block w-4 h-px bg-[#C8A660]/70" />
      {children}
    </span>
  );
}

/* ═══════════════════════════════════════════════════════════════
   NAV
   ═══════════════════════════════════════════════════════════════ */
function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const [dark, setDark] = useState(true);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 24);
    fn();
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  // Lock body scroll when mobile menu is open
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  function toggleTheme() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {}
  }

  const links = [
    { label: "Platform", href: "#platform" },
    { label: "Modules", href: "#modules" },
    { label: "Security", href: "#security" },
    { label: "FAQ", href: "#faq" },
  ];

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-all duration-500 ${
        scrolled
          ? "glass border-b border-black/5 dark:border-white/10"
          : "bg-transparent"
      }`}
      aria-label="Primary"
    >
      <div className="max-w-[1400px] mx-auto px-6 md:px-10 h-[68px] flex items-center justify-between">
        <a href="#top" className="flex items-center gap-3 group" aria-label="Truffles — home">
          <div className="relative w-7 h-7">
            <div className="absolute inset-0 rounded-[6px] bg-[#C8A660]/20 group-hover:bg-[#C8A660]/30 transition-colors" />
            <div className="absolute inset-[2px] rounded-[4px] bg-[#111] flex items-center justify-center text-[#C8A660] text-[11px] font-mono font-bold">
              tf
            </div>
          </div>
          <span className="text-[14px] tracking-[-0.02em] font-medium">
            <span className="text-[#111] dark:text-white">truffles</span>
            <span className="text-[#C8A660]">.ai</span>
          </span>
        </a>

        <nav className="hidden md:flex items-center gap-8" aria-label="Main navigation">
          {links.map((l) => (
            <a
              key={l.label}
              href={l.href}
              className="text-[13px] text-[#52525B] dark:text-[#A1A1AA] hover:text-[#111] dark:hover:text-white transition-colors duration-200"
            >
              {l.label}
            </a>
          ))}
        </nav>

        <div className="hidden md:flex items-center gap-3">
          <button
            onClick={toggleTheme}
            aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
            className="w-8 h-8 flex items-center justify-center rounded-full text-[#71717A] hover:text-[#111] dark:text-[#A1A1AA] dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
          >
            {mounted && (dark ? <Sun size={15} /> : <Moon size={15} />)}
          </button>
          <a
            href={APP_URL}
            className="text-[13px] text-[#52525B] dark:text-[#A1A1AA] hover:text-[#111] dark:hover:text-white transition-colors"
          >
            Sign in
          </a>
          <a
            href="#cta"
            className="inline-flex items-center gap-1.5 text-[13px] font-medium text-white bg-[#111] hover:bg-[#C8A660] dark:text-[#08090C] dark:bg-white dark:hover:bg-[#C8A660] dark:hover:text-white px-5 py-2 rounded-full transition-all duration-300 shadow-[0_1px_2px_rgba(0,0,0,0.08)]"
          >
            Book a demo <ArrowRight size={12} />
          </a>
        </div>

        <div className="md:hidden flex items-center gap-2">
          <button
            onClick={toggleTheme}
            aria-label="Toggle theme"
            className="w-9 h-9 flex items-center justify-center rounded-full text-[#71717A] dark:text-[#A1A1AA]"
          >
            {mounted && (dark ? <Sun size={16} /> : <Moon size={16} />)}
          </button>
          <button
            className="w-9 h-9 flex items-center justify-center rounded-full text-[#52525B] dark:text-[#A1A1AA]"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
          >
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {open && (
          <motion.nav
            id="mobile-menu"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25 }}
            className="md:hidden bg-white dark:bg-[#0D0E12] border-t border-black/5 dark:border-white/10 px-6 py-6 flex flex-col gap-1 shadow-[0_8px_24px_rgba(0,0,0,0.08)]"
            aria-label="Mobile navigation"
          >
            {links.map((l) => (
              <a
                key={l.label}
                href={l.href}
                onClick={() => setOpen(false)}
                className="text-[15px] text-[#27272A] dark:text-white/85 py-2.5 hover:text-[#C8A660] dark:hover:text-[#C8A660] transition-colors"
              >
                {l.label}
              </a>
            ))}
            <div className="h-px bg-black/5 dark:bg-white/10 my-3" />
            <a
              href={APP_URL}
              className="text-[14px] text-[#52525B] dark:text-white/70 py-2.5"
            >
              Sign in
            </a>
            <a
              href="#cta"
              onClick={() => setOpen(false)}
              className="mt-1 text-center text-[14px] font-medium bg-[#111] dark:bg-white text-white dark:text-[#08090C] py-3 rounded-full"
            >
              Book a demo
            </a>
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
  );
}

/* ═══════════════════════════════════════════════════════════════
   HERO
   ═══════════════════════════════════════════════════════════════ */
function Hero() {
  return (
    <section
      id="top"
      className="relative min-h-screen bg-[#F7F5F0] dark:bg-[#08090C] overflow-hidden flex items-center text-[#111] dark:text-white"
    >
      <div className="absolute inset-0 pointer-events-none [background-image:radial-gradient(circle,rgba(0,0,0,0.09)_1px,transparent_1px)] dark:[background-image:radial-gradient(circle,rgba(255,255,255,0.06)_1px,transparent_1px)] [background-size:32px_32px]" />
      <div
        className="absolute top-0 right-0 w-[560px] h-[560px] pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse at top right, rgba(200,166,96,0.10) 0%, transparent 65%)",
        }}
      />

      <HeroPlates opacity={0.5} />

      <div
        className="absolute inset-y-0 right-0 w-[72%] pointer-events-none z-[5]"
        style={{
          background:
            "linear-gradient(to right, rgb(var(--hero-bg-rgb)) 0%, rgb(var(--hero-bg-rgb)) 18%, rgb(var(--hero-bg-rgb) / 0.55) 48%, transparent 70%)",
        }}
      />
      <div
        className="absolute top-0 right-0 w-[72%] h-40 pointer-events-none z-[5]"
        style={{
          background:
            "linear-gradient(to bottom, rgb(var(--hero-bg-rgb)) 0%, transparent 100%)",
        }}
      />
      <div
        className="absolute bottom-0 right-0 w-[72%] h-40 pointer-events-none z-[5]"
        style={{
          background:
            "linear-gradient(to top, rgb(var(--hero-bg-rgb)) 0%, transparent 100%)",
        }}
      />

      <div className="max-w-[1400px] mx-auto w-full px-6 md:px-10 pt-36 pb-24 relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.05 }}
          className="mb-8"
        >
          <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[#C8A660]/30 bg-[#C8A660]/[0.06] text-[11px] font-mono tracking-wide text-[#8B6A2A] dark:text-[#E8C878]">
            <span className="live-dot inline-block w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Now generally available · FY-2025 disclosure season
          </span>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 44 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, delay: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
          className="text-[clamp(58px,10.5vw,142px)] font-normal tracking-[-0.05em] leading-[0.88] mb-7 max-w-[860px]"
          style={SERIF}
        >
          GL{" "}
          <br className="hidden md:block" />
          <span className="italic text-[#C8A660]">intelligence.</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.5 }}
          className="text-[17px] text-[#52525B] dark:text-[#A1A1AA] leading-[1.65] max-w-[520px] mb-10"
        >
          An agentic mesh that takes journal entries through every FASB disclosure standard
          — ASC 740, 842, 280, 606, 326, DISE — and produces audit-ready 10-K workpapers, footnotes,
          and XBRL in hours, not weeks.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.7 }}
          className="flex flex-wrap items-center gap-4 md:gap-6"
        >
          <a
            href="#cta"
            className="group inline-flex items-center gap-3 px-8 py-3.5 text-[14px] font-medium text-white bg-[#111] dark:text-[#08090C] dark:bg-white rounded-full hover:bg-[#C8A660] dark:hover:bg-[#C8A660] dark:hover:text-white hover:shadow-[0_0_32px_rgba(200,166,96,0.30)] transition-all duration-300"
          >
            Book a demo
            <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
          </a>
          <a
            href="#platform"
            className="inline-flex items-center gap-2 text-[14px] text-[#52525B] dark:text-[#A1A1AA] hover:text-[#111] dark:hover:text-white transition-colors duration-200"
          >
            See how it works <ArrowRight size={13} />
          </a>
        </motion.div>

        <motion.ul
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.0, duration: 0.6 }}
          className="flex flex-wrap items-center gap-x-5 gap-y-2 mt-12"
          aria-label="Trust signals"
        >
          {[
            "ASU 2023-09 ready",
            "SOC 2 Type II — in progress",
            "VPC deployment",
            "Source-to-footnote lineage",
          ].map((t) => (
            <li key={t} className="flex items-center gap-1.5">
              <CheckCircle2 size={12} className="text-emerald-500 shrink-0" aria-hidden />
              <span className="text-[11px] font-mono text-[#71717A] dark:text-[#8B8B93]">
                {t}
              </span>
            </li>
          ))}
        </motion.ul>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════
   TRUST / COMPLIANCE STRIP
   ═══════════════════════════════════════════════════════════════ */
function TrustStrip() {
  const items = [
    { label: "ASC 740", sub: "Income Tax" },
    { label: "ASU 2023-09", sub: "Rate Recon" },
    { label: "ASC 842", sub: "Leases" },
    { label: "ASC 280", sub: "Segments" },
    { label: "ASC 606", sub: "Revenue" },
    { label: "ASC 326", sub: "Credit Losses" },
    { label: "XBRL", sub: "US-GAAP Taxonomy" },
  ];
  return (
    <section className="py-10 border-y border-black/5 dark:border-white/5 bg-white dark:bg-[#0A0A0F]">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <span className="text-[11px] font-mono uppercase tracking-[0.22em] text-[#C8A660]/90 shrink-0">
            Native coverage
          </span>
          <ul className="flex flex-wrap items-center gap-x-7 gap-y-3">
            {items.map((i) => (
              <li
                key={i.label}
                className="flex items-baseline gap-2 text-[13px] text-[#27272A] dark:text-white/80"
              >
                <span className="font-medium">{i.label}</span>
                <span className="text-[11px] font-mono text-[#A1A1AA] dark:text-white/35">
                  {i.sub}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════
   USE CASE TICKER
   ═══════════════════════════════════════════════════════════════ */
function UseCaseTicker() {
  const [active, setActive] = useState(0);
  const reduce = useReducedMotion();
  const cases = [
    "Rate Reconciliation",
    "Jurisdictional Disaggregation",
    "Deferred Tax Schedules",
    "Compliance Validation",
    "10-K Footnote Generation",
    "XBRL Tagging",
  ];

  useEffect(() => {
    if (reduce) return;
    const id = setInterval(() => setActive((prev) => (prev + 1) % cases.length), 2500);
    return () => clearInterval(id);
  }, [cases.length, reduce]);

  return (
    <section className="py-28 md:py-36 bg-white dark:bg-[#0A0A0F] overflow-hidden">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-12">
          <div className="md:w-[260px] shrink-0 pt-1">
            <SectionEyebrow>Capabilities</SectionEyebrow>
            <p className="text-[14px] text-[#52525B] dark:text-[#A1A1AA] mt-4 leading-relaxed">
              Every deliverable a tax or financial reporting team owns — handled by a single
              platform, validated against the latest FASB guidance.
            </p>
            <a
              href="#platform"
              className="inline-flex items-center gap-2 text-[13px] font-medium text-[#111] dark:text-white mt-6 hover:text-[#C8A660] dark:hover:text-[#C8A660] transition-colors"
            >
              Explore platform <ArrowRight size={13} />
            </a>
          </div>
          <div className="flex-1 space-y-0.5">
            {cases.map((c, i) => (
              <motion.button
                key={c}
                animate={{ opacity: i === active ? 1 : 0.09 }}
                transition={{ duration: 0.45 }}
                className={`w-full text-left cursor-pointer py-1 pl-3 border-l-2 transition-colors duration-500 ${
                  i === active ? "border-[#C8A660]" : "border-transparent"
                }`}
                onClick={() => setActive(i)}
                aria-pressed={i === active}
              >
                <span
                  className="text-[clamp(26px,4.2vw,56px)] tracking-[-0.03em] leading-[1.1] text-[#111] dark:text-white block"
                  style={SERIF}
                >
                  {c}
                </span>
              </motion.button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════
   GOOGLE CLOUD
   ═══════════════════════════════════════════════════════════════ */
const GC_DOTS = Array.from({ length: 35 }, (_, i) => ({
  x: ((i * 7 + 13) * 17) % 100,
  y: ((i * 11 + 7) * 23) % 100,
  s: 1.5 + ((i * 3 + 1) % 30) / 10,
  d: +((i * 0.17) % 6).toFixed(2),
  t: 3 + ((i * 13) % 50) / 10,
}));

function GoogleCloud() {
  const reduce = useReducedMotion();
  return (
    <section className="relative min-h-[80vh] flex items-center justify-center overflow-hidden bg-[#060608]">
      <motion.div
        className="absolute w-[700px] h-[700px] rounded-full pointer-events-none"
        style={{
          background:
            "radial-gradient(circle, rgba(200,166,96,0.22) 0%, transparent 65%)",
          filter: "blur(130px)",
          top: "-5%",
          left: "8%",
        }}
        animate={reduce ? undefined : { x: [0, 100, -40, 0], y: [0, -60, 30, 0] }}
        transition={{ duration: 22, repeat: Infinity, ease: "linear" }}
      />
      <motion.div
        className="absolute w-[550px] h-[550px] rounded-full pointer-events-none"
        style={{
          background:
            "radial-gradient(circle, rgba(232,200,120,0.15) 0%, transparent 65%)",
          filter: "blur(110px)",
          bottom: "-8%",
          right: "5%",
        }}
        animate={reduce ? undefined : { x: [0, -70, 45, 0], y: [0, 50, -35, 0] }}
        transition={{ duration: 18, repeat: Infinity, ease: "linear" }}
      />
      <motion.div
        className="absolute w-[400px] h-[400px] rounded-full pointer-events-none"
        style={{
          background:
            "radial-gradient(circle, rgba(180,130,40,0.18) 0%, transparent 65%)",
          filter: "blur(90px)",
          top: "30%",
          right: "22%",
        }}
        animate={reduce ? undefined : { x: [0, 55, -45, 0], y: [0, -35, 55, 0] }}
        transition={{ duration: 26, repeat: Infinity, ease: "linear" }}
      />

      <div className="absolute inset-0 [background-image:radial-gradient(circle,rgba(255,255,255,0.035)_1px,transparent_1px)] [background-size:28px_28px] pointer-events-none" />

      <motion.div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[420px] h-[420px] md:w-[620px] md:h-[620px] rounded-full pointer-events-none"
        style={{
          background:
            "conic-gradient(from 0deg, transparent, rgba(200,166,96,0.12), transparent 35%, rgba(200,166,96,0.08), transparent 65%, rgba(200,166,96,0.06), transparent)",
          filter: "blur(50px)",
        }}
        animate={reduce ? undefined : { rotate: 360 }}
        transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
      />

      {!reduce && (
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          {GC_DOTS.map((p, i) => (
            <motion.div
              key={i}
              className="absolute rounded-full bg-[#C8A660]"
              style={{ width: p.s, height: p.s, left: `${p.x}%`, top: `${p.y}%` }}
              animate={{ opacity: [0, 0.5, 0], scale: [0.5, 1.2, 0.5] }}
              transition={{ duration: p.t, delay: p.d, repeat: Infinity }}
            />
          ))}
        </div>
      )}

      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            className="absolute rounded-full border border-[#C8A660]"
            style={{
              width: 280 + i * 160,
              height: 280 + i * 160,
              top: -(280 + i * 160) / 2,
              left: -(280 + i * 160) / 2,
            }}
            animate={
              reduce
                ? undefined
                : { opacity: [0, 0.05 - i * 0.01, 0], scale: [0.97, 1, 1.03] }
            }
            transition={{ duration: 5, delay: i * 1.2, repeat: Infinity }}
          />
        ))}
      </div>

      <div className="relative z-10 text-center px-6 md:px-10 max-w-[1400px] mx-auto">
        <Reveal>
          <h2
            className="text-[clamp(56px,11vw,140px)] font-normal tracking-[-0.05em] leading-[0.85] text-white"
            style={SERIF}
          >
            Intelligence
            <br />
            <span className="italic text-[#C8A660]">at scale.</span>
          </h2>
          <p className="text-[14px] text-white/35 mt-7 max-w-[340px] mx-auto leading-relaxed">
            Built on Google Cloud. Deployed in your VPC. Your data never leaves your tenancy.
          </p>
        </Reveal>

        <Reveal delay={0.2}>
          <div className="flex flex-wrap items-center justify-center gap-6 md:gap-8 mt-16 opacity-45 hover:opacity-80 transition-opacity duration-700">
            <img
              src="/logo-gcp.png"
              className="h-5 object-contain brightness-0 invert"
              alt="Google Cloud"
              loading="lazy"
            />
            <div className="w-px h-4 bg-white/15" />
            <div className="flex items-center gap-2">
              <img
                src="/logo-bigquery.png"
                className="h-5 object-contain brightness-0 invert"
                alt="BigQuery"
                loading="lazy"
              />
              <span className="text-[11px] font-mono text-white/45">BigQuery</span>
            </div>
            <div className="w-px h-4 bg-white/15" />
            <span className="text-[11px] font-mono text-white/45">Cortex Framework</span>
            <div className="w-px h-4 bg-white/15" />
            <span className="text-[11px] font-mono text-white/45">VPC-SC Compatible</span>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════
   STICKY TABS — "Source to 10-K in four steps"
   ═══════════════════════════════════════════════════════════════ */
function StickyTabs() {
  const [activeTab, setActiveTab] = useState(0);
  const reduce = useReducedMotion();

  const tabs = [
    {
      label: "Connect your ERP",
      desc:
        "Journal entries from SAP S/4HANA, Oracle EBS, NetSuite or Workday stream into BigQuery through Cortex. Normalized, enriched, and queryable within the first day.",
      visual: "connect",
    },
    {
      label: "Agents analyze",
      desc:
        "Seven specialized agents run in parallel against live BigQuery data — classifying accounts, computing provisions, reconciling jurisdictions, and flagging anomalies before they reach your auditor.",
      visual: "analyze",
    },
    {
      label: "Compliance checks",
      desc:
        "Every output is validated against ASU 2023-09, ASC 740, and historical SEC comment letter patterns. Eleven automated checks per filing, with full pass/fail evidence.",
      visual: "compliance",
    },
    {
      label: "File with confidence",
      desc:
        "Audit-ready 10-K footnotes, XBRL tags, and workpapers generated with source-to-disclosure traceability. Review in hours, not weeks.",
      visual: "file",
    },
  ];

  useEffect(() => {
    if (reduce) return;
    const interval = setInterval(
      () => setActiveTab((prev) => (prev + 1) % tabs.length),
      4000,
    );
    return () => clearInterval(interval);
  }, [tabs.length, reduce]);

  return (
    <section
      id="platform"
      className="py-28 bg-white dark:bg-[#0A0A0F] relative overflow-hidden scroll-mt-20"
    >
      <HeroPlates opacity={0.08} className="absolute inset-y-0 right-[-22%] w-[60%]" />
      <div className="max-w-[1400px] mx-auto px-6 md:px-10 relative z-10">
        <Reveal>
          <div className="mb-16">
            <SectionEyebrow>How it works</SectionEyebrow>
            <h2
              className="text-[clamp(32px,4.5vw,52px)] font-normal tracking-[-0.035em] leading-[1.05] text-[#111] dark:text-white mt-4"
              style={SERIF}
            >
              Source to 10-K.{" "}
              <span className="italic text-[#C8A660]">Four steps.</span>
            </h2>
          </div>
        </Reveal>

        <div className="grid md:grid-cols-[320px_1fr] gap-12 md:gap-16">
          <div className="flex flex-col gap-1">
            {tabs.map((tab, i) => (
              <button
                key={tab.label}
                onClick={() => setActiveTab(i)}
                className="text-left"
                aria-pressed={i === activeTab}
              >
                <div className="flex gap-4 py-5 pl-1 pr-4">
                  <div className="flex flex-col items-center shrink-0 pt-0.5">
                    <span
                      className={`text-[10px] font-mono tabular-nums transition-colors duration-500 ${
                        i === activeTab ? "text-[#C8A660]" : "text-[#6B6B6B]/30"
                      }`}
                    >
                      0{i + 1}
                    </span>
                    {i < tabs.length - 1 && (
                      <div
                        className="w-px flex-1 mt-2 bg-[#D4D4D8] dark:bg-[#2A2B2E]"
                        style={{ minHeight: 24 }}
                      />
                    )}
                  </div>
                  <div className="flex-1">
                    <span
                      className={`text-[17px] tracking-[-0.01em] block transition-colors duration-500 ${
                        i === activeTab
                          ? "text-[#111] dark:text-white font-medium"
                          : "text-[#6B6B6B]/60 dark:text-[#6B6B6B]/40 font-normal"
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
                          <p className="text-[13px] text-[#52525B] dark:text-[#A1A1AA] leading-relaxed mt-2">
                            {tab.desc}
                          </p>
                          {!reduce && (
                            <div className="mt-3 h-[2px] bg-[#E4E4E7] dark:bg-[#222326] rounded-full overflow-hidden">
                              <motion.div
                                key={`progress-${activeTab}`}
                                initial={{ width: "0%" }}
                                animate={{ width: "100%" }}
                                transition={{ duration: 4, ease: "linear" }}
                                className="h-full bg-[#C8A660]/60 rounded-full"
                              />
                            </div>
                          )}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>
              </button>
            ))}
          </div>

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

/* ── Panel Chrome ─── */
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
    <div className="h-full flex flex-col rounded-2xl overflow-hidden bg-[#E8EEF6] shadow-[0_8px_40px_rgba(0,0,0,0.18)] ring-1 ring-black/5">
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

function PanelSidebar({
  items,
  active = 0,
  extra,
}: {
  items: string[];
  active?: number;
  extra?: ReactNode;
}) {
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
    { name: "SAP S/4HANA", logo: "/logo-sap.jpg", rows: "1,204", status: "Live" },
    { name: "Oracle EBS", logo: "/logo-oracle.png", rows: "847", status: "Live" },
    { name: "Salesforce", logo: "/logo-salesforce.jpg", rows: "796", status: "Syncing" },
    { name: "Google BigQuery", logo: "/logo-bigquery.png", rows: "512", status: "Syncing" },
    { name: "NetSuite", logo: "/logo-netsuite.jpg", rows: "—", status: "Queued" },
    { name: "Snowflake", logo: "/logo-snowflake.jpg", rows: "—", status: "Queued" },
  ];
  const statusColor: Record<string, string> = {
    Live: "#059669",
    Syncing: "#C8A660",
    Queued: "#D1D5DB",
  };

  return (
    <Panel title="truffles · data sources" badge="2,847 rows" badgeColor="#059669">
      <div className="flex h-full">
        <PanelSidebar items={["Sources", "Mappings", "Schedule", "Logs"]} />
        <div className="flex-1 overflow-y-auto bg-white">
          <div className="flex items-center px-4 py-2 border-b border-[#F0F0F2] bg-[#FAFAFA]">
            <span className="text-[9px] font-mono text-[#C4C4C4] uppercase tracking-widest w-9" />
            <span className="text-[9px] font-mono text-[#C4C4C4] uppercase tracking-widest flex-1">
              Source
            </span>
            <span className="text-[9px] font-mono text-[#C4C4C4] uppercase tracking-widest w-16 text-right">
              Rows
            </span>
            <span className="text-[9px] font-mono text-[#C4C4C4] uppercase tracking-widest w-16 text-right">
              Status
            </span>
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
                  <img
                    src={s.logo}
                    alt=""
                    aria-hidden
                    className="w-6 h-6 object-contain"
                    loading="lazy"
                  />
                </div>
              </div>
              <span className="text-[12px] text-[#374151] flex-1 group-hover:text-[#111] transition-colors">
                {s.name}
              </span>
              <span className="text-[11px] font-mono text-[#9CA3AF] w-16 text-right">
                {s.rows}
              </span>
              <div className="w-16 flex justify-end items-center gap-1.5">
                <span
                  className="w-1.5 h-1.5 rounded-full shrink-0"
                  style={{ background: statusColor[s.status] }}
                />
                <span
                  className="text-[10px] font-mono"
                  style={{ color: statusColor[s.status] }}
                >
                  {s.status}
                </span>
              </div>
            </motion.div>
          ))}
          <div className="px-4 py-3 flex items-center gap-2 text-[#C4C4C4] hover:text-[#9CA3AF] cursor-pointer transition-colors">
            <span className="w-5 h-5 rounded border border-dashed border-[#D1D5DB] flex items-center justify-center">
              <Plus size={11} />
            </span>
            <span className="text-[11px]">Add data source</span>
          </div>
        </div>
      </div>
    </Panel>
  );
}

function TabAnalyze() {
  const agents = [
    {
      name: "Mapping Agent",
      desc: "Classifying 500+ GL accounts",
      icon: Search,
      progress: 87,
      color: "#818CF8",
      state: "Running",
    },
    {
      name: "Tax Agent",
      desc: "Computing provisions across 10 jurisdictions",
      icon: BarChart3,
      progress: 64,
      color: "#C8A660",
      state: "Running",
    },
    {
      name: "Reconciliation Agent",
      desc: "Current vs. deferred tax balances",
      icon: Activity,
      progress: 45,
      color: "#34D399",
      state: "Running",
    },
    {
      name: "Compliance Agent",
      desc: "ASU 2023-09 requirement validation",
      icon: Shield,
      progress: 32,
      color: "#A78BFA",
      state: "Queued",
    },
  ];

  return (
    <Panel title="truffles · agent pipeline" badge="Running" badgeColor="#C8A660">
      <div className="flex h-full">
        <PanelSidebar
          items={["Pipeline", "Logs", "Config", "History"]}
          extra={
            <div className="px-4 pb-4">
              <div className="text-[9px] font-mono text-[#C4C4C4] uppercase tracking-wider mb-1">
                Run time
              </div>
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
        <div className="flex-1 py-5 px-5 overflow-y-auto bg-[#E8EEF6]">
          {agents.map((a, i) => (
            <motion.div
              key={a.name}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1, duration: 0.4 }}
              className="flex gap-3"
            >
              <div className="flex flex-col items-center shrink-0 pt-3">
                <div
                  className="w-8 h-8 rounded-full border-2 bg-white flex items-center justify-center shrink-0 shadow-sm"
                  style={{ borderColor: a.color }}
                >
                  <a.icon size={13} style={{ color: a.color }} />
                </div>
                {i < agents.length - 1 && (
                  <div
                    className="w-px bg-[#C8D3E0] flex-1 my-1"
                    style={{ minHeight: 20 }}
                  />
                )}
              </div>
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
                      transition={{
                        delay: i * 0.1 + 0.3,
                        duration: 1,
                        ease: "easeOut",
                      }}
                      className="h-full rounded-full"
                      style={{ background: a.color }}
                    />
                  </div>
                  <span
                    className="text-[10px] font-mono shrink-0 tabular-nums"
                    style={{ color: a.color }}
                  >
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
    <Panel title="truffles · compliance review" badge="10/11 passed" badgeColor="#C8A660">
      <div className="flex h-full">
        <PanelSidebar
          items={["Checks", "Findings", "History", "Export"]}
          extra={
            <div className="px-4 pb-4">
              <div className="text-[9px] font-mono text-[#C4C4C4] uppercase tracking-wider mb-1">
                Score
              </div>
              <div
                className="text-[26px] font-normal text-emerald-500 leading-none"
                style={SERIF}
              >
                91%
              </div>
            </div>
          }
        />
        <div className="flex-1 overflow-y-auto bg-white">
          <div className="flex items-center px-4 py-2 border-b border-[#F0F0F2] bg-[#FAFAFA]">
            <span className="text-[9px] font-mono text-[#C4C4C4] uppercase tracking-widest flex-1">
              Check
            </span>
            <span className="text-[9px] font-mono text-[#C4C4C4] uppercase tracking-widest w-28 text-right hidden md:block">
              Rule
            </span>
            <span className="text-[9px] font-mono text-[#C4C4C4] uppercase tracking-widest w-12 text-center">
              Pass
            </span>
          </div>
          {checks.map((c, i) => (
            <motion.div
              key={c.text}
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.07, duration: 0.35 }}
              className="flex items-center px-4 py-3 border-b border-[#F5F5F7] hover:bg-[#FAFAFA] transition-colors group"
            >
              <span className="text-[12px] text-[#374151] flex-1 group-hover:text-[#111] transition-colors">
                {c.text}
              </span>
              <span className="text-[10px] font-mono text-[#C4C4C4] w-28 text-right hidden md:block">
                {c.rule}
              </span>
              <div className="w-12 flex justify-center">
                {c.ok ? (
                  <CheckCircle2 size={15} className="text-emerald-500" />
                ) : (
                  <AlertCircle size={15} className="text-amber-400" />
                )}
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
  const reduce = useReducedMotion();

  useEffect(() => {
    if (reduce) {
      setTyped(narrative);
      return;
    }
    setTyped("");
    let i = 0;
    const id = setInterval(() => {
      i += 2;
      if (i >= narrative.length) {
        setTyped(narrative);
        clearInterval(id);
      } else setTyped(narrative.slice(0, i));
    }, 22);
    return () => clearInterval(id);
  }, [narrative, reduce]);

  const outputs = [
    { icon: Globe, label: "XBRL Tags", value: "142", color: "#3B82F6" },
    { icon: Shield, label: "Workpapers", value: "12", color: "#A78BFA" },
    { icon: CheckCircle2, label: "SEC Ready", value: "Yes", color: "#059669" },
  ];

  return (
    <Panel title="truffles · footnote generator" badge="Generated" badgeColor="#059669">
      <div className="flex h-full">
        <PanelSidebar items={["Note 8", "Note 9", "Note 10", "XBRL", "Export"]} />
        <div className="flex-1 flex flex-col overflow-hidden bg-white">
          <div className="flex items-center border-b border-[#F0F0F2] bg-[#FAFAFA] px-2">
            <div className="px-3 py-2 text-[11px] font-mono text-[#111] border-b-2 border-[#C8A660] bg-white">
              income-taxes.md
            </div>
            <div className="px-3 py-2 text-[11px] font-mono text-[#C4C4C4]">
              rate-recon.xlsx
            </div>
          </div>
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
          <div className="border-t border-[#F0F0F2] bg-[#FAFAFA] px-4 py-2.5 flex items-center gap-5">
            {outputs.map((o, i) => (
              <motion.div
                key={o.label}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
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

/* ═══════════════════════════════════════════════════════════════
   PRODUCT SHOWCASE
   ═══════════════════════════════════════════════════════════════ */
function ProductShowcase() {
  const reconRows = [
    { item: "Federal statutory rate", rate: "+21.00%", pos: false },
    { item: "State & local", rate: "+2.10%", pos: false },
    { item: "Ireland, 12.5%", rate: "−1.09%", pos: true },
    { item: "R&D credit (IRC §41)", rate: "−0.90%", pos: true },
    { item: "Other adjustments", rate: "+0.59%", pos: false },
  ];

  return (
    <section className="py-28 bg-[#FAFAFA] dark:bg-[#08090C] overflow-hidden">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <Reveal>
          <div className="mb-16 max-w-[620px]">
            <SectionEyebrow>Live platform</SectionEyebrow>
            <h2
              className="text-[clamp(28px,3.5vw,44px)] font-normal tracking-[-0.03em] leading-[1.1] mt-4 text-[#111] dark:text-white"
              style={SERIF}
            >
              Every number,{" "}
              <span className="italic text-[#C8A660]">
                traceable to a source row.
              </span>
            </h2>
            <p className="text-[15px] text-[#52525B] dark:text-[#A1A1AA] mt-5 leading-[1.7]">
              Drill from a footnote back to a journal entry in two clicks. The full
              lineage — source, agent, prompt, and review status — is preserved for
              your auditors.
            </p>
          </div>
        </Reveal>

        <div className="grid md:grid-cols-[1fr_300px] gap-5">
          <Reveal>
            <motion.div
              whileHover={{ y: -4, boxShadow: "0 24px 64px rgba(0,0,0,0.07)" }}
              transition={{ duration: 0.3 }}
              className="relative bg-white dark:bg-[#111214] rounded-2xl p-7 shadow-[0_2px_16px_rgba(0,0,0,0.05)] dark:shadow-[0_2px_24px_rgba(0,0,0,0.4)]"
            >
              <div className="absolute top-0 inset-x-0 h-[2px] rounded-t-2xl bg-gradient-to-r from-transparent via-[#C8A660]/70 to-transparent" />
              <div className="grid grid-cols-4 gap-3 mb-6">
                {[
                  { label: "ETR", value: "25.3%", accent: "text-[#C8A660]" },
                  {
                    label: "Provision",
                    value: "$75.0M",
                    accent: "text-[#111] dark:text-white",
                  },
                  {
                    label: "Jurisdictions",
                    value: "10",
                    accent: "text-[#111] dark:text-white",
                  },
                  { label: "Compliance", value: "91%", accent: "text-emerald-600" },
                ].map((kpi) => (
                  <div
                    key={kpi.label}
                    className="bg-[#F8F8F8] dark:bg-white/5 rounded-xl p-3.5"
                  >
                    <div className="text-[9px] font-mono text-[#71717A] uppercase tracking-wider mb-1.5">
                      {kpi.label}
                    </div>
                    <div
                      className={`text-[22px] font-normal tracking-tight ${kpi.accent}`}
                      style={SERIF}
                    >
                      {kpi.value}
                    </div>
                  </div>
                ))}
              </div>
              <div className="bg-[#F8F8F8] dark:bg-white/5 rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b border-[#E4E4E7]/50 dark:border-white/10 flex items-center justify-between">
                  <span className="text-[9px] font-mono text-[#71717A] uppercase tracking-wider">
                    Rate reconciliation
                  </span>
                  <span className="text-[9px] font-mono text-[#C8A660]/70">
                    FY2025
                  </span>
                </div>
                {reconRows.map((row) => (
                  <div
                    key={row.item}
                    className="flex items-center justify-between px-4 py-2.5 border-b border-[#E4E4E7]/30 dark:border-white/5 last:border-0"
                  >
                    <span className="text-[12px] font-mono text-[#71717A]">
                      {row.item}
                    </span>
                    <span
                      className={`text-[12px] font-mono ${
                        row.pos ? "text-emerald-600" : "text-[#555] dark:text-white/60"
                      }`}
                    >
                      {row.rate}
                    </span>
                  </div>
                ))}
                <div className="flex items-center justify-between px-4 py-3 bg-[#C8A660]/[0.05]">
                  <span className="text-[12px] font-mono font-medium text-[#111] dark:text-white">
                    Effective tax rate
                  </span>
                  <span className="text-[14px] font-mono font-semibold text-[#C8A660]">
                    25.30%
                  </span>
                </div>
              </div>
            </motion.div>
          </Reveal>

          <div className="flex flex-col gap-4">
            <Reveal delay={0.1}>
              <motion.div
                whileHover={{ y: -3 }}
                transition={{ duration: 0.3 }}
                className="bg-white dark:bg-[#111214] rounded-2xl p-5 shadow-[0_2px_16px_rgba(0,0,0,0.05)] dark:shadow-[0_2px_16px_rgba(0,0,0,0.3)]"
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
                        aria-hidden
                      />
                    ) : (
                      <AlertCircle
                        size={14}
                        className="text-amber-500 shrink-0"
                        aria-hidden
                      />
                    )}
                    <span className="text-[11px] text-[#71717A]">{c.text}</span>
                  </div>
                ))}
              </motion.div>
            </Reveal>

            <Reveal delay={0.15}>
              <motion.div
                whileHover={{ y: -3 }}
                transition={{ duration: 0.3 }}
                className="bg-white dark:bg-[#111214] rounded-2xl p-5 shadow-[0_2px_16px_rgba(0,0,0,0.05)] dark:shadow-[0_2px_16px_rgba(0,0,0,0.3)]"
              >
                <div className="text-[9px] font-mono text-[#71717A] uppercase tracking-wider mb-3">
                  Tax rate waterfall
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

/* ═══════════════════════════════════════════════════════════════
   QUOTE
   ═══════════════════════════════════════════════════════════════ */
function Quote() {
  return (
    <section className="py-20 md:py-24 bg-[#111] relative overflow-hidden">
      <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-[#C8A660]/35 to-transparent" />
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <div className="grid md:grid-cols-[1fr_300px] gap-12 md:gap-20 items-center">
          <div>
            <div
              className="text-[100px] leading-none text-[#C8A660]/15 -ml-2 mb-1 select-none"
              style={SERIF}
              aria-hidden
            >
              &#8220;
            </div>
            <blockquote
              className="text-[clamp(18px,2.4vw,26px)] font-normal text-white/90 leading-[1.55] tracking-[-0.015em]"
              style={SERIF}
            >
              Our 740 package used to take three weeks and a pair of late nights at
              the printer. This quarter we closed it before the audit open meeting —
              with a cleaner rate recon than we&apos;ve ever filed.
            </blockquote>
            <figcaption className="flex items-center gap-4 mt-8">
              <div className="w-8 h-px bg-[#C8A660]/40" />
              <div>
                <div className="text-[13px] text-white/70 font-medium">
                  VP, Tax Reporting
                </div>
                <div className="text-[11px] font-mono text-[#C8A660]/60 mt-0.5">
                  Fortune 100 technology company
                </div>
              </div>
            </figcaption>
          </div>

          <Reveal>
            <div className="text-right">
              <div className="text-[10px] font-mono text-[#C8A660]/60 uppercase tracking-[0.2em] mb-3">
                Time saved
              </div>
              <div
                className="text-[clamp(64px,9vw,112px)] font-normal tracking-[-0.05em] leading-none metric-num-gradient"
                style={SERIF}
              >
                3×
              </div>
              <div className="text-[14px] text-white/40 mt-3 font-mono">
                faster close cycle
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════
   METRICS
   ═══════════════════════════════════════════════════════════════ */
function Metrics() {
  return (
    <section className="py-28 bg-[#FAFAFA] dark:bg-[#08090C] relative overflow-hidden">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10 relative z-10">
        <div className="grid md:grid-cols-[1fr_380px] gap-16 md:gap-24 items-start">
          <Reveal>
            <SectionEyebrow>By the numbers</SectionEyebrow>
            <div
              className="text-[clamp(88px,13vw,172px)] font-normal tracking-[-0.06em] leading-none mt-3 metric-num-gradient"
              style={SERIF}
            >
              <Counter target={85} suffix="%" />
            </div>
            <h3
              className="text-[clamp(20px,2.4vw,28px)] font-normal tracking-[-0.025em] text-[#111] dark:text-white mt-3 leading-[1.25]"
              style={SERIF}
            >
              Faster close. Not days faster.
              <br />
              <span className="italic text-[#C8A660]">Weeks faster.</span>
            </h3>
            <p className="text-[14px] text-[#52525B] dark:text-[#A1A1AA] mt-5 leading-relaxed max-w-[440px]">
              Fortune 500 controllers spend 3–5 weeks per quarter on disclosure prep.
              Truffles customers close in under one, with audit-quality evidence on
              every line.
            </p>
          </Reveal>

          <div className="flex flex-col gap-2">
            {[
              {
                target: 6,
                suffix: "",
                label: "FASB standards covered",
                sub: "ASC 740 · 842 · 280 · 606 · 326 · DISE",
              },
              {
                target: 100,
                suffix: "%",
                label: "ASU 2023-09 coverage",
                sub: "Validated against SEC comment letter patterns",
              },
              {
                target: 11,
                suffix: "",
                label: "Automated checks per filing",
                sub: "With pass/fail evidence + workpaper trace",
              },
            ].map((m, i) => (
              <Reveal key={m.label} delay={i * 0.1}>
                <div className="py-5">
                  <div
                    className="text-[clamp(40px,5vw,60px)] font-normal tracking-[-0.04em] leading-none metric-num-gradient"
                    style={SERIF}
                  >
                    <Counter target={m.target} suffix={m.suffix} />
                  </div>
                  <div className="text-[14px] font-medium text-[#27272A] dark:text-white/75 mt-2">
                    {m.label}
                  </div>
                  <div className="text-[11px] font-mono text-[#71717A]/60 mt-1">
                    {m.sub}
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════
   MODULES
   ═══════════════════════════════════════════════════════════════ */
function Modules() {
  const modules = [
    {
      span: "md:col-span-2",
      icon: Globe,
      color: "#C8A660",
      badge: "Flagship",
      badgeExtra: "Required by SEC",
      standard: "",
      title: "DISE Mandate",
      desc:
        "Evidence mapping, gap analysis, and SEC comment risk scoring. DISE sits at the center of every standard you need to comply with — and is the first regulator to actually enforce disaggregation.",
      tags: ["Evidence Map", "Gap Detection", "SEC Risk Score", "Comment Letter AI"],
      stat: "11 automated checks",
    },
    {
      span: "",
      icon: BarChart3,
      color: "#C8A660",
      badge: "ASC 740",
      standard: "ASU 2023-09",
      title: "Income Tax Provision",
      desc:
        "Rate reconciliation, jurisdictional disaggregation, footnote generation. Full ASU 2023-09 coverage with pre-built SEC comment letter heuristics.",
      tags: [],
      stat: "40+ disclosure items",
    },
    {
      span: "",
      icon: PieChart,
      color: "#C8A660",
      badge: "ASC 280",
      standard: "ASU 2023-07",
      title: "Segment Reporting",
      desc:
        "CODM identification, significant expense categories, and ASU 2023-07 interim disclosures — assembled from your existing management reporting.",
      tags: [],
      stat: "CODM analysis",
    },
    {
      span: "",
      icon: Building2,
      color: "#C8A660",
      badge: "ASC 842",
      standard: "IFRS 16 ready",
      title: "Lease Accounting",
      desc:
        "ROU asset classification, maturity schedules, and quantitative/qualitative disclosures — refreshed every close with live lease data.",
      tags: [],
      stat: "ROU + maturity",
    },
    {
      span: "",
      icon: TrendingUp,
      color: "#C8A660",
      badge: "ASC 606",
      standard: "IFRS 15 ready",
      title: "Revenue",
      desc:
        "Five-step model compliance, performance obligation tracking, and variable consideration disclosures at contract granularity.",
      tags: [],
      stat: "5-step model",
    },
    {
      span: "md:col-span-2",
      icon: Activity,
      color: "#C8A660",
      badge: "ASC 326",
      standard: "CECL · ASU 2016-13",
      title: "Credit Losses",
      desc:
        "CECL modeling, allowance calculations, and vintage analysis across loan and receivable portfolios. Supports quantitative disclosures and roll-forward schedules.",
      tags: [],
      stat: "Vintage analysis",
    },
  ];

  return (
    <section id="modules" className="py-28 max-w-[1400px] mx-auto px-6 md:px-10 scroll-mt-20">
      <Reveal>
        <div className="text-center mb-16">
          <SectionEyebrow>Standards</SectionEyebrow>
          <h2
            className="text-[clamp(32px,4.5vw,52px)] font-normal tracking-[-0.035em] leading-[1.05] text-[#111] dark:text-white mt-4"
            style={SERIF}
          >
            Every critical{" "}
            <span className="italic text-[#C8A660]">FASB standard.</span>
          </h2>
        </div>
      </Reveal>

      <div className="grid md:grid-cols-3 gap-4">
        {modules.map((m, i) => (
          <Reveal key={m.title} delay={i * 0.05} className={m.span}>
            <motion.div
              whileHover={{ y: -6 }}
              transition={{ duration: 0.3 }}
              className="group h-full cursor-pointer relative overflow-hidden rounded-2xl p-7 bg-white dark:bg-[#111214] shadow-[0_2px_16px_rgba(0,0,0,0.05)] dark:shadow-[0_2px_16px_rgba(0,0,0,0.3)] hover:shadow-[0_20px_56px_rgba(0,0,0,0.10)] transition-all duration-[400ms]"
            >
              <div
                className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none rounded-2xl"
                style={{
                  background: `radial-gradient(ellipse at top left, ${m.color}09 0%, transparent 60%)`,
                }}
              />
              <div
                className="absolute left-0 top-6 bottom-6 w-[3px] rounded-r-full opacity-0 group-hover:opacity-100 transition-opacity duration-[400ms]"
                style={{ background: m.color }}
              />

              <div className="relative z-10 h-full flex flex-col">
                <div className="flex items-start justify-between mb-5">
                  <div
                    className="w-11 h-11 rounded-xl flex items-center justify-center transition-colors duration-300"
                    style={{ background: `${m.color}14` }}
                  >
                    <m.icon size={20} style={{ color: m.color }} />
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span
                      className="text-[9px] font-mono uppercase tracking-wider px-2.5 py-1 rounded-full font-medium"
                      style={{ color: m.color, background: `${m.color}12` }}
                    >
                      {m.badge}
                    </span>
                    {m.badgeExtra && (
                      <span className="text-[9px] font-mono px-2 py-0.5 rounded-full text-red-400/90 bg-red-400/[0.08]">
                        {m.badgeExtra}
                      </span>
                    )}
                    {m.standard && !m.badgeExtra && (
                      <span className="text-[9px] font-mono text-[#A1A1AA]">
                        {m.standard}
                      </span>
                    )}
                  </div>
                </div>

                <h3
                  className="text-[20px] font-normal tracking-[-0.02em] mb-2 text-[#111] dark:text-white"
                  style={SERIF}
                >
                  {m.title}
                </h3>
                <p className="text-[13px] text-[#52525B] dark:text-[#A1A1AA] leading-[1.7] flex-1">
                  {m.desc}
                </p>

                {m.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-4">
                    {m.tags.map((t) => (
                      <span
                        key={t}
                        className="text-[9px] font-mono px-2 py-1 rounded-md"
                        style={{ color: m.color, background: `${m.color}0f` }}
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                )}

                <div className="mt-5 pt-4 flex items-center justify-between">
                  <span className="text-[10px] font-mono text-[#A1A1AA]">{m.stat}</span>
                  <ArrowRight
                    size={14}
                    className="transition-all duration-300 group-hover:translate-x-1"
                    style={{ color: `${m.color}60` }}
                  />
                </div>
              </div>
            </motion.div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════
   DEPLOYMENT TIMELINE
   ═══════════════════════════════════════════════════════════════ */
function DeploymentTimeline() {
  const steps = [
    {
      icon: Lock,
      week: "Week 1",
      title: "Kickoff & security review",
      desc:
        "Deploy into your GCP or AWS tenancy. Security review with your team (SOC 2 docs, DPIA, model card). Cortex connectors to SAP/Oracle provisioned.",
    },
    {
      icon: Search,
      week: "Week 2",
      title: "Historical reconciliation",
      desc:
        "Mapping agents ingest prior-year GL. Rate recon, segment data, and lease schedules back-tested against your last 10-K. Your controller reviews every mapping.",
    },
    {
      icon: FileCheck,
      week: "Week 3",
      title: "Pilot close",
      desc:
        "Shadow-run your next quarterly close. Side-by-side outputs against your existing process. No production impact, full audit trail.",
    },
    {
      icon: Clock,
      week: "Week 4+",
      title: "Production",
      desc:
        "Go live for your next close cycle. Controller-in-the-loop approvals. Continuous monitoring for regulatory changes and new SEC comment patterns.",
    },
  ];

  return (
    <section
      id="deploy"
      className="py-28 bg-white dark:bg-[#0A0A0F] border-y border-black/5 dark:border-white/5 scroll-mt-20"
    >
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <Reveal>
          <div className="grid md:grid-cols-[1fr_520px] gap-12 md:gap-20 items-end mb-16">
            <div>
              <SectionEyebrow>Onboarding</SectionEyebrow>
              <h2
                className="text-[clamp(28px,3.5vw,44px)] font-normal tracking-[-0.035em] leading-[1.1] text-[#111] dark:text-white mt-4"
                style={SERIF}
              >
                From signed MSA{" "}
                <span className="italic text-[#C8A660]">to production, in a month.</span>
              </h2>
            </div>
            <p className="text-[15px] text-[#52525B] dark:text-[#A1A1AA] leading-[1.7]">
              Dedicated deployment team. Your data never leaves your cloud. A controller-in-the-loop
              by default — Truffles never files on its own.
            </p>
          </div>
        </Reveal>

        <div className="grid md:grid-cols-4 gap-4">
          {steps.map((s, i) => (
            <Reveal key={s.week} delay={i * 0.06}>
              <div className="relative bg-[#FAFAFA] dark:bg-white/5 rounded-2xl p-6 h-full overflow-hidden">
                <div className="absolute top-0 left-0 h-[2px] w-full">
                  <div
                    className="h-full bg-[#C8A660]"
                    style={{ width: `${(i + 1) * 25}%` }}
                  />
                </div>
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-9 h-9 rounded-xl bg-[#C8A660]/12 flex items-center justify-center">
                    <s.icon size={16} className="text-[#C8A660]" />
                  </div>
                  <span className="text-[10px] font-mono uppercase tracking-widest text-[#C8A660]">
                    {s.week}
                  </span>
                </div>
                <h3
                  className="text-[17px] font-normal tracking-[-0.015em] text-[#111] dark:text-white mb-2"
                  style={SERIF}
                >
                  {s.title}
                </h3>
                <p className="text-[12.5px] text-[#52525B] dark:text-[#A1A1AA] leading-[1.6]">
                  {s.desc}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════
   INTEGRATION GRID
   ═══════════════════════════════════════════════════════════════ */
function IntegrationGrid() {
  const integrations = [
    { name: "SAP", desc: "S/4HANA · ECC · BPC", logo: "/logo-sap.jpg" },
    { name: "Oracle", desc: "EBS · Fusion · HFM", logo: "/logo-oracle.png" },
    { name: "Salesforce", desc: "Revenue Cloud · CPQ", logo: "/logo-salesforce.jpg" },
    { name: "BigQuery", desc: "Data warehouse · Cortex", logo: "/logo-bigquery.png" },
    { name: "NetSuite", desc: "ERP · SuiteTax", logo: "/logo-netsuite.jpg" },
    { name: "Snowflake", desc: "Data cloud · streams", logo: "/logo-snowflake.jpg" },
    { name: "AWS", desc: "S3 · RDS · Lambda", logo: "/logo-aws.jpg" },
    { name: "Google Cloud", desc: "Cloud Run · GKE", logo: "/logo-gcp.png" },
    { name: "Azure", desc: "AKS · SQL · Synapse", logo: "/logo-azure.png" },
  ];

  return (
    <section
      id="integrations"
      className="py-28 bg-[#F5F5F7] dark:bg-[#0A0A0F] scroll-mt-20"
    >
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <Reveal>
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-14">
            <div>
              <SectionEyebrow>Ecosystem</SectionEyebrow>
              <h2
                className="text-[clamp(28px,3.5vw,44px)] font-normal tracking-[-0.03em] leading-[1.1] text-[#111] dark:text-white mt-4"
                style={SERIF}
              >
                Works with the stack{" "}
                <span className="italic text-[#C8A660]">you already have.</span>
              </h2>
            </div>
            <p className="text-[14px] text-[#52525B] dark:text-[#A1A1AA] max-w-[300px] leading-relaxed shrink-0">
              Certified connectors to every major ERP, data warehouse, and cloud. No middleware,
              no new data lake required.
            </p>
          </div>
        </Reveal>

        <div className="grid grid-cols-3 gap-3 md:gap-4">
          {integrations.map((item, i) => (
            <Reveal key={item.name} delay={i * 0.04}>
              <motion.div
                whileHover={{ y: -3 }}
                transition={{ duration: 0.2 }}
                className="bg-white dark:bg-[#111214] rounded-xl p-5 md:p-6 flex flex-col items-center gap-3 group shadow-[0_2px_12px_rgba(0,0,0,0.04)] hover:shadow-[0_8px_32px_rgba(200,166,96,0.10)] transition-all duration-300"
              >
                <div className="w-full h-9 flex items-center justify-center">
                  <img
                    src={item.logo}
                    alt={item.name}
                    loading="lazy"
                    className="max-h-7 max-w-[100px] w-auto object-contain grayscale opacity-60 group-hover:grayscale-0 group-hover:opacity-100 transition-all duration-[350ms]"
                  />
                </div>
                <div className="text-center">
                  <div className="text-[12px] font-medium text-[#27272A] dark:text-white/60 group-hover:text-[#111] dark:group-hover:text-white transition-colors duration-300">
                    {item.name}
                  </div>
                  <div className="text-[10px] font-mono text-[#A1A1AA] mt-0.5 hidden md:block">
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

/* ═══════════════════════════════════════════════════════════════
   SECURITY
   ═══════════════════════════════════════════════════════════════ */
function Security() {
  const pillars = [
    {
      icon: Shield,
      title: "SOC 2 Type II",
      desc: "In-progress with a Big 4 auditor. Bridge letter available on request.",
    },
    {
      icon: Lock,
      title: "Private cloud deployment",
      desc: "Runs inside your GCP or AWS tenancy. Your data never leaves your VPC.",
    },
    {
      icon: FileCheck,
      title: "Full audit trail",
      desc:
        "Every agent decision, prompt, and output is logged with cryptographic chain of custody.",
    },
    {
      icon: Globe,
      title: "SOX · GDPR · CCPA",
      desc:
        "Sub-processors documented, DPAs in place, data residency in US or EU on request.",
    },
  ];

  return (
    <section id="security" className="py-28 bg-white dark:bg-[#111214] scroll-mt-20">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10">
        <div className="grid md:grid-cols-[1fr_1.1fr] gap-16 md:gap-28 items-start">
          <Reveal>
            <SectionEyebrow>Security</SectionEyebrow>
            <h2
              className="text-[clamp(28px,3.5vw,44px)] font-normal tracking-[-0.035em] leading-[1.1] text-[#111] dark:text-white mt-4 mb-6"
              style={SERIF}
            >
              Built for teams where{" "}
              <span className="italic text-[#C8A660]">a single error matters.</span>
            </h2>
            <p className="text-[15px] text-[#52525B] dark:text-[#A1A1AA] leading-[1.75] max-w-[420px]">
              Disclosures are binding legal documents. The infrastructure should reflect
              that — defense-in-depth, private deployment, and full evidence for every
              number that reaches the filing.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <a
                href={`mailto:${SECURITY_EMAIL}?subject=Security%20review%20request`}
                className="inline-flex items-center gap-2 text-[13px] font-medium text-[#111] dark:text-white hover:text-[#C8A660] dark:hover:text-[#C8A660] transition-colors"
              >
                Request security package <ArrowUpRight size={13} />
              </a>
              <span className="text-[11px] font-mono text-[#A1A1AA]">
                · SIG Lite · CAIQ · SOC 2 bridge
              </span>
            </div>
          </Reveal>

          <Reveal delay={0.1}>
            <div className="grid sm:grid-cols-2 gap-3">
              {pillars.map((p) => (
                <div
                  key={p.title}
                  className="rounded-2xl p-5 bg-[#FAFAFA] dark:bg-white/5 border border-black/5 dark:border-white/5"
                >
                  <div className="w-9 h-9 rounded-xl bg-[#C8A660]/12 flex items-center justify-center mb-3">
                    <p.icon size={16} className="text-[#C8A660]" />
                  </div>
                  <h3 className="text-[14px] font-medium text-[#111] dark:text-white mb-1.5">
                    {p.title}
                  </h3>
                  <p className="text-[12px] text-[#52525B] dark:text-[#A1A1AA] leading-[1.6]">
                    {p.desc}
                  </p>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════
   FAQ
   ═══════════════════════════════════════════════════════════════ */
function FAQ() {
  const [open, setOpen] = useState<number | null>(0);
  const faqs: { q: string; a: ReactNode }[] = [
    {
      q: "How long does deployment take?",
      a: (
        <>
          Most customers reach a shadow pilot in <strong>three weeks</strong> and
          full production by the following quarterly close. The cadence is: Week 1
          security + connectors, Week 2 historical reconciliation, Week 3 shadow
          close, Week 4 go-live.
        </>
      ),
    },
    {
      q: "Where does my data live? Does it ever leave my cloud?",
      a: (
        <>
          Truffles deploys <strong>inside your GCP or AWS tenancy</strong>. GL data
          stays in your BigQuery project. Claude inference runs via Anthropic on
          Bedrock (AWS) or GCP Model Garden — your choice. No training data ever
          leaves your environment.
        </>
      ),
    },
    {
      q: "How are outputs made audit-ready?",
      a: (
        <>
          Every footnote, rate-recon row, and XBRL tag is bound to the exact source
          rows that produced it. The full lineage — source, agent, prompt, approver
          — is exportable as workpapers in native format, aligned to your audit
          firm&apos;s requirements.
        </>
      ),
    },
    {
      q: "Can the AI file on its own?",
      a: (
        <>
          No — by design. Every material output routes through a{" "}
          <strong>controller-in-the-loop approval queue</strong>. Truffles drafts
          and validates; humans approve and file.
        </>
      ),
    },
    {
      q: "Do you support ERPs beyond SAP and Oracle?",
      a: (
        <>
          Yes. Native connectors for <strong>SAP S/4HANA, ECC, Oracle EBS, Fusion,
          NetSuite, Workday, Sage Intacct</strong>, and anything queryable from
          Snowflake or BigQuery. Custom GL schemas are supported via our mapping
          agent.
        </>
      ),
    },
    {
      q: "How is pricing structured?",
      a: (
        <>
          Annual subscription, tiered by{" "}
          <strong>number of reporting entities and standards</strong> in scope.
          Contact us for a tailored quote — most Fortune 500 deployments land
          between mid-six and low-seven figures annually.
        </>
      ),
    },
  ];

  return (
    <section id="faq" className="py-28 bg-[#F7F5F0] dark:bg-[#08090C] scroll-mt-20">
      <div className="max-w-[1000px] mx-auto px-6 md:px-10">
        <Reveal>
          <div className="text-center mb-14">
            <SectionEyebrow>FAQ</SectionEyebrow>
            <h2
              className="text-[clamp(32px,4vw,48px)] font-normal tracking-[-0.035em] leading-[1.05] text-[#111] dark:text-white mt-4"
              style={SERIF}
            >
              Procurement{" "}
              <span className="italic text-[#C8A660]">questions, answered.</span>
            </h2>
          </div>
        </Reveal>

        <div className="divide-y divide-black/8 dark:divide-white/10 border-y border-black/8 dark:border-white/10">
          {faqs.map((f, i) => {
            const isOpen = open === i;
            return (
              <div key={f.q}>
                <button
                  onClick={() => setOpen(isOpen ? null : i)}
                  className="w-full flex items-center justify-between gap-6 py-5 text-left group"
                  aria-expanded={isOpen}
                  aria-controls={`faq-panel-${i}`}
                >
                  <span
                    className="text-[17px] md:text-[19px] tracking-[-0.015em] text-[#111] dark:text-white group-hover:text-[#C8A660] dark:group-hover:text-[#C8A660] transition-colors"
                    style={SERIF}
                  >
                    {f.q}
                  </span>
                  <span className="w-8 h-8 rounded-full border border-black/10 dark:border-white/15 flex items-center justify-center text-[#52525B] dark:text-[#A1A1AA] shrink-0 group-hover:border-[#C8A660]/50 transition-colors">
                    {isOpen ? <Minus size={14} /> : <Plus size={14} />}
                  </span>
                </button>
                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      key="panel"
                      id={`faq-panel-${i}`}
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
                      className="overflow-hidden"
                    >
                      <p className="pb-6 pr-14 text-[14px] md:text-[15px] text-[#52525B] dark:text-[#A1A1AA] leading-[1.75]">
                        {f.a}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </div>

        <p className="text-center text-[13px] text-[#71717A] dark:text-[#8B8B93] mt-10">
          More questions? Email{" "}
          <a
            href={`mailto:${CONTACT_EMAIL}`}
            className="text-[#C8A660] hover:underline underline-offset-4"
          >
            {CONTACT_EMAIL}
          </a>
          .
        </p>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════
   CTA
   ═══════════════════════════════════════════════════════════════ */
function CTA() {
  return (
    <section
      id="cta"
      className="py-36 bg-[#F7F5F0] dark:bg-[#08090C] relative overflow-hidden scroll-mt-20"
    >
      <HeroPlates
        opacity={0.08}
        scale={0.55}
        className="absolute inset-y-[-20%] right-[-15%] w-[55%]"
      />
      <div className="absolute top-1/2 left-0 right-0 h-px">
        <div className="w-full h-full bg-[#E0DDD8] dark:bg-[#1A1B1E] relative overflow-hidden">
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
              style={SERIF}
            >
              <span className="cta-gradient-heading">Close faster.</span>
              <br />
              File <span className="italic text-[#C8A660]">smarter.</span>
            </h2>
            <p className="text-[16px] text-[#52525B] dark:text-[#A1A1AA] leading-[1.7] mb-12 max-w-[460px] mx-auto">
              A 30-minute walkthrough with our founding team. We&apos;ll tailor the demo
              to your ERP, standards in scope, and audit calendar.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-4 md:gap-6">
              <a
                href={`mailto:${CONTACT_EMAIL}?subject=Truffles%20demo%20request`}
                className="group inline-flex items-center gap-3 px-8 py-3.5 text-[14px] font-medium text-white bg-[#111] dark:text-[#08090C] dark:bg-white hover:bg-[#C8A660] dark:hover:bg-[#C8A660] hover:text-white rounded-full transition-all duration-300 shadow-[0_1px_2px_rgba(0,0,0,0.08)]"
              >
                Book a demo
                <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
              </a>
              <a
                href={`mailto:${SECURITY_EMAIL}?subject=Security%20review%20package`}
                className="group inline-flex items-center gap-2 px-6 py-3.5 text-[14px] text-[#27272A] dark:text-white/80 border border-black/10 dark:border-white/15 rounded-full hover:border-[#C8A660] dark:hover:border-[#C8A660] hover:text-[#C8A660] transition-all duration-300"
              >
                Request security package
                <ArrowUpRight size={13} className="group-hover:-translate-y-0.5 group-hover:translate-x-0.5 transition-transform" />
              </a>
            </div>

            <div className="mt-10 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-[11px] font-mono text-[#71717A] dark:text-[#8B8B93]">
              <span>No credit card required</span>
              <span className="w-1 h-1 rounded-full bg-[#C8A660]/50" />
              <span>30-minute call</span>
              <span className="w-1 h-1 rounded-full bg-[#C8A660]/50" />
              <span>NDA on request</span>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════════════════════════
   FOOTER
   ═══════════════════════════════════════════════════════════════ */
function Footer() {
  const columns = [
    {
      title: "Platform",
      links: [
        { label: "Overview", href: "#platform" },
        { label: "AI Agents", href: "#platform" },
        { label: "Data Pipeline", href: "#integrations" },
        { label: "Compliance Engine", href: "#security" },
        { label: "Deployment", href: "#deploy" },
      ],
    },
    {
      title: "Modules",
      links: [
        { label: "ASC 740 · Income Tax", href: "#modules" },
        { label: "DISE Mandate", href: "#modules" },
        { label: "ASC 280 · Segments", href: "#modules" },
        { label: "ASC 842 · Leases", href: "#modules" },
        { label: "ASC 606 · Revenue", href: "#modules" },
        { label: "ASC 326 · Credit Losses", href: "#modules" },
      ],
    },
    {
      title: "Company",
      links: [
        { label: "Contact", href: `mailto:${CONTACT_EMAIL}` },
        { label: "Careers", href: `mailto:${CAREERS_EMAIL}?subject=Careers%20inquiry` },
        { label: "Security", href: "#security" },
        { label: "FAQ", href: "#faq" },
      ],
    },
    {
      title: "Resources",
      links: [
        { label: "Sign in", href: APP_URL },
        {
          label: "Documentation",
          href: `mailto:${CONTACT_EMAIL}?subject=Documentation%20access`,
        },
        {
          label: "API Reference",
          href: `mailto:${CONTACT_EMAIL}?subject=API%20access`,
        },
        { label: "Status", href: `mailto:${CONTACT_EMAIL}?subject=Status%20inquiry` },
      ],
    },
  ];

  const legal = [
    { label: "Privacy", href: `mailto:${CONTACT_EMAIL}?subject=Privacy%20policy` },
    { label: "Terms", href: `mailto:${CONTACT_EMAIL}?subject=Terms%20of%20service` },
    { label: "Security", href: "#security" },
    { label: "DPA", href: `mailto:${SECURITY_EMAIL}?subject=DPA%20request` },
  ];

  return (
    <footer className="bg-[#F5F5F7] dark:bg-[#08090C] relative overflow-hidden">
      <div className="max-w-[1400px] mx-auto px-6 md:px-10 py-16 relative z-10">
        <div className="grid md:grid-cols-[1.5fr_1fr_1fr_1fr_1fr] gap-10 mb-14">
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
            <p className="text-[13px] text-[#52525B] dark:text-[#8B8B93] leading-relaxed max-w-[260px]">
              Agentic AI for financial disclosure. From ERP to signed 10-K.
            </p>
            <div className="flex gap-4 mt-6">
              <a
                href="https://www.linkedin.com/company/truffles-ai"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[11px] font-mono text-[#71717A] hover:text-[#111] dark:hover:text-white transition-colors"
              >
                LinkedIn
              </a>
              <a
                href="https://twitter.com/truffles_ai"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[11px] font-mono text-[#71717A] hover:text-[#111] dark:hover:text-white transition-colors"
              >
                X (Twitter)
              </a>
            </div>
          </div>

          {columns.map((col) => (
            <div key={col.title}>
              <div className="text-[10px] font-mono text-[#71717A] dark:text-[#6B6B6B] uppercase tracking-widest mb-4">
                {col.title}
              </div>
              <div className="flex flex-col gap-2.5">
                {col.links.map((link) => (
                  <a
                    key={link.label}
                    href={link.href}
                    className="text-[13px] text-[#52525B] dark:text-[#A1A1AA] hover:text-[#111] dark:hover:text-white transition-colors duration-200"
                  >
                    {link.label}
                  </a>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="pt-8 border-t border-black/5 dark:border-white/5 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <span className="text-[11px] font-mono text-[#71717A] dark:text-[#6B6B6B]">
            © {new Date().getFullYear()} BE Technology Corp. All rights reserved.
          </span>
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            {legal.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="text-[11px] font-mono text-[#71717A] dark:text-[#6B6B6B] hover:text-[#111] dark:hover:text-[#A1A1AA] transition-colors"
              >
                {link.label}
              </a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}

/* ═══════════════════════════════════════════════════════════════
   PAGE
   ═══════════════════════════════════════════════════════════════ */
export default function Home() {
  return (
    <>
      <Nav />
      <main id="main">
        <Hero />
        <TrustStrip />
        <UseCaseTicker />
        <GoogleCloud />
        <StickyTabs />
        <ProductShowcase />
        <Quote />
        <Metrics />
        <Modules />
        <DeploymentTimeline />
        <IntegrationGrid />
        <Security />
        <FAQ />
        <CTA />
      </main>
      <Footer />
    </>
  );
}
