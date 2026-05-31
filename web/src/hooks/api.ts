// TanStack Query hooks: server state lives here. current_period is the as-of month — it is part of
// every query key, so changing it refetches the grid, variances, and review queue for that month
// (each month's data caches independently). Mutations invalidate review+progress FOR THAT PERIOD so
// the UI always mirrors the API's review state.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { AnswerRequest, EditRequest, TimeCut } from "@/api/schema";

export const qk = {
  pnl: (p: number, timeCut: TimeCut) => ["pnl", p, timeCut] as const,
  variances: (p: number) => ["variances", p] as const,
  review: (p: number) => ["review", p] as const,
  progress: (p: number) => ["progress", p] as const,
};

export function usePnl(currentPeriod: number, timeCut: TimeCut) {
  return useQuery({
    queryKey: qk.pnl(currentPeriod, timeCut),
    queryFn: () => api.pnlView(currentPeriod, timeCut),
  });
}

export function useVariances(currentPeriod: number) {
  return useQuery({
    queryKey: qk.variances(currentPeriod),
    queryFn: () => api.variancesView(currentPeriod),
  });
}

export function useReview(currentPeriod: number) {
  return useQuery({ queryKey: qk.review(currentPeriod), queryFn: () => api.review(currentPeriod) });
}

export function useProgress(currentPeriod: number) {
  return useQuery({ queryKey: qk.progress(currentPeriod), queryFn: () => api.progress(currentPeriod) });
}

export function useReviewActions(currentPeriod: number) {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: qk.review(currentPeriod) });
    qc.invalidateQueries({ queryKey: qk.progress(currentPeriod) });
  };

  const investigate = useMutation({
    mutationFn: (flagId: string) => api.investigate(flagId, currentPeriod),
    onSuccess: invalidate,
  });
  const answer = useMutation({
    mutationFn: (v: { flagId: string; body: AnswerRequest }) => api.answer(v.flagId, currentPeriod, v.body),
    onSuccess: invalidate,
  });
  const accept = useMutation({
    mutationFn: (flagId: string) => api.accept(flagId, currentPeriod),
    onSuccess: invalidate,
  });
  const edit = useMutation({
    mutationFn: (v: { flagId: string; body: EditRequest }) => api.edit(v.flagId, currentPeriod, v.body),
    onSuccess: invalidate,
  });
  const dismiss = useMutation({
    mutationFn: (flagId: string) => api.dismiss(flagId, currentPeriod),
    onSuccess: invalidate,
  });

  return { investigate, answer, accept, edit, dismiss };
}
