import { afterEach, describe, expect, it, vi } from "vitest";
import { notifyTransferCompleted } from "../lib/notifications";

const transfer = {
  id: "transfer-1",
  reference: "TRF-123",
  amount: "100.00",
  currency: "NGN",
  recipient_ref: "recipient-1",
  status: "completed" as const,
  provider_transfer_id: "prov-1",
  created_at: "2026-08-14T09:00:00Z",
  updated_at: "2026-08-14T09:01:00Z",
};

afterEach(() => {
  vi.restoreAllMocks();
  Object.defineProperty(window, "Notification", {
    configurable: true,
    value: undefined,
  });
});

describe("notifyTransferCompleted", () => {
  it("uses the native Notification API for a completed transfer", async () => {
    const NotificationMock = vi.fn();
    Object.assign(NotificationMock, {
      permission: "granted",
      requestPermission: vi.fn().mockResolvedValue("granted"),
    });
    Object.defineProperty(window, "Notification", {
      configurable: true,
      value: NotificationMock,
    });

    await notifyTransferCompleted(transfer);

    expect(NotificationMock).toHaveBeenCalledWith("Payout completed", {
      body: "TRF-123 has been completed successfully.",
      icon: "/favicon.svg",
      tag: "transfer-transfer-1-completed",
    });
  });
});
