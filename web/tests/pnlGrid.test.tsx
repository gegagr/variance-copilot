import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PnlGrid } from "@/components/PnlGrid";
import { pnlView } from "./fixtures";

const flagged = new Set(["ebitda", "revenue"]);

describe("PnlGrid", () => {
  it("renders line / subtotal / margin rows and marks flagged lines", () => {
    render(
      <PnlGrid pnl={pnlView as any} timeCut="ytd" flaggedLines={flagged} selectedLine={null} onSelectLine={() => {}} />,
    );
    expect(screen.getByTestId("grid-row-revenue")).toBeInTheDocument();
    expect(screen.getByTestId("grid-row-gross_profit")).toBeInTheDocument(); // subtotal
    expect(screen.getByTestId("grid-row-gross_margin_pct")).toBeInTheDocument(); // margin
    expect(screen.getByTestId("marker-ebitda")).toBeInTheDocument();
    expect(screen.queryByTestId("marker-cogs")).not.toBeInTheDocument(); // not flagged
  });

  it("renders each figure verbatim from the served display string (SC-001)", () => {
    render(
      <PnlGrid pnl={pnlView as any} timeCut="ytd" flaggedLines={flagged} selectedLine={null} onSelectLine={() => {}} />,
    );
    // ebitda current_year ytd display string from the fixture, char-for-char.
    const row = screen.getByTestId("grid-row-ebitda");
    expect(row).toHaveTextContent("€78,600.00");
    // margin row shows a percent display, never recomputed.
    expect(screen.getByTestId("grid-row-gross_margin_pct")).toHaveTextContent("48.7%");
  });
});
