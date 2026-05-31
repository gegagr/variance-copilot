import type { TimeCut } from "@/api/schema";
import { cn } from "@/lib/utils";

const CUTS: { value: TimeCut; label: string }[] = [
  { value: "prior_month_ytd", label: "Prior-month YTD" },
  { value: "current_month", label: "Current month" },
  { value: "ytd", label: "YTD" },
  { value: "full_year", label: "Full year" },
];

export function TimeCutSelector({ value, onChange }: { value: TimeCut; onChange: (c: TimeCut) => void }) {
  return (
    <div className="inline-flex rounded-md border border-border bg-surface p-0.5" role="tablist" aria-label="Time cut">
      {CUTS.map((c) => (
        <button
          key={c.value}
          role="tab"
          aria-selected={value === c.value}
          onClick={() => onChange(c.value)}
          className={cn(
            "rounded px-3 py-1 text-sm transition-colors",
            value === c.value ? "bg-accent text-accent-fg" : "text-slate-600 hover:bg-canvas",
          )}
        >
          {c.label}
        </button>
      ))}
    </div>
  );
}
