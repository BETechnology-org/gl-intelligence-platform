import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Instrument_Serif } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

const instrumentSerif = Instrument_Serif({
  variable: "--font-instrument-serif",
  weight: "400",
  subsets: ["latin"],
  style: ["normal", "italic"],
  display: "swap",
});

const SITE_URL = "https://truffles.ai";
const SITE_NAME = "Truffles";
const TAGLINE = "Agentic FASB compliance, from ERP to 10-K.";
const DESCRIPTION =
  "Truffles is the agentic AI platform for FASB financial disclosure. Automate ASC 740, 842, 280, 606, 326 and the DISE mandate — from journal entry to signed 10-K, built on Google Cloud Cortex.";

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#F7F5F0" },
    { media: "(prefers-color-scheme: dark)", color: "#08090C" },
  ],
  width: "device-width",
  initialScale: 1,
  colorScheme: "dark light",
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: `${SITE_NAME} — ${TAGLINE}`,
    template: `%s · ${SITE_NAME}`,
  },
  description: DESCRIPTION,
  applicationName: SITE_NAME,
  generator: "Next.js",
  keywords: [
    "FASB compliance",
    "financial disclosure automation",
    "ASU 2023-09",
    "ASC 740",
    "ASC 842",
    "ASC 280",
    "ASC 606",
    "ASC 326",
    "DISE mandate",
    "income tax provision",
    "rate reconciliation",
    "agentic AI",
    "ERP intelligence",
    "SAP S/4HANA",
    "Oracle EBS",
    "Google Cloud Cortex",
    "BigQuery",
    "10-K automation",
    "XBRL tagging",
  ],
  authors: [{ name: "BE Technology Corp", url: SITE_URL }],
  creator: "BE Technology Corp",
  publisher: "BE Technology Corp",
  category: "Enterprise Financial Software",
  alternates: { canonical: SITE_URL },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: SITE_URL,
    siteName: SITE_NAME,
    title: `${SITE_NAME} — ${TAGLINE}`,
    description: DESCRIPTION,
    images: [
      {
        url: "/opengraph-image.png",
        width: 1200,
        height: 630,
        alt: "Truffles — Agentic FASB compliance platform",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: `${SITE_NAME} — ${TAGLINE}`,
    description: DESCRIPTION,
    images: ["/opengraph-image.png"],
    creator: "@truffles_ai",
  },
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon.ico", sizes: "any" },
    ],
    apple: [{ url: "/apple-icon.png", sizes: "180x180", type: "image/png" }],
  },
  manifest: "/manifest.webmanifest",
  formatDetection: { telephone: false, email: false, address: false },
};

const organizationJsonLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "BE Technology Corp",
  url: SITE_URL,
  logo: `${SITE_URL}/favicon.svg`,
  description: DESCRIPTION,
  foundingLocation: { "@type": "Place", address: { "@type": "PostalAddress", addressCountry: "US" } },
  sameAs: [
    "https://www.linkedin.com/company/truffles-ai",
    "https://twitter.com/truffles_ai",
  ],
  brand: { "@type": "Brand", name: SITE_NAME },
};

const softwareJsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: `${SITE_NAME} GL Intelligence`,
  applicationCategory: "BusinessApplication",
  applicationSubCategory: "Financial Disclosure Automation",
  operatingSystem: "Web",
  description: DESCRIPTION,
  url: SITE_URL,
  publisher: { "@type": "Organization", name: "BE Technology Corp" },
  offers: { "@type": "Offer", price: "0", priceCurrency: "USD", availability: "https://schema.org/InStock" },
};

// Inline script to prevent FOUC on theme load — runs before paint, reads
// localStorage / prefers-color-scheme and sets `dark` class on <html>.
const themeScript = `
(function(){try{
  var s = localStorage.getItem('theme');
  var d = s ? s === 'dark' : (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) !== false;
  if (d) document.documentElement.classList.add('dark');
  else document.documentElement.classList.remove('dark');
}catch(e){}})();
`.trim();

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} ${instrumentSerif.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationJsonLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareJsonLd) }}
        />
      </head>
      <body className="min-h-full flex flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[100] focus:px-4 focus:py-2 focus:rounded-full focus:bg-[#111] focus:text-white focus:text-sm focus:shadow-lg"
        >
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
