// Stateful, PERIOD-AWARE MSW handlers emulating the Block 4 review API deterministically (offline).
// Each as-of month (current_period) owns its own review store, mirroring the real API. Period 6 (the
// default) serves the full fixture flag set so existing tests are unchanged; other periods serve a
// distinct subset so switching the as-of period is observably different.
import { http, HttpResponse } from "msw";

import { DRAFT_COMMENTARY, QUESTION_TEXT, flags, pnlView } from "../fixtures";

type Item = {
  flag_id: string;
  reporting_line: string;
  status: string;
  record: any;
  original_draft: any;
  controller_answer: any;
  edited_text: string | null;
  updated_at: string;
};

// Which flags become a question (vs a self-explanatory draft) on investigate.
const QUESTION_FLAGS = new Set(["revenue|ytd|current_vs_prior_year"]);

// Period 6 = the full fixture set; any other period = a distinct (non-empty) subset.
function flagsForPeriod(period: number) {
  return period === 6 ? flags : flags.slice(0, 1);
}

// One review store per as-of month: Map<period, Map<flag_id, Item>>.
const stores = new Map<number, Map<string, Item>>();

// Test introspection: which periods each endpoint was queried with (asserts refetch-on-change).
export const requested = { review: [] as number[], variances: [] as number[], pnl: [] as number[] };

function periodOf(request: Request): number {
  return Number(new URL(request.url).searchParams.get("current_period") ?? "6");
}

function seedPeriod(period: number): Map<string, Item> {
  const store = new Map<string, Item>();
  for (const f of flagsForPeriod(period)) {
    store.set(f.flag_id as string, {
      flag_id: f.flag_id as string,
      reporting_line: f.reporting_line as string,
      status: "detected",
      record: null,
      original_draft: null,
      controller_answer: null,
      edited_text: null,
      updated_at: "t0",
    });
  }
  return store;
}

function storeFor(period: number): Map<string, Item> {
  let store = stores.get(period);
  if (!store) {
    store = seedPeriod(period);
    stores.set(period, store);
  }
  return store;
}

export function resetStore() {
  stores.clear();
  stores.set(6, seedPeriod(6)); // eager-seed the default period (back-compat with existing tests)
  requested.review.length = 0;
  requested.variances.length = 0;
  requested.pnl.length = 0;
}
resetStore();

function draftFor(flagId: string) {
  return { schema_version: "1.0.0", flag_id: flagId, commentary: DRAFT_COMMENTARY, is_proposal: true };
}
function questionRecord(flagId: string) {
  return {
    status: "question",
    question: { text: QUESTION_TEXT, hypothesis: { text: "Likely the new enterprise contract." } },
    draft: null,
  };
}

const progress = (period: number) => {
  const items = [...storeFor(period).values()];
  const resolved = items.filter((i) => i.status === "accepted" || i.status === "dismissed").length;
  const by_status: Record<string, number> = {};
  for (const i of items) by_status[i.status] = (by_status[i.status] ?? 0) + 1;
  return { total: flagsForPeriod(period).length, resolved, by_status };
};

const get = (period: number, flagId: string) => storeFor(period).get(decodeURIComponent(flagId));

export const handlers = [
  http.get("/api/pnl/view", ({ request }) => {
    requested.pnl.push(periodOf(request));
    return HttpResponse.json(pnlView);
  }),
  http.get("/api/variances/view", ({ request }) => {
    const p = periodOf(request);
    requested.variances.push(p);
    return HttpResponse.json(flagsForPeriod(p));
  }),
  http.get("/api/review", ({ request }) => {
    const p = periodOf(request);
    requested.review.push(p);
    return HttpResponse.json([...storeFor(p).values()]);
  }),
  http.get("/api/review/progress", ({ request }) => HttpResponse.json(progress(periodOf(request)))),

  http.post("/api/review/:flagId/investigate", ({ params, request }) => {
    const it = get(periodOf(request), params.flagId as string);
    if (!it) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    if (QUESTION_FLAGS.has(it.flag_id)) {
      it.status = "awaiting_controller";
      it.record = questionRecord(it.flag_id);
    } else {
      it.status = "drafted";
      it.original_draft = draftFor(it.flag_id);
      it.record = { status: "draft", draft: it.original_draft };
    }
    return HttpResponse.json(it);
  }),

  http.post("/api/review/:flagId/answer", async ({ params, request }) => {
    const it = get(periodOf(request), params.flagId as string);
    if (!it) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    if (it.status !== "awaiting_controller")
      return HttpResponse.json({ detail: "invalid transition" }, { status: 409 });
    const body = (await request.json()) as { text: string };
    it.status = "drafted";
    it.controller_answer = { text: body.text };
    it.original_draft = draftFor(it.flag_id);
    return HttpResponse.json(it);
  }),

  http.post("/api/review/:flagId/accept", ({ params, request }) => {
    const it = get(periodOf(request), params.flagId as string);
    if (!it) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    if (it.status !== "drafted")
      return HttpResponse.json({ detail: "invalid transition" }, { status: 409 });
    it.status = "accepted";
    return HttpResponse.json(it);
  }),

  http.post("/api/review/:flagId/edit", async ({ params, request }) => {
    const it = get(periodOf(request), params.flagId as string);
    if (!it) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const body = (await request.json()) as { edited_text: string };
    it.status = "drafted"; // edit reverts to drafted; original retained
    it.edited_text = body.edited_text;
    return HttpResponse.json(it);
  }),

  http.post("/api/review/:flagId/dismiss", ({ params, request }) => {
    const it = get(periodOf(request), params.flagId as string);
    if (!it) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    it.status = "dismissed";
    return HttpResponse.json(it);
  }),
];
