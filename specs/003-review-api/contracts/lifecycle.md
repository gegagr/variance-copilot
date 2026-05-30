# Contract: Review lifecycle state machine

The workflow state machine lives in `api/services/lifecycle.py` (pure). It is the single
source of truth for valid transitions; the service calls it before every state change and the
adapter maps `InvalidTransition` to HTTP 409.

## States

`detected → investigating → awaiting_controller → drafted → accepted | dismissed`

Resolved = `{accepted, dismissed}`.

## Transition table `(status, action) → new_status`

| From \ Action | investigate | answer | accept | edit | dismiss |
|---------------|-------------|--------|--------|------|---------|
| detected | investigating | ✗ | ✗ | ✗ | dismissed |
| investigating | ✗ | ✗ | ✗ | ✗ | ✗ |
| awaiting_controller | ✗ | drafted | ✗ | ✗ | dismissed |
| drafted | investigating¹ | ✗ | accepted | drafted | dismissed |
| accepted | ✗ | ✗ | ✗ | drafted² | dismissed |
| dismissed | ✗ | ✗ | ✗ | ✗ | ✗ |

✗ = rejected (`InvalidTransition` → HTTP 409), status unchanged.

¹ Re-investigate from `drafted` starts a fresh run: it returns to `investigating`, discards the
prior run's draft and any `edited_text`, and (when the new run produces a Draft) sets
`original_draft` to the new run's AI draft as the provenance baseline.
² Editing an `accepted` item reverts it to `drafted`; the new text MUST be re-accepted before it
is final again (the `original_draft` snapshot is preserved throughout).

## Internal resolution (within `investigate`)

After `investigating`, the Block 3 agent result drives the next state, NOT a controller action:

- agent returns a **Question** → `awaiting_controller`
- agent returns a **Draft** (self-explanatory) → `drafted`
- agent **fail-safe** (no grounded output) → back to `detected`; the API surfaces the failure and
  serves no commentary.

## Notes

- `investigate` is allowed only from `detected` or `drafted` (re-run); never from
  `awaiting_controller` (answer first), `investigating`, `accepted`, or `dismissed`.
- `edit` retains the `original_draft` and writes `edited_text`; from `accepted` it also reverts
  status to `drafted`.
- Every accepted transition appends a `ReviewAction(action, actor, ts, from_status, to_status)`.
