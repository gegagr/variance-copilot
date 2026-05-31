# Contract — UI changes: As-of selector + query-key threading

A new "As of" selector plus `current_period` woven into the existing TanStack Query keys. No new
screens; the existing components are reused. The UI still renders the API's display strings verbatim
and performs no figure arithmetic.

## schema.ts (constants)

Replace the single session constant:

```ts
// before
export const CURRENT_PERIOD = 6;

// after
export const DEFAULT_PERIOD = 6;            // latest month with actuals
export const AS_OF_PERIODS = [1, 2, 3, 4, 5, 6] as const;  // months with actuals, latest last
```

> The selectable set is a UI constant for v0 (documented assumption). A future `/periods` endpoint can
> make it data-driven without changing the component contract.

## api/client.ts

`review`, `progress`, and the mutations carry `current_period`:

```
review(currentPeriod)             -> GET  /review?current_period=…
progress(currentPeriod)           -> GET  /review/progress?current_period=…
investigate(flagId, currentPeriod)-> POST /review/{flagId}/investigate?current_period=…
answer(flagId, currentPeriod, body)
accept(flagId, currentPeriod)
edit(flagId, currentPeriod, body)
dismiss(flagId, currentPeriod)
```

`pnlView(currentPeriod, timeCut)` and `variancesView(currentPeriod)` are unchanged.

## hooks/api.ts (query keys + hook signatures)

```ts
export const qk = {
  pnl:       (p: number, tc: TimeCut) => ["pnl", p, tc] as const,
  variances: (p: number)             => ["variances", p] as const,
  review:    (p: number)             => ["review", p] as const,
  progress:  (p: number)             => ["progress", p] as const,
};

usePnl(currentPeriod, timeCut)   // queryKey qk.pnl(currentPeriod, timeCut)
useVariances(currentPeriod)      // qk.variances(currentPeriod)
useReview(currentPeriod)         // qk.review(currentPeriod)
useProgress(currentPeriod)       // qk.progress(currentPeriod)
useReviewActions(currentPeriod)  // mutations carry currentPeriod; invalidate review+progress for that period
```

- Mutations invalidate `qk.review(currentPeriod)` and `qk.progress(currentPeriod)` so the card status
  and progress mirror the API for the selected month.
- Because `current_period` is in every key, switching months refetches the grid, variances, and queue
  together, and each month's data is cached independently (returning to a month is instant and shows
  its own state).

## components/AsOfSelector.tsx (NEW)

- Mirrors `TimeCutSelector`: a small labelled control over `AS_OF_PERIODS`.
- Props: `{ value: number; onChange: (p: number) => void }`.
- Renders each period as a human label (e.g. "Jun (P6)"); display-only, no arithmetic.

## components/Workspace.tsx

- Add UI state: `const [currentPeriod, setCurrentPeriod] = useState<number>(DEFAULT_PERIOD);`
- Render `<AsOfSelector value={currentPeriod} onChange={setCurrentPeriod} />` in the header
  (alongside progress / "Investigate all"). The `TimeCutSelector` stays in the P&L pane and continues
  to slice relative to `currentPeriod`.
- Thread `currentPeriod` into `usePnl`, `useVariances`, `useReview`, `useProgress`, and
  `useReviewActions`; pass it on every mutation call.

## Tests (extend existing Vitest + MSW)
- MSW handlers key fixtures by `current_period` (so period 6 returns the seeded queue; another period
  returns its own).
- A test asserts changing the As-of selector refetches grid/variances/review (query keys include
  `current_period`).
- A test asserts the `time_cut` selector still works for the chosen as-of month (independent
  controls).
- The existing no-arithmetic guard continues to pass (the selector adds no figure math).
