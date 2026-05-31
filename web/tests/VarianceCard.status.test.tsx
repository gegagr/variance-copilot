import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { VarianceCard } from "@/components/VarianceCard";
import { flags } from "./fixtures";

const v = flags[0] as any; // ebitda flag with display strings

function card() {
  return screen.getByTestId(`card-${v.flag_id}`);
}

describe("VarianceCard status variants", () => {
  it("detected → Investigate only", () => {
    render(<VarianceCard variance={v} item={null} />);
    expect(card()).toHaveAttribute("data-status", "detected");
    expect(within(card()).getByRole("button", { name: "Investigate" })).toBeInTheDocument();
    expect(within(card()).queryByRole("button", { name: "Accept" })).not.toBeInTheDocument();
  });

  it("investigating → disabled, no controls", () => {
    render(<VarianceCard variance={v} item={{ status: "detected" } as any} busy />);
    expect(card()).toHaveAttribute("data-status", "investigating");
    expect(within(card()).queryByRole("button", { name: "Investigate" })).not.toBeInTheDocument();
  });

  it("awaiting_controller → question + hypothesis + answer + Submit (disabled until typed)", () => {
    const item = {
      status: "awaiting_controller",
      record: { question: { text: "Why up?", hypothesis: { text: "Late booking." } } },
    } as any;
    render(<VarianceCard variance={v} item={item} />);
    expect(screen.getByText("Why up?")).toBeInTheDocument();
    expect(screen.getByText(/Late booking/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Dismiss" })).toBeInTheDocument();
  });

  it("drafted → commentary + Accept/Edit/Dismiss", () => {
    const item = { status: "drafted", original_draft: { commentary: "EBITDA up." } } as any;
    render(<VarianceCard variance={v} item={item} />);
    expect(screen.getByText("EBITDA up.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Accept" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dismiss" })).toBeInTheDocument();
  });

  it("accepted → settled, Edit/Dismiss, no Accept", () => {
    const item = { status: "accepted", original_draft: { commentary: "Final." } } as any;
    render(<VarianceCard variance={v} item={item} />);
    expect(card()).toHaveAttribute("data-status", "accepted");
    expect(screen.getByText("Final.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Accept" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
  });

  it("dismissed → settled, no actions", () => {
    render(<VarianceCard variance={v} item={{ status: "dismissed" } as any} />);
    expect(card()).toHaveAttribute("data-status", "dismissed");
    expect(within(card()).queryByRole("button")).not.toBeInTheDocument();
  });

  it("failed → shows the error reason + Retry/Dismiss", () => {
    const item = { status: "failed", error: "model returned prose under forced emit" } as any;
    render(<VarianceCard variance={v} item={item} />);
    expect(card()).toHaveAttribute("data-status", "failed");
    expect(screen.getByText(/model returned prose/)).toBeInTheDocument();
    expect(within(card()).getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(within(card()).getByRole("button", { name: "Dismiss" })).toBeInTheDocument();
  });

  it("renders variance figures from served display strings (no compute)", () => {
    render(<VarianceCard variance={v} item={null} />);
    expect(card()).toHaveTextContent("€78,600.00");
    expect(card()).toHaveTextContent("€66,000.00");
    expect(card()).toHaveTextContent("19.1%");
  });
});
