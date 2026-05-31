import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "@/App";
import { server } from "./setup";
import { http, HttpResponse } from "msw";
import { renderWithClient } from "./util";

const EBITDA = "ebitda|ytd|current_vs_prior_year";
const REVENUE = "revenue|ytd|current_vs_prior_year"; // QUESTION flag

async function loadWorkspace() {
  const r = renderWithClient(<App />);
  await r.findByTestId(`card-${EBITDA}`);
  // Wait for the clean baseline (review query settled) before the test acts.
  await waitFor(() => {
    expect(status(EBITDA)).toBe("detected");
    expect(status(REVENUE)).toBe("detected");
  });
  return r;
}
const card = (id: string) => screen.getByTestId(`card-${id}`);
const status = (id: string) => card(id).getAttribute("data-status");

describe("review flows", () => {
  it("investigate → drafted, then accept → accepted (progress updates)", async () => {
    const { user } = await loadWorkspace();
    await user.click(within(card(EBITDA)).getByRole("button", { name: "Investigate" }));
    await waitFor(() => expect(status(EBITDA)).toBe("drafted"));
    expect(card(EBITDA)).toHaveTextContent("EBITDA outperformed");

    await user.click(within(card(EBITDA)).getByRole("button", { name: "Accept" }));
    await waitFor(() => expect(status(EBITDA)).toBe("accepted"));
    await waitFor(() => expect(screen.getByText(/resolved/)).toHaveTextContent("1 / 3 resolved"));
  });

  it("question → answer → drafted", async () => {
    const { user } = await loadWorkspace();
    await user.click(within(card(REVENUE)).getByRole("button", { name: "Investigate" }));
    await waitFor(() => expect(status(REVENUE)).toBe("awaiting_controller"));
    expect(card(REVENUE)).toHaveTextContent(/enterprise contract/);

    await user.type(within(card(REVENUE)).getByLabelText("Your answer"), "Yes, the new contract.");
    await user.click(within(card(REVENUE)).getByRole("button", { name: "Submit" }));
    await waitFor(() => expect(status(REVENUE)).toBe("drafted"));
  });

  it("edit then accept → accepted reflects the edit", async () => {
    const { user } = await loadWorkspace();
    await user.click(within(card(EBITDA)).getByRole("button", { name: "Investigate" }));
    await waitFor(() => expect(status(EBITDA)).toBe("drafted"));

    await user.click(within(card(EBITDA)).getByRole("button", { name: "Edit" }));
    const editor = within(card(EBITDA)).getByLabelText("Edit commentary");
    await user.clear(editor);
    await user.type(editor, "Controller's revised wording.");
    await user.click(within(card(EBITDA)).getByRole("button", { name: "Save & accept" }));

    await waitFor(() => expect(status(EBITDA)).toBe("accepted"));
    expect(card(EBITDA)).toHaveTextContent("Controller's revised wording.");
  });

  it("dismiss → dismissed", async () => {
    const { user } = await loadWorkspace();
    await user.click(within(card(EBITDA)).getByRole("button", { name: "Investigate" }));
    await waitFor(() => expect(status(EBITDA)).toBe("drafted"));
    await user.click(within(card(EBITDA)).getByRole("button", { name: "Dismiss" }));
    await waitFor(() => expect(status(EBITDA)).toBe("dismissed"));
  });

  it("a rejected action (409) surfaces an error and the card reflects the API status", async () => {
    const { user } = await loadWorkspace();
    await user.click(within(card(EBITDA)).getByRole("button", { name: "Investigate" }));
    await waitFor(() => expect(status(EBITDA)).toBe("drafted"));

    // Force the next accept to 409.
    server.use(
      http.post("/api/review/:flagId/accept", () =>
        HttpResponse.json({ detail: "cannot accept from drafted" }, { status: 409 }),
      ),
    );
    await user.click(within(card(EBITDA)).getByRole("button", { name: "Accept" }));
    await waitFor(() => expect(card(EBITDA)).toHaveTextContent(/cannot accept/));
    expect(status(EBITDA)).toBe("drafted"); // unchanged — reflects the API, not an optimistic guess
  });

  it("investigate all runs pending cards sequentially", async () => {
    const { user } = await loadWorkspace();
    await user.click(screen.getByRole("button", { name: "Investigate all" }));
    await waitFor(() => expect(status(EBITDA)).toBe("drafted"));
    await waitFor(() => expect(status(REVENUE)).toBe("awaiting_controller"));
  });
});
