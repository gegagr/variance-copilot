import { useMemo, useState } from "react";

import type { ReviewItemView, TimeCut } from "@/api/schema";
import { DEFAULT_PERIOD } from "@/api/schema";
import { ApiError } from "@/api/client";
import { AsOfSelector } from "@/components/AsOfSelector";
import { PnlGrid } from "@/components/PnlGrid";
import { ProgressBar } from "@/components/ProgressBar";
import { TimeCutSelector } from "@/components/TimeCutSelector";
import { VarianceReviewPanel, type PanelHandlers } from "@/components/VarianceReviewPanel";
import { Button } from "@/components/ui/button";
import { usePnl, useProgress, useReview, useReviewActions, useVariances } from "@/hooks/api";
import { buildAnchor, flaggedLines as flaggedLinesOf } from "@/lib/anchor";

export function Workspace() {
  const [currentPeriod, setCurrentPeriod] = useState<number>(DEFAULT_PERIOD);
  const [timeCut, setTimeCut] = useState<TimeCut>("ytd");
  const [selectedFlagId, setSelectedFlagId] = useState<string | null>(null);
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, string | null>>({});

  const pnl = usePnl(currentPeriod, timeCut);
  const variances = useVariances(currentPeriod);
  const review = useReview(currentPeriod);
  const progress = useProgress(currentPeriod);
  const actions = useReviewActions(currentPeriod);

  const anchor = useMemo(() => buildAnchor(variances.data ?? []), [variances.data]);
  const flagged = useMemo(() => flaggedLinesOf(anchor), [anchor]);
  const itemByFlag = useMemo(() => {
    const m = new Map<string, ReviewItemView>();
    for (const it of review.data ?? []) m.set(it.flag_id, it);
    return m;
  }, [review.data]);

  const selectedLine = selectedFlagId ? anchor.flagToLine.get(selectedFlagId) ?? null : null;

  const setError = (flagId: string, msg: string | null) =>
    setErrors((e) => ({ ...e, [flagId]: msg }));
  const setBusy = (flagId: string, on: boolean) => setPending((p) => ({ ...p, [flagId]: on }));

  const runInvestigate = async (flagId: string) => {
    setBusy(flagId, true);
    setError(flagId, null);
    try {
      await actions.investigate.mutateAsync(flagId);
    } catch (err) {
      setError(flagId, err instanceof ApiError ? err.message : "Investigation failed");
    } finally {
      setBusy(flagId, false);
    }
  };

  const wrap = (flagId: string, p: Promise<unknown>) =>
    p.catch((err) => setError(flagId, err instanceof ApiError ? err.message : "Action failed"));

  const handlers: PanelHandlers = {
    onInvestigate: (flagId) => void runInvestigate(flagId),
    onAnswer: (flagId, text) =>
      void wrap(flagId, actions.answer.mutateAsync({ flagId, body: { text, accepted_hypothesis: true } })),
    onAccept: (flagId) => void wrap(flagId, actions.accept.mutateAsync(flagId)),
    onEditAndAccept: (flagId, text) =>
      void wrap(
        flagId,
        // Sequential: edit (→ drafted, original retained) THEN accept the edited text.
        actions.edit
          .mutateAsync({ flagId, body: { edited_text: text } })
          .then(() => actions.accept.mutateAsync(flagId)),
      ),
    onDismiss: (flagId) => void wrap(flagId, actions.dismiss.mutateAsync(flagId)),
  };

  const investigateAll = async () => {
    for (const v of variances.data ?? []) {
      const status = itemByFlag.get(v.flag_id)?.status ?? "detected";
      if (status === "detected") await runInvestigate(v.flag_id); // sequential
    }
  };

  if (pnl.isLoading || variances.isLoading) {
    return <div className="p-8 text-slate-500">Loading the review workspace…</div>;
  }

  return (
    <div className="mx-auto flex h-full max-w-[1400px] flex-col gap-4 p-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Variance review</h1>
          <p className="text-sm text-slate-500">Review flagged P&amp;L variances and draft the commentary.</p>
        </div>
        <div className="flex items-center gap-4">
          <AsOfSelector value={currentPeriod} onChange={setCurrentPeriod} />
          {progress.data && <ProgressBar resolved={progress.data.resolved} total={progress.data.total} />}
          <Button variant="outline" onClick={() => void investigateAll()}>
            Investigate all
          </Button>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.4fr_1fr]">
        <section className="rounded-lg border border-border bg-surface p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium text-slate-700">Profit &amp; loss</h2>
            <TimeCutSelector value={timeCut} onChange={setTimeCut} />
          </div>
          {pnl.data && (
            <PnlGrid
              pnl={pnl.data}
              timeCut={timeCut}
              flaggedLines={flagged}
              selectedLine={selectedLine}
              onSelectLine={(line) => {
                const first = anchor.lineToFlags.get(line)?.[0] ?? null;
                setSelectedFlagId(first);
              }}
            />
          )}
        </section>

        <section>
          <h2 className="mb-3 text-sm font-medium text-slate-700">Review queue</h2>
          <VarianceReviewPanel
            variances={variances.data ?? []}
            itemByFlag={itemByFlag}
            selectedFlagId={selectedFlagId}
            selectedLine={selectedLine}
            onSelect={setSelectedFlagId}
            pending={pending}
            errors={errors}
            handlers={handlers}
          />
        </section>
      </div>
    </div>
  );
}
