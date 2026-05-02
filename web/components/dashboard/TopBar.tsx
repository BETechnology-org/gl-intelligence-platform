import { Calendar, Building2 } from "lucide-react";

interface Props {
  fiscalYear: string;
  companyCode: string;
  userEmail?: string | null;
}

export function TopBar({ fiscalYear, companyCode, userEmail }: Props) {
  return (
    <header className="flex h-14 items-center justify-between border-b border-neutral-200 bg-white/80 px-6 backdrop-blur dark:border-neutral-800 dark:bg-neutral-950/80">
      <div className="flex items-center gap-6 text-sm">
        <div className="flex items-center gap-2 text-neutral-600 dark:text-neutral-400">
          <Building2 size={16} />
          <span className="font-medium">Company</span>
          <span className="rounded bg-neutral-100 px-2 py-0.5 font-mono text-[12px] dark:bg-neutral-800">
            {companyCode}
          </span>
        </div>
        <div className="flex items-center gap-2 text-neutral-600 dark:text-neutral-400">
          <Calendar size={16} />
          <span className="font-medium">Fiscal year</span>
          <span className="rounded bg-neutral-100 px-2 py-0.5 font-mono text-[12px] dark:bg-neutral-800">
            FY{fiscalYear}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3 text-sm text-neutral-600 dark:text-neutral-400">
        {userEmail && <span className="font-medium">{userEmail}</span>}
      </div>
    </header>
  );
}
