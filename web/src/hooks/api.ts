// TanStack Query hooks: server state lives here. Mutations invalidate review+progress so the UI
// always mirrors the API's review state.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import { CURRENT_PERIOD, type AnswerRequest, type EditRequest, type TimeCut } from "@/api/schema";

export const qk = {
  pnl: (timeCut: TimeCut) => ["pnl", CURRENT_PERIOD, timeCut] as const,
  variances: () => ["variances", CURRENT_PERIOD] as const,
  review: () => ["review"] as const,
  progress: () => ["progress"] as const,
};

export function usePnl(timeCut: TimeCut) {
  return useQuery({ queryKey: qk.pnl(timeCut), queryFn: () => api.pnlView(CURRENT_PERIOD, timeCut) });
}

export function useVariances() {
  return useQuery({ queryKey: qk.variances(), queryFn: () => api.variancesView(CURRENT_PERIOD) });
}

export function useReview() {
  return useQuery({ queryKey: qk.review(), queryFn: () => api.review() });
}

export function useProgress() {
  return useQuery({ queryKey: qk.progress(), queryFn: () => api.progress() });
}

export function useReviewActions() {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: qk.review() });
    qc.invalidateQueries({ queryKey: qk.progress() });
  };

  const investigate = useMutation({ mutationFn: (flagId: string) => api.investigate(flagId), onSuccess: invalidate });
  const answer = useMutation({
    mutationFn: (v: { flagId: string; body: AnswerRequest }) => api.answer(v.flagId, v.body),
    onSuccess: invalidate,
  });
  const accept = useMutation({ mutationFn: (flagId: string) => api.accept(flagId), onSuccess: invalidate });
  const edit = useMutation({
    mutationFn: (v: { flagId: string; body: EditRequest }) => api.edit(v.flagId, v.body),
    onSuccess: invalidate,
  });
  const dismiss = useMutation({ mutationFn: (flagId: string) => api.dismiss(flagId), onSuccess: invalidate });

  return { investigate, answer, accept, edit, dismiss };
}
