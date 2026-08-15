import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { TransferDetail } from "./transfer-detail";
import type { Transfer } from "../lib/types";

vi.mock("next/image", () => ({
  default: (props: { src: string; alt?: string }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={props.src} alt={props.alt ?? ""} />
  ),
}));

function makeTransfer(overrides: Partial<Transfer> = {}): Transfer {
  return {
    id: "t_123",
    reference: "ref_x6kq",
    amount: "1000.00",
    currency: "NGN",
    recipient_ref: "recipient_ab12",
    status: "completed",
    provider_transfer_id: "prov_1",
    created_at: "2026-08-14T09:00:00Z",
    updated_at: "2026-08-14T09:30:00Z",
    ...overrides,
  };
}

function renderReceipt(transfer: Transfer) {
  return render(
    <TransferDetail
      transfer={transfer}
      busy={null}
      actionError={null}
      simBusy={null}
      simError={null}
      onAction={vi.fn()}
      onSimulate={vi.fn()}
      onRefresh={vi.fn()}
    />,
  );
}

function timelineSteps() {
  const timeline = screen.getByRole("list", { name: "Transfer progress" });
  return Array.from(timeline.children).filter((child) =>
    child.className.split(" ").includes("receipt-step"),
  );
}

describe("TransferDetail receipt", () => {
  it("shows_receipt_branding_and_reference", () => {
    renderReceipt(makeTransfer());

    expect(screen.getByText("PayOut receipt")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "ref_x6kq" })).toBeTruthy();
  });

  it("shows_total_payout_recipient_and_metadata", () => {
    renderReceipt(makeTransfer());

    expect(screen.getByText("Total payout")).toBeTruthy();
    expect(screen.getByText("₦1,000.00")).toBeTruthy();
    expect(screen.getByText("Recipient: recipient_ab12")).toBeTruthy();
    expect(screen.getByText("Provider transfer ID")).toBeTruthy();
    expect(screen.getByText("prov_1")).toBeTruthy();
    expect(screen.getByText("NGN")).toBeTruthy();
  });

  it("marks_timeline_complete_for_completed_transfer", () => {
    renderReceipt(makeTransfer({ status: "completed" }));

    const steps = timelineSteps();
    expect(steps.length).toBe(3);
    expect(
      steps.every((step) => step.className.includes("receipt-step--active")),
    ).toBe(true);
  });

  it("marks_processing_step_current_for_processing_transfer", () => {
    renderReceipt(makeTransfer({ status: "processing" }));

    const active = timelineSteps().filter((step) =>
      step.className.includes("receipt-step--active"),
    );
    expect(active.length).toBe(2);
  });
});
