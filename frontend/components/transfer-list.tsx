import Link from "next/link";
import type { Transfer } from "../lib/types";
import { StatusBadge } from "./status-badge";
import { formatAmount } from "../lib/format";

export function TransferList({
  transfers,
  loading,
  error,
  onRetry,
}: {
  transfers: Transfer[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  if (loading && transfers.length === 0) {
    return (
      <div className="list-state" role="status">
        Loading transfers…
      </div>
    );
  }

  if (error && transfers.length === 0) {
    return (
      <div className="list-state list-state--error" role="alert">
        <p className="list-state__message">{error}</p>
        <button type="button" className="button button--ghost" onClick={onRetry}>
          Retry
        </button>
      </div>
    );
  }

  if (transfers.length === 0) {
    return (
      <div className="list-state" role="status">
        No transfers yet. Create your first one.
      </div>
    );
  }

  return (
    <ul className="transfer-list">
      {transfers.map((transfer) => (
        <li key={transfer.id}>
          <Link
            href={`/transfers/${transfer.id}`}
            className="transfer-row"
            aria-label={`View transfer ${transfer.reference}`}
          >
            <span className="transfer-row__main">
              <span className="transfer-row__reference">
                {transfer.reference}
              </span>
              <span className="transfer-row__meta">
                {transfer.recipient_ref}
              </span>
            </span>
            <span className="transfer-row__amount">
              {formatAmount(transfer.amount, transfer.currency)}
            </span>
            <StatusBadge status={transfer.status} />
          </Link>
        </li>
      ))}
    </ul>
  );
}