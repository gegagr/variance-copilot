// Ergonomic aliases over the GENERATED OpenAPI types (src/api/types.ts — do not hand-edit).
import type { components } from "./types";

export type PnLResultView = components["schemas"]["PnLResultView"];
export type PnLLineView = components["schemas"]["PnLLineView"];
export type PnlCellView = components["schemas"]["PnlCellView"];
export type FlaggedVarianceView = components["schemas"]["FlaggedVarianceView"];
export type ReviewItemView = components["schemas"]["ReviewItemView"];
export type ReviewProgressView = components["schemas"]["ReviewProgressView"];
export type AnswerRequest = components["schemas"]["AnswerRequest"];
export type EditRequest = components["schemas"]["EditRequest"];
export type InvestigationRecord = components["schemas"]["InvestigationRecord"];
export type Question = components["schemas"]["Question"];
export type Draft = components["schemas"]["Draft"];

export type ReviewStatus = ReviewItemView["status"];
export type TimeCut = "prior_month_ytd" | "current_month" | "ytd" | "full_year";

// The as-of month the workspace is anchored to. Selectable set = months that have actuals
// (the latest, period 6, is the default). A future /periods endpoint can make this data-driven.
export const DEFAULT_PERIOD = 6;
export const AS_OF_PERIODS = [1, 2, 3, 4, 5, 6] as const; // months with actuals, latest last
