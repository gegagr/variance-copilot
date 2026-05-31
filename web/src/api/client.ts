// The ONLY network access in the app. Thin typed wrapper over fetch; base URL `/api`.
import type {
  AnswerRequest,
  EditRequest,
  FlaggedVarianceView,
  PnLResultView,
  ReviewItemView,
  ReviewProgressView,
  TimeCut,
} from "./schema";

const BASE = "/api";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(res.status, body?.detail ?? res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const id = (flagId: string) => encodeURIComponent(flagId);

export const api = {
  pnlView: (currentPeriod: number, timeCut: TimeCut) =>
    request<PnLResultView>(`/pnl/view?current_period=${currentPeriod}&time_cut=${timeCut}`),
  variancesView: (currentPeriod: number) =>
    request<FlaggedVarianceView[]>(`/variances/view?current_period=${currentPeriod}`),
  review: () => request<ReviewItemView[]>(`/review`),
  progress: () => request<ReviewProgressView>(`/review/progress`),
  investigate: (flagId: string) =>
    request<ReviewItemView>(`/review/${id(flagId)}/investigate`, { method: "POST" }),
  answer: (flagId: string, body: AnswerRequest) =>
    request<ReviewItemView>(`/review/${id(flagId)}/answer`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  accept: (flagId: string) =>
    request<ReviewItemView>(`/review/${id(flagId)}/accept`, { method: "POST" }),
  edit: (flagId: string, body: EditRequest) =>
    request<ReviewItemView>(`/review/${id(flagId)}/edit`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  dismiss: (flagId: string) =>
    request<ReviewItemView>(`/review/${id(flagId)}/dismiss`, { method: "POST" }),
};
