import type { MetadataRoute } from "next";

const SITE = "https://truffles.ai";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return [
    { url: `${SITE}/`, lastModified: now, changeFrequency: "weekly", priority: 1.0 },
    { url: `${SITE}/#platform`, lastModified: now, changeFrequency: "monthly", priority: 0.9 },
    { url: `${SITE}/#modules`, lastModified: now, changeFrequency: "monthly", priority: 0.9 },
    { url: `${SITE}/#security`, lastModified: now, changeFrequency: "monthly", priority: 0.8 },
  ];
}
