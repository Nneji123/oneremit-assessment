import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { TransferActions } from "./transfer-actions";
import type { TransferStatus } from "../lib/types";

function renderActions(status: TransferStatus) {
  const onAction = vi.fn();
  render(<TransferActions status={status} busy={null} onAction={onAction} />);
  return onAction;
}

describe("TransferActions", () => {
  it("pending_transfer_enables_submit_and_cancel", () => {
    renderActions("pending");

    const submit = screen.getByRole("button", {
      name: "Submit",
    }) as HTMLButtonElement;
    const cancel = screen.getByRole("button", {
      name: "Cancel",
    }) as HTMLButtonElement;

    expect(submit.disabled).toBe(false);
    expect(cancel.disabled).toBe(false);
  });

  it("processing_transfer_disables_or_hides_illegal_actions", () => {
    renderActions("processing");

    expect(screen.queryByRole("button", { name: "Submit" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Cancel" })).toBeNull();
  });

  it("terminal_transfer_has_no_actions", () => {
    for (const status of ["completed", "failed", "cancelled"] as const) {
      const { unmount } = render(
        <TransferActions status={status} busy={null} onAction={vi.fn()} />,
      );

      expect(screen.queryByRole("button", { name: "Submit" })).toBeNull();
      expect(screen.queryByRole("button", { name: "Cancel" })).toBeNull();
      unmount();
    }
  });
});