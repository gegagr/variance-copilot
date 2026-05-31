// DISPLAY-ONLY helpers. CONSTITUTION: this module MUST NOT transform a served figure string —
// no parseFloat/Number, no ×100, no rounding, no summing. Figures arrive pre-formatted from the
// API (deterministic Python). Here we only pick styling (e.g. color by direction).

export type Direction = "favorable" | "unfavorable" | "neutral";

/** Tailwind text color class for a variance direction. Never touches a figure value. */
export function directionClass(direction: string): string {
  if (direction === "favorable") return "text-favorable";
  if (direction === "unfavorable") return "text-unfavorable";
  return "text-slate-600";
}

/** A served display string, rendered verbatim. Identity by design — the UI adds no formatting. */
export function figure(display: string | null | undefined): string {
  return display ?? "—";
}
