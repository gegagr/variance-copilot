import { cn } from "@/lib/utils";

export function Progress({ value, max, className }: { value: number; max: number; className?: string }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div className={cn("h-2 w-full overflow-hidden rounded-full bg-border", className)} role="progressbar" aria-valuenow={value} aria-valuemax={max}>
      <div className="h-full bg-accent transition-all" style={{ width: `${pct}%` }} />
    </div>
  );
}
