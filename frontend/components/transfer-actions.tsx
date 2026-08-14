import type { TransferStatus } from "../lib/types";

export type TransferAction = "submit" | "cancel";

export function TransferActions({
  status,
  busy,
  onAction,
}: {
  status: TransferStatus;
  busy?: TransferAction | null;
  onAction: (action: TransferAction) => void;
}) {
  if (status !== "pending") {
    return null;
  }

  const disabled = busy !== null && busy !== undefined;

  return (
    <div className="transfer-actions">
      <button
        type="button"
        className="button button--primary"
        onClick={() => onAction("submit")}
        disabled={disabled}
        aria-busy={busy === "submit"}
      >
        Submit
      </button>
      <button
        type="button"
        className="button button--ghost"
        onClick={() => onAction("cancel")}
        disabled={disabled}
        aria-busy={busy === "cancel"}
      >
        Cancel
      </button>
    </div>
  );
}