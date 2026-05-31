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

export const CURRENT_PERIOD = 6; // the review session's fiscal period (matches Block 4 default)
