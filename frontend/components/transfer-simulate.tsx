import type { TransferStatus } from "../lib/types";

export type SimulateStatus = "completed" | "failed";

export function TransferSimulate({
  status,
  busy,
  onSimulate,
}: {
  status: TransferStatus;
  busy?: SimulateStatus | null;
  onSimulate: (status: SimulateStatus) => void;
}) {
  if (status !== "processing") {
    return null;
  }

  const disabled = busy !== null && busy !== undefined;

  return (
    <div className="simulate-controls">
      <span className="simulate-controls__label">Simulate provider event</span>
      <button
        type="button"
        className="button button--accent"
        onClick={() => onSimulate("completed")}
        disabled={disabled}
        aria-busy={busy === "completed"}
      >
        Simulate completed
      </button>
      <button
        type="button"
        className="button button--ghost"
        onClick={() => onSimulate("failed")}
        disabled={disabled}
        aria-busy={busy === "failed"}
      >
        Simulate failed
      </button>
    </div>
  );
}
