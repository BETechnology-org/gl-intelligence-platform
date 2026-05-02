import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { Document, Packer, Paragraph, Table, TableCell, TableRow, HeadingLevel, TextRun, WidthType, AlignmentType } from "docx";

import { createClient } from "@/utils/supabase/server";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import { DISE_CATEGORIES, DISE_CAPTIONS, DISE_CITATIONS, type DISECategory, type DISECaption } from "@/lib/dise-categories";

export const runtime = "nodejs";

const fmtThousands = (n: number) => Math.round(n / 1000).toLocaleString();

interface ApprovedRow {
  gl_account: string;
  description: string;
  posting_amount: number;
  dise_category: DISECategory;
  expense_caption: DISECaption;
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
    .from("dise_approved_mappings")
    .select("*")
    .eq("company_id", companyId)
    .eq("fiscal_year", fiscalYear);
  const rows = (data ?? []) as unknown as ApprovedRow[];

  const filename = `dise_disclosure_FY${fiscalYear}`;

  if (format === "json") {
    return NextResponse.json(
      {
        company_id: companyId,
        fiscal_year: fiscalYear,
        approved_count: rows.length,
        rows,
        pivot: buildPivot(rows),
      },
      {
        headers: { "Content-Disposition": `attachment; filename="${filename}.json"` },
      },
    );
  }

  if (format === "csv") {
    const csv = buildCSV(rows);
    return new NextResponse(csv, {
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": `attachment; filename="${filename}.csv"`,
      },
    });
  }

  if (format === "docx") {
    const doc = buildDocx(fiscalYear, rows);
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

function buildPivot(rows: ApprovedRow[]) {
  const pivot: Record<DISECategory, Record<DISECaption, number>> = {} as Record<DISECategory, Record<DISECaption, number>>;
  DISE_CATEGORIES.forEach((c) => {
    pivot[c] = {} as Record<DISECaption, number>;
    DISE_CAPTIONS.forEach((cap) => { pivot[c][cap] = 0; });
  });
  for (const r of rows) {
    if (pivot[r.dise_category]?.[r.expense_caption] !== undefined) {
      pivot[r.dise_category][r.expense_caption] += Number(r.posting_amount ?? 0);
    }
  }
  return pivot;
}

function buildCSV(rows: ApprovedRow[]): string {
  const header = ["gl_account", "description", "posting_amount", "dise_category", "expense_caption", "asc_citation", "reviewer", "reviewed_at"];
  const lines = [header.join(",")];
  for (const r of rows) {
    const cells = [
      r.gl_account,
      `"${(r.description ?? "").replace(/"/g, '""')}"`,
      String(r.posting_amount ?? 0),
      r.dise_category,
      r.expense_caption,
      r.asc_citation ?? "",
      r.reviewer ?? "",
      r.reviewed_at ?? "",
    ];
    lines.push(cells.join(","));
  }
  return lines.join("\n");
}

function buildDocx(fiscalYear: string, rows: ApprovedRow[]): Document {
  const pivot = buildPivot(rows);

  const headerRow = new TableRow({
    children: [
      new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: "Natural expense category", bold: true })] })] }),
      new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: "ASC citation", bold: true })] })] }),
      ...DISE_CAPTIONS.map((cap) =>
        new TableCell({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: cap, bold: true })] })] }),
      ),
      new TableCell({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: "Total", bold: true })] })] }),
    ],
  });

  const bodyRows = DISE_CATEGORIES.map((cat) => {
    const rowTotal = DISE_CAPTIONS.reduce((s, cap) => s + pivot[cat][cap], 0);
    return new TableRow({
      children: [
        new TableCell({ children: [new Paragraph(cat)] }),
        new TableCell({ children: [new Paragraph(DISE_CITATIONS[cat])] }),
        ...DISE_CAPTIONS.map((cap) =>
          new TableCell({
            children: [
              new Paragraph({
                alignment: AlignmentType.RIGHT,
                text: pivot[cat][cap] ? fmtThousands(pivot[cat][cap]) : "—",
              }),
            ],
          }),
        ),
        new TableCell({
          children: [new Paragraph({ alignment: AlignmentType.RIGHT, text: rowTotal ? fmtThousands(rowTotal) : "—" })],
        }),
      ],
    });
  });

  const colTotals: Record<DISECaption, number> = {} as Record<DISECaption, number>;
  DISE_CAPTIONS.forEach((cap) => {
    colTotals[cap] = DISE_CATEGORIES.reduce((s, c) => s + pivot[c][cap], 0);
  });
  const grandTotal = Object.values(colTotals).reduce((s, v) => s + v, 0);

  const totalRow = new TableRow({
    children: [
      new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: "Total", bold: true })] })] }),
      new TableCell({ children: [new Paragraph("")] }),
      ...DISE_CAPTIONS.map((cap) =>
        new TableCell({
          children: [
            new Paragraph({
              alignment: AlignmentType.RIGHT,
              children: [new TextRun({ text: colTotals[cap] ? fmtThousands(colTotals[cap]) : "—", bold: true })],
            }),
          ],
        }),
      ),
      new TableCell({
        children: [
          new Paragraph({
            alignment: AlignmentType.RIGHT,
            children: [new TextRun({ text: grandTotal ? fmtThousands(grandTotal) : "—", bold: true })],
          }),
        ],
      }),
    ],
  });

  const table = new Table({
    rows: [headerRow, ...bodyRows, totalRow],
    width: { size: 100, type: WidthType.PERCENTAGE },
  });

  return new Document({
    sections: [
      {
        children: [
          new Paragraph({ heading: HeadingLevel.HEADING_1, text: `Disaggregation of Income Statement Expenses (DISE) — FY${fiscalYear}` }),
          new Paragraph({
            text: `Tabular disclosure required by ASU 2024-03 (ASC 220-40). Amounts in thousands. Built from ${rows.length} controller-approved GL classifications.`,
          }),
          new Paragraph({ text: "" }),
          table,
          new Paragraph({ text: "" }),
          new Paragraph({ heading: HeadingLevel.HEADING_2, text: "Methodology" }),
          new Paragraph({
            text: "The Company classified its income statement expenses into the natural expense categories prescribed by ASC 220-40 using a controller-reviewed AI classification of source GL accounts. Each classification is supported by the underlying GL detail and was approved by the Controller prior to inclusion in this disclosure. Reasonable estimates and methods that approximate the prescribed categories were used where source detail was not directly available, as permitted by ASC 220-40.",
          }),
          new Paragraph({ heading: HeadingLevel.HEADING_2, text: "Selling expenses definition" }),
          new Paragraph({
            text: "For purposes of this disclosure, selling expenses include direct sales force compensation and benefits, advertising and marketing programs, third-party sales commissions, sales support technology, and travel incurred in pursuit of new and existing customer relationships. The Company applied this definition consistently across the periods presented.",
          }),
          new Paragraph({ heading: HeadingLevel.HEADING_2, text: "Inventory expensed when sold" }),
          new Paragraph({
            text: "Amounts of inventory expensed when sold are included in the \"Purchases of inventory\" row when those amounts are recognized in cost of revenues. Capitalized inventory is excluded from this disclosure until expensed.",
          }),
        ],
      },
    ],
  });
}
