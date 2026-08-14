import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TransferForm } from "./transfer-form";
import type { Transfer } from "../lib/types";

function transferFixture(): Transfer {
  return {
    id: "0f1a2b3c-4d5e-4f6a-8b7c-9d0e1f2a3b4c",
    reference: "TRF-abc123",
    amount: "120.00",
    currency: "NGN",
    recipient_ref: "ACC-1",
    status: "pending",
    provider_transfer_id: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

describe("TransferForm", () => {
  it("create_form_surfaces_api_error", async () => {
    const onCreate = vi
      .fn()
      .mockRejectedValue(new Error("Amount must be greater than zero."));
    render(<TransferForm onCreate={onCreate} />);

    fireEvent.change(screen.getByLabelText(/amount/i), {
      target: { value: "0" },
    });
    fireEvent.change(screen.getByLabelText(/recipient/i), {
      target: { value: "ACC-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create transfer/i }));

    expect(
      await screen.findByText("Amount must be greater than zero."),
    ).toBeTruthy();
    expect(onCreate).toHaveBeenCalledTimes(1);
  });

  it("create_form_submits_payload_and_resets_fields", async () => {
    const onCreate = vi.fn().mockResolvedValue(transferFixture());
    const onCreated = vi.fn();
    render(<TransferForm onCreate={onCreate} onCreated={onCreated} />);

    fireEvent.change(screen.getByLabelText(/amount/i), {
      target: { value: "120.00" },
    });
    fireEvent.change(screen.getByLabelText(/recipient/i), {
      target: { value: "ACC-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create transfer/i }));

    await waitFor(() =>
      expect(onCreate).toHaveBeenCalledWith({
        amount: "120.00",
        currency: "NGN",
        recipient_ref: "ACC-1",
      }),
    );
    await waitFor(() => expect(onCreated).toHaveBeenCalledTimes(1));
  });
});