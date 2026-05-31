# Contract: card lifecycle → controls & visual treatment

`VarianceCard` renders a variant per the API's review status. Status comes from Block 4 only; the
UI never derives it. Controls are gated on status (FR-012); after any action the card shows the
API's returned status.

| Status | Visual treatment | Content shown | Controls (enabled) |
|--------|------------------|---------------|--------------------|
| `detected` | neutral, "flagged" badge | variance figures (display strings), direction color | **Investigate** |
| `investigating` | pending shimmer/spinner, accent border | "Investigating…" | none (all disabled) |
| `awaiting_controller` | attention accent | Question text + hypothesis + cited evidence | answer textarea + **Submit**; **Dismiss** |
| `drafted` | active | proposed commentary | **Accept**, **Edit**, **Dismiss** (+ re-investigate if API allows) |
| `accepted` | settled, de-emphasized, success tint | accepted commentary text | **Edit** (→ drafted), **Dismiss** |
| `dismissed` | settled, de-emphasized, muted | "Dismissed" | none |

## Semantic colors

- **Variance direction**: `favorable` vs `unfavorable` tint on the variance figure (from the served
  `direction`, never recomputed).
- **Status**: a per-status accent (detected neutral, investigating accent, awaiting attention,
  drafted active, accepted success, dismissed muted) — all from the single indigo-anchored palette.

## Interaction rules

- **Investigate** (detected, or re-investigate where allowed) → `POST .../investigate`; card enters
  `investigating` (mutation pending) then shows the returned status.
- **Submit answer** (awaiting_controller) → requires non-empty text (client-guarded) →
  `POST .../answer` → `drafted`.
- **Edit** → opens an inline editor seeded with the current commentary; **Save+Accept** sends
  `POST .../edit` then `POST .../accept` (or edit alone → stays `drafted`). Accepted text reflects
  the edit (SC-005).
- **Accept** (drafted) → `POST .../accept` → `accepted`.
- **Dismiss** → `POST .../dismiss` → `dismissed`.
- **Error/fail-safe** → card shows an error treatment; the rest of the workspace stays usable.

## Anchoring

- Selecting a card sets `selectedFlagId`; the grid highlights that flag's reporting line.
- Selecting a marked grid line emphasizes/scrolls the queue to that line's card group (a line may
  have several cards).
