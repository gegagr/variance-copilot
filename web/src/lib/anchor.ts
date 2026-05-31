// Pure line <-> cards index for bidirectional anchoring. One card per flag; a line may map to many.
import type { FlaggedVarianceView } from "@/api/schema";

export interface AnchorIndex {
  lineToFlags: Map<string, string[]>;
  flagToLine: Map<string, string>;
}

export function buildAnchor(flags: FlaggedVarianceView[]): AnchorIndex {
  const lineToFlags = new Map<string, string[]>();
  const flagToLine = new Map<string, string>();
  for (const f of flags) {
    flagToLine.set(f.flag_id, f.reporting_line);
    const arr = lineToFlags.get(f.reporting_line) ?? [];
    arr.push(f.flag_id);
    lineToFlags.set(f.reporting_line, arr);
  }
  return { lineToFlags, flagToLine };
}

/** Reporting lines that have at least one flagged variance (for grid markers). */
export function flaggedLines(index: AnchorIndex): Set<string> {
  return new Set(index.lineToFlags.keys());
}
