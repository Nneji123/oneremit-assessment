import type { Transfer } from "../lib/types";
import { StatusBadge } from "./status-badge";
import { TransferActions, type TransferAction } from "./transfer-actions";
import { formatAmount, formatDateTime } from "../lib/format";

export function TransferDetail({
  transfer,
  busy,
  actionError,
  onAction,
  onRefresh,
}: {
  transfer: Transfer;
  busy: TransferAction | null;
  actionError: string | null;
  onAction: (action: TransferAction) => void;
  onRefresh: () => void;
}) {
  return (
    <article className="card">
      <div className="detail-header">
        <div>
          <p className="eyebrow">Transfer</p>
          <h2>{transfer.reference}</h2>
        </div>
        <StatusBadge status={transfer.status} />
      </div>

      <dl className="detail-grid">
        <div>
          <dt>Amount</dt>
          <dd>{formatAmount(transfer.amount, transfer.currency)}</dd>
        </div>
        <div>
          <dt>Currency</dt>
          <dd>{transfer.currency}</dd>
        </div>
        <div>
          <dt>Recipient</dt>
          <dd>{transfer.recipient_ref}</dd>
        </div>
        <div>
          <dt>Provider transfer ID</dt>
          <dd>{transfer.provider_transfer_id ?? "—"}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{formatDateTime(transfer.created_at)}</dd>
        </div>
        <div>
          <dt>Updated</dt>
          <dd>{formatDateTime(transfer.updated_at)}</dd>
        </div>
      </dl>

      <div className="detail-actions">
        <TransferActions status={transfer.status} busy={busy} onAction={onAction} />
        <button
          type="button"
          className="button button--ghost"
          onClick={onRefresh}
          disabled={busy !== null}
        >
          Refresh
        </button>
      </div>

      {actionError && (
        <p className="form-error" role="alert" aria-live="assertive">
          {actionError}
        </p>
      )}
    </article>
  );
}