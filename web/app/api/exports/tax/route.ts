import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { Document, Packer, Paragraph, Table, TableCell, TableRow, HeadingLevel, TextRun, WidthType, AlignmentType } from "docx";

import { createClient } from "@/utils/supabase/server";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import type { TaxCategory } from "@/lib/api";

export const runtime = "nodejs";

const STATUTORY_RATE = 0.21;
const fmtMillions = (n: number) => `$${(n / 1_000_000).toFixed(1)}M`;
const fmtPct = (n: number) => `${(n * 100).toFixed(2)}%`;

interface ApprovedRow {
  gl_account: string;
  description: string;
  posting_amount: number | string;
  tax_category: TaxCategory;
  tax_category_label: string;
  asc_citation: string | null;
  reviewer: string;
  reviewed_at: string;
}

export async function GET(req: NextRequest) {
  const cookieStore = await cookies();
  const supabase = createClient(cookieStore);
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return new NextResponse("unauthorized", { status: 401 });

  const url = new URL(req.url);
  const companyId = url.searchParams.get("company_id");
  const fiscalYear = url.searchParams.get("fiscal_year");
  const format = (url.searchParams.get("format") ?? "csv").toLowerCase();
  if (!companyId || !fiscalYear) {
    return new NextResponse("company_id + fiscal_year required", { status: 400 });
  }

  const { data } = await getSupabaseAdmin()
    .from("tax_approved_mappings")
    .select("*")
    .eq("company_id", companyId)
    .eq("fiscal_year", fiscalYear);
  const rows = (data ?? []) as unknown as ApprovedRow[];

  const filename = `tax_disclosure_FY${fiscalYear}`;

  if (format === "csv") {
    const header = ["gl_account", "description", "posting_amount", "tax_category", "tax_category_label", "asc_citation", "reviewer", "reviewed_at"];
    const lines = [header.join(",")];
    for (const r of rows) {
      lines.push([
        r.gl_account,
        `"${(r.description ?? "").replace(/"/g, '""')}"`,
        String(r.posting_amount ?? 0),
        r.tax_category,
        r.tax_category_label,
        r.asc_citation ?? "",
        r.reviewer ?? "",
        r.reviewed_at ?? "",
      ].join(","));
    }
    return new NextResponse(lines.join("\n"), {
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": `attachment; filename="${filename}.csv"`,
      },
    });
  }

  if (format === "json") {
    return NextResponse.json({ company_id: companyId, fiscal_year: fiscalYear, approved_count: rows.length, rows });
  }

  if (format === "docx") {
    const totals: Record<TaxCategory, number> = {
      current_federal: 0, current_state: 0, current_foreign: 0,
      deferred_federal: 0, deferred_state: 0, deferred_foreign: 0,
      deferred_tax_asset: 0, deferred_tax_liab: 0,
      pretax_domestic: 0, pretax_foreign: 0,
      not_tax_account: 0,
    };
    for (const r of rows) totals[r.tax_category] += Number(r.posting_amount ?? 0);

    const currentTotal = totals.current_federal + totals.current_state + totals.current_foreign;
    const deferredTotal = totals.deferred_federal + totals.deferred_state + totals.deferred_foreign;
    const totalProvision = currentTotal + deferredTotal;
    const pretax = totals.pretax_domestic + totals.pretax_foreign;
    const effectiveRate = pretax > 0 ? totalProvision / pretax : 0;

    const tableA = new Table({
      width: { size: 100, type: WidthType.PERCENTAGE },
      rows: [
        new TableRow({
          children: ["Item", "Amount", "% of pretax"].map((t) =>
            new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: t, bold: true })] })] }),
          ),
        }),
        ...[
          { item: "US federal statutory @21%", amt: pretax * STATUTORY_RATE },
          { item: "State and local, net of federal benefit", amt: totals.current_state + totals.deferred_state },
          { item: "Foreign rate differential", amt: (totals.current_foreign + totals.deferred_foreign) - (totals.pretax_foreign * STATUTORY_RATE) },
          { item: "Deferred tax expense — federal", amt: totals.deferred_federal },
          { item: "Total income tax expense", amt: totalProvision },
        ].map(({ item, amt }) =>
          new TableRow({
            children: [
              new TableCell({ children: [new Paragraph(item)] }),
              new TableCell({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, text: fmtMillions(amt) })] }),
              new TableCell({
                children: [new Paragraph({ alignment: AlignmentType.RIGHT, text: pretax > 0 ? fmtPct(amt / pretax) : "—" })],
              }),
            ],
          }),
        ),
      ],
    });

    const doc = new Document({
      sections: [
        {
          children: [
            new Paragraph({ heading: HeadingLevel.HEADING_1, text: `Income Taxes (ASU 2023-09) — FY${fiscalYear}` }),
            new Paragraph({
              text: `ETR reconciliation, pre-tax income split, and supporting detail built from ${rows.length} controller-approved tax GL classifications. Effective tax rate: ${fmtPct(effectiveRate)}; statutory rate: ${(STATUTORY_RATE * 100).toFixed(0)}%.`,
            }),
            new Paragraph({ text: "" }),
            new Paragraph({ heading: HeadingLevel.HEADING_2, text: "Table A — Effective tax rate reconciliation" }),
            tableA,
            new Paragraph({ text: "" }),
            new Paragraph({ heading: HeadingLevel.HEADING_2, text: "Table C — Pre-tax income split" }),
            new Paragraph(`Domestic operations: ${fmtMillions(totals.pretax_domestic)}.`),
            new Paragraph(`Foreign operations: ${fmtMillions(totals.pretax_foreign)}.`),
            new Paragraph(`Total: ${fmtMillions(pretax)}.`),
          ],
        },
      ],
    });

    const buf = await Packer.toBuffer(doc);
    return new NextResponse(new Uint8Array(buf), {
      headers: {
        "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "Content-Disposition": `attachment; filename="${filename}.docx"`,
      },
    });
  }

  return new NextResponse("unsupported format (csv | json | docx)", { status: 400 });
}
