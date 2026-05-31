import type { PnLLineView, PnLResultView, PnlCellView, TimeCut } from "@/api/schema";
import { cn } from "@/lib/utils";

const SCENARIOS = ["prior_year", "current_year", "budget"] as const;
const SCENARIO_LABEL: Record<string, string> = {
  prior_year: "Prior year",
  current_year: "Current year",
  budget: "Budget",
};

function cellFor(line: PnLLineView, scenario: string, timeCut: TimeCut): PnlCellView | undefined {
  return line.cells.find((c) => c.scenario === scenario && c.time_cut === timeCut);
}

function rowClasses(line: PnLLineView): string {
  if (line.line_type === "subtotal") return "font-semibold bg-canvas";
  if (line.line_type === "margin") return "text-slate-500 italic";
  return "";
}

export function PnlGrid({
  pnl,
  timeCut,
  flaggedLines,
  selectedLine,
  onSelectLine,
}: {
  pnl: PnLResultView;
  timeCut: TimeCut;
  flaggedLines: Set<string>;
  selectedLine: string | null;
  onSelectLine: (line: string) => void;
}) {
  return (
    <table className="w-full border-collapse text-sm" aria-label="P&L grid">
      <thead>
        <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-slate-500">
          <th className="py-2 pr-4 font-medium">Reporting line</th>
          {SCENARIOS.map((s) => (
            <th key={s} className="px-3 py-2 text-right font-medium">
              {SCENARIO_LABEL[s]}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {pnl.lines.map((line) => {
          const flagged = flaggedLines.has(line.reporting_line);
          const selected = selectedLine === line.reporting_line;
          return (
            <tr
              key={line.reporting_line}
              data-testid={`grid-row-${line.reporting_line}`}
              data-flagged={flagged}
              data-selected={selected}
              onClick={() => flagged && onSelectLine(line.reporting_line)}
              className={cn(
                "border-b border-border/60",
                rowClasses(line),
                flagged && "cursor-pointer hover:bg-accent-subtle/60",
                selected && "bg-accent-subtle ring-1 ring-accent",
              )}
            >
              <td className="py-2 pr-4">
                <span className="inline-flex items-center gap-2">
                  {flagged && (
                    <span
                      data-testid={`marker-${line.reporting_line}`}
                      aria-label="flagged"
                      className="inline-block h-2 w-2 rounded-full bg-accent"
                    />
                  )}
                  {line.reporting_line}
                </span>
              </td>
              {SCENARIOS.map((s) => {
                const cell = cellFor(line, s, timeCut);
                return (
                  <td key={s} className="num px-3 py-2 text-right tabular-nums">
                    {/* Rendered verbatim from the API's display string — no UI computation. */}
                    {cell ? cell.display : "—"}
                  </td>
                );
              })}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
