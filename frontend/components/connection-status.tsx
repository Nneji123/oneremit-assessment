export type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "offline";

const LABELS: Record<ConnectionStatus, string> = {
  connecting: "Connecting…",
  connected: "Live",
  reconnecting: "Reconnecting…",
  offline: "Offline",
};

export function ConnectionStatus({ status }: { status: ConnectionStatus }) {
  return (
    <span className={`connection-status connection-status--${status}`} role="status">
      <span className="connection-status__dot" aria-hidden="true" />
      {LABELS[status]}
    </span>
  );
}
