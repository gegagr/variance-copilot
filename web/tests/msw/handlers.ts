// Stateful MSW handlers that emulate the Block 4 review API deterministically (offline).
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

const store = new Map<string, Item>();

export function resetStore() {
  store.clear();
  for (const f of flags) {
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

const progress = () => {
  const items = [...store.values()];
  const resolved = items.filter((i) => i.status === "accepted" || i.status === "dismissed").length;
  const by_status: Record<string, number> = {};
  for (const i of items) by_status[i.status] = (by_status[i.status] ?? 0) + 1;
  return { total: flags.length, resolved, by_status };
};

const get = (flagId: string) => store.get(decodeURIComponent(flagId));

export const handlers = [
  http.get("/api/pnl/view", () => HttpResponse.json(pnlView)),
  http.get("/api/variances/view", () => HttpResponse.json(flags)),
  http.get("/api/review", () => HttpResponse.json([...store.values()])),
  http.get("/api/review/progress", () => HttpResponse.json(progress())),

  http.post("/api/review/:flagId/investigate", ({ params }) => {
    const it = get(params.flagId as string);
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
    const it = get(params.flagId as string);
    if (!it) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    if (it.status !== "awaiting_controller")
      return HttpResponse.json({ detail: "invalid transition" }, { status: 409 });
    const body = (await request.json()) as { text: string };
    it.status = "drafted";
    it.controller_answer = { text: body.text };
    it.original_draft = draftFor(it.flag_id);
    return HttpResponse.json(it);
  }),

  http.post("/api/review/:flagId/accept", ({ params }) => {
    const it = get(params.flagId as string);
    if (!it) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    if (it.status !== "drafted")
      return HttpResponse.json({ detail: "invalid transition" }, { status: 409 });
    it.status = "accepted";
    return HttpResponse.json(it);
  }),

  http.post("/api/review/:flagId/edit", async ({ params, request }) => {
    const it = get(params.flagId as string);
    if (!it) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const body = (await request.json()) as { edited_text: string };
    it.status = "drafted"; // edit reverts to drafted; original retained
    it.edited_text = body.edited_text;
    return HttpResponse.json(it);
  }),

  http.post("/api/review/:flagId/dismiss", ({ params }) => {
    const it = get(params.flagId as string);
    if (!it) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    it.status = "dismissed";
    return HttpResponse.json(it);
  }),
];
