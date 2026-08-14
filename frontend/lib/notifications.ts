import type { Transfer } from "./types";

export async function requestTransferNotificationPermission(): Promise<void> {
  if (typeof window === "undefined" || !("Notification" in window)) {
    return;
  }

  if (Notification.permission === "default") {
    try {
      await Notification.requestPermission();
    } catch {
      // Notification permission is optional and browser-controlled.
    }
  }
}

export async function notifyTransferCompleted(transfer: Transfer): Promise<void> {
  if (typeof window === "undefined" || !("Notification" in window)) {
    return;
  }

  await requestTransferNotificationPermission();
  const permission = Notification.permission;

  if (permission !== "granted") {
    return;
  }

  new Notification("Payout completed", {
    body: `${transfer.reference} has been completed successfully.`,
    icon: "/favicon.svg",
    tag: `transfer-${transfer.id}-completed`,
  });
}
