import type { MetadataRoute } from "next";

export const dynamic = "force-static";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Truffles — Agentic FASB Compliance",
    short_name: "Truffles",
    description:
      "Agentic AI for FASB financial disclosure. Automate ASC 740, 842, 280, 606, 326 — from ERP to signed 10-K.",
    start_url: "/",
    display: "standalone",
    background_color: "#08090C",
    theme_color: "#08090C",
    icons: [
      { src: "/favicon.svg", sizes: "any", type: "image/svg+xml" },
      { src: "/apple-icon.png", sizes: "180x180", type: "image/png" },
    ],
    categories: ["business", "productivity", "finance"],
  };
}
