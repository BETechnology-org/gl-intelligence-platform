import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Instrument_Serif } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const instrumentSerif = Instrument_Serif({
  variable: "--font-instrument-serif",
  weight: "400",
  subsets: ["latin"],
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  title: "Truffles — Agentic Financial Intelligence",
  description:
    "Automate FASB disclosure compliance from ERP to signed 10-K. AI agents for ASC 740, 842, 280, 606, and 326 — built on Google Cloud Cortex.",
  keywords: [
    "FASB compliance",
    "financial disclosure automation",
    "ASC 740",
    "ASC 842",
    "DISE mandate",
    "income tax provision",
    "agentic AI",
    "ERP intelligence",
    "Google Cortex",
    "BigQuery",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${instrumentSerif.variable} h-full antialiased dark`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
