import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "@/App";
import { renderWithClient } from "./util";
import { requested } from "./msw/handlers";

const EBITDA = "ebitda|ytd|current_vs_prior_year";
const REVENUE = "revenue|ytd|current_vs_prior_year"; // only present at period 6 (full fixture set)

describe("as-of period selector", () => {
  it("defaults to the latest period (6) and populates the queue", async () => {
    renderWithClient(<App />);
    await screen.findByTestId(`card-${EBITDA}`);
    // the full fixture flag set is shown for the default month
    expect(screen.getByTestId(`card-${REVENUE}`)).toBeInTheDocument();
    // every initial query carried current_period=6
    await waitFor(() => expect(requested.review).toContain(6));
    expect(requested.variances).toContain(6);
    expect(requested.pnl).toContain(6);
    // the default selector tab is Jun (P6)
    expect(screen.getByRole("tab", { name: "Jun (P6)" })).toHaveAttribute("aria-selected", "true");
  });

  it("changing the as-of period refetches grid, variances, and review for that period", async () => {
    const { user } = renderWithClient(<App />);
    await screen.findByTestId(`card-${EBITDA}`);
    expect(screen.getByTestId(`card-${REVENUE}`)).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "May (P5)" }));

    // all three queries refetched for the new period
    await waitFor(() => expect(requested.review).toContain(5));
    expect(requested.variances).toContain(5);
    expect(requested.pnl).toContain(5);

    // period 5 serves a distinct (smaller) set: the REVENUE card is gone, EBITDA remains
    await waitFor(() => expect(screen.queryByTestId(`card-${REVENUE}`)).toBeNull());
    expect(screen.getByTestId(`card-${EBITDA}`)).toBeInTheDocument();
  });

  it("the time-cut selector still slices relative to the held as-of period", async () => {
    const { user } = renderWithClient(<App />);
    await screen.findByTestId(`card-${EBITDA}`);
    const pnlCallsBefore = requested.pnl.length;

    await user.click(screen.getByRole("tab", { name: "Current month" }));

    // a fresh P&L fetch for the SAME as-of period (6); the as-of selector is unchanged
    await waitFor(() => expect(requested.pnl.length).toBeGreaterThan(pnlCallsBefore));
    expect(requested.pnl.every((p) => p === 6)).toBe(true);
    expect(screen.getByRole("tab", { name: "Jun (P6)" })).toHaveAttribute("aria-selected", "true");
  });
});
