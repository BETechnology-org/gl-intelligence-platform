import { ImageResponse } from "next/og";

export const dynamic = "force-static";
export const alt = "Truffles — Agentic FASB compliance, from ERP to 10-K";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px 80px",
          background:
            "radial-gradient(120% 80% at 88% -10%, rgba(200,166,96,0.35) 0%, rgba(200,166,96,0.00) 55%), radial-gradient(80% 60% at 0% 110%, rgba(184,144,64,0.22) 0%, rgba(11,12,16,0) 55%), #0B0C10",
          color: "white",
          fontFamily: "sans-serif",
          position: "relative",
        }}
      >
        {/* Top bar */}
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: 12,
              background: "linear-gradient(135deg, #1A1B20, #0B0C10)",
              border: "1px solid rgba(200,166,96,0.35)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#E8C878",
              fontSize: 22,
              fontWeight: 700,
              letterSpacing: -1,
            }}
          >
            tf
          </div>
          <div style={{ display: "flex", fontSize: 26, letterSpacing: -0.5 }}>
            <span style={{ color: "white" }}>truffles</span>
            <span style={{ color: "#C8A660" }}>.ai</span>
          </div>
          <div style={{ flex: 1 }} />
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 14px",
              borderRadius: 999,
              border: "1px solid rgba(255,255,255,0.15)",
              color: "rgba(255,255,255,0.7)",
              fontSize: 18,
              letterSpacing: 2,
              textTransform: "uppercase",
              fontFamily: "monospace",
            }}
          >
            <div style={{ width: 8, height: 8, borderRadius: 999, background: "#059669" }} />
            GL Intelligence
          </div>
        </div>

        {/* Headline */}
        <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
          <div
            style={{
              fontSize: 104,
              lineHeight: 1,
              letterSpacing: -4,
              fontWeight: 400,
              fontFamily: "serif",
              maxWidth: 980,
              display: "flex",
              flexWrap: "wrap",
            }}
          >
            <span>Agentic FASB compliance,&nbsp;</span>
            <span style={{ fontStyle: "italic", color: "#E8C878" }}>from ERP to 10-K.</span>
          </div>
          <div
            style={{
              color: "rgba(255,255,255,0.62)",
              fontSize: 26,
              letterSpacing: -0.3,
              maxWidth: 820,
              lineHeight: 1.4,
            }}
          >
            ASC 740 · 842 · 280 · 606 · 326 · DISE — automated, validated, audit-ready.
          </div>
        </div>

        {/* Footer strip */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 32,
            paddingTop: 28,
            borderTop: "1px solid rgba(255,255,255,0.08)",
            color: "rgba(255,255,255,0.5)",
            fontFamily: "monospace",
            fontSize: 18,
            letterSpacing: 3,
            textTransform: "uppercase",
          }}
        >
          <span>SAP · Oracle · NetSuite</span>
          <span style={{ color: "rgba(200,166,96,0.5)" }}>·</span>
          <span>Built on Google Cloud</span>
          <span style={{ color: "rgba(200,166,96,0.5)" }}>·</span>
          <span>ASU 2023-09 Ready</span>
        </div>
      </div>
    ),
    { ...size }
  );
}
