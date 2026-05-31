import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "@/App";
import { renderWithClient } from "./util";

const EBITDA = "ebitda|ytd|current_vs_prior_year";
const REVENUE = "revenue|ytd|current_vs_prior_year";

describe("bidirectional anchoring", () => {
  it("selecting a grid line focuses its card; selecting a card highlights its line", async () => {
    const { user } = renderWithClient(<App />);

    // Wait for the workspace to load (grid + cards).
    await waitFor(() => expect(screen.getByTestId("grid-row-ebitda")).toBeInTheDocument());
    await screen.findByTestId(`card-${EBITDA}`);

    // Grid line → card focus.
    await user.click(screen.getByTestId("grid-row-ebitda"));
    await waitFor(() =>
      expect(screen.getByTestId(`card-${EBITDA}`)).toHaveAttribute("data-selected", "true"),
    );

    // Card → grid line highlight.
    await user.click(screen.getByTestId(`card-${REVENUE}`));
    await waitFor(() =>
      expect(screen.getByTestId("grid-row-revenue")).toHaveAttribute("data-selected", "true"),
    );
  });
});
