# Contract: figure display strings (Block 4 addition — the UI's constitutional anchor)

The UI must render figures but never compute or reformat them. So **deterministic Python** produces
a display string per figure and Block 4 serves it; the UI prints it verbatim.

## engine/format.py (pure, deterministic, tested)

```python
def money(value: Decimal, currency: str = "EUR") -> str:   # "€78,600.00"
def percent(ratio: Decimal) -> str:                         # "16.7%"  (×100 happens HERE, in Python)
def points(ratio: Decimal) -> str:                          # "+1.8 pp"
def not_meaningful(label: str = "n/m") -> str:              # "n/m"
```

Rules: fixed precision (money 2dp, percent/points 1dp), `,` grouping, `€` glyph, explicit sign on
points; output is a pure function of the input (no locale/clock). These functions are the ONLY
place a figure becomes display text — the ×100 for percent lives here, never in the UI.

## Block 4 served DTOs gain display fields

- **PnlCellView**: `{ value: string, display: string, value_kind: string, is_margin: boolean }`.
- **FlaggedVarianceView**: the existing flag fields PLUS
  `current_display`, `comparator_display`, `abs_display | null`, `pct_display | null`,
  `pp_display | null`. Raw decimal-string fields are unchanged (provenance).
- These `*View` shapes are served from NEW endpoints `GET /pnl/view` and `GET /variances/view`.
  The existing `GET /pnl` and `GET /variances` stay byte-pure (raw engine output) so Block 4's
  verbatim pass-through tests remain green — zero regression. The UI consumes the `/view` endpoints.

## Guarantees

- Every figure the UI shows has a Python-produced `display` string in the response.
- Raw values remain (for stable keys/sorting); the UI uses `display` for all rendering.
- A Block 1 test covers `format.py` (exact strings for representative values); a Block 4 test
  covers that `*View` DTOs carry display strings matching `format.py`.

## Contract tests

- `format.money(Decimal("78600.00")) == "€78,600.00"`; `format.percent(Decimal("0.166667")) ==
  "16.7%"`; `format.points(Decimal("0.017857")) == "+1.8 pp"`.
- `GET /variances` items include `*_display` strings equal to `format.*` of the raw values.
- The UI render test asserts a cell's text equals the served `display` exactly (SC-001).
