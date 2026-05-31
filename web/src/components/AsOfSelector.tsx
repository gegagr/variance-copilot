import { AS_OF_PERIODS } from "@/api/schema";
import { cn } from "@/lib/utils";

// Human label for a fiscal month (display-only; no arithmetic on any figure).
const MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const label = (p: number) => `${MONTHS[p] ?? "P"} (P${p})`;

export function AsOfSelector({ value, onChange }: { value: number; onChange: (p: number) => void }) {
  return (
    <div className="inline-flex items-center gap-2">
      <span className="text-sm text-slate-500">As of</span>
      <div className="inline-flex rounded-md border border-border bg-surface p-0.5" role="tablist" aria-label="As-of period">
        {AS_OF_PERIODS.map((p) => (
          <button
            key={p}
            role="tab"
            aria-selected={value === p}
            onClick={() => onChange(p)}
            className={cn(
              "rounded px-3 py-1 text-sm transition-colors",
              value === p ? "bg-accent text-accent-fg" : "text-slate-600 hover:bg-canvas",
            )}
          >
            {label(p)}
          </button>
        ))}
      </div>
    </div>
  );
}
