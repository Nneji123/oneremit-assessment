import Image from "next/image";
import type { Transfer } from "../lib/types";
import { StatusBadge } from "./status-badge";
import { TransferActions, type TransferAction } from "./transfer-actions";
import {
  TransferSimulate,
  type SimulateStatus,
} from "./transfer-simulate";
import { formatAmount, formatDateTime } from "../lib/format";

const STAGES: Array<[string, string]> = [
  ["Created", "Transfer received"],
  ["Processing", "Submitted to provider"],
  ["Outcome", "Provider confirmed"],
];

function stageRank(status: Transfer["status"]): number {
  switch (status) {
    case "pending":
      return 0;
    case "processing":
      return 1;
    default:
      return 2;
  }
}

function stageDescription(status: Transfer["status"], stage: string): string {
  if (stage !== "Outcome") {
    return STAGES.find(([label]) => label === stage)?.[1] ?? "";
  }
  switch (status) {
    case "failed":
      return "Payment failed";
    case "cancelled":
      return "Transfer cancelled";
    default:
      return "Provider confirmed";
  }
}

function outcomeModifier(status: Transfer["status"]): string {
  if (status === "failed") return "receipt-step--failed";
  if (status === "cancelled") return "receipt-step--cancelled";
  return "";
}

function stepMark(status: Transfer["status"], stage: string, reached: boolean): string {
  if (stage !== "Outcome" || !reached) {
    return "";
  }
  switch (status) {
    case "failed":
      return "✕";
    case "cancelled":
      return "–";
    case "completed":
      return "✓";
    default:
      return "";
  }
}

export function TransferDetail({
  transfer,
  busy,
  actionError,
  simBusy,
  simError,
  onAction,
  onSimulate,
  onRefresh,
}: {
  transfer: Transfer;
  busy: TransferAction | null;
  actionError: string | null;
  simBusy: SimulateStatus | null;
  simError: string | null;
  onAction: (action: TransferAction) => void;
  onSimulate: (status: SimulateStatus) => void;
  onRefresh: () => void;
}) {
  const rank = stageRank(transfer.status);
  return (
    <article className="card receipt-card">
      <Image
        className="receipt-card__globe"
        src="/oneremit-globe-dots.png"
        alt=""
        fill
        sizes="(max-width: 960px) 100vw, 960px"
        aria-hidden="true"
      />
      <div className="receipt-card__content">
        <div className="receipt-brandbar">
          <Image
            src="/oneremit-logo.svg"
            alt="Oneremit"
            width={138}
            height={26}
            priority
          />
          <span>PayOut receipt</span>
        </div>

        <div className="receipt-heading">
          <div>
            <p className="receipt-kicker">Transfer receipt</p>
            <h1>{transfer.reference}</h1>
          </div>
          <StatusBadge status={transfer.status} />
        </div>

        <div className="receipt-total">
          <span className="receipt-total__label">Total payout</span>
          <strong>{formatAmount(transfer.amount, transfer.currency)}</strong>
          <span className="receipt-total__recipient">
            Recipient: {transfer.recipient_ref}
          </span>
        </div>

        <ol className="receipt-timeline" aria-label="Transfer progress">
          {STAGES.flatMap(([label], index) => {
            const reached = index <= rank;
            const isLast = index === STAGES.length - 1;
            const items = [
              <li
                className={`receipt-step ${reached ? "receipt-step--active" : ""} ${
                  index === rank ? "receipt-step--current" : ""
                } ${isLast && reached ? outcomeModifier(transfer.status) : ""}`}
                key={label}
              >
                <span className="receipt-step__dot" aria-hidden="true">
                  {stepMark(transfer.status, label, reached)}
                </span>
                <span className="receipt-step__text">
                  <strong>{label}</strong>
                  <small>{stageDescription(transfer.status, label)}</small>
                </span>
              </li>,
            ];
            if (!isLast) {
              items.push(
                <li
                  className={`receipt-step__connector ${
                    index < rank ? "receipt-step__connector--active" : ""
                  }`}
                  key={`${label}-connector`}
                  aria-hidden="true"
                >
                  <svg viewBox="0 0 16 16" width="14" height="14">
                    <path
                      d="M4 2l6 6-6 6"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </li>,
              );
            }
            return items;
          })}
        </ol>

        <dl className="detail-grid">
          <div>
            <dt>Currency</dt>
            <dd>{transfer.currency}</dd>
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
          <TransferSimulate
            status={transfer.status}
            busy={simBusy}
            onSimulate={onSimulate}
          />
          <button
            type="button"
            className="button button--ghost"
            onClick={onRefresh}
            disabled={busy !== null || simBusy !== null}
          >
            Refresh
          </button>
        </div>

        {actionError && (
          <p className="form-error" role="alert" aria-live="assertive">
            {actionError}
          </p>
        )}
        {simError && (
          <p className="form-error" role="alert" aria-live="assertive">
            {simError}
          </p>
        )}

        <p className="receipt-footnote">
          This receipt reflects the latest state recorded by the payout service.
        </p>
      </div>
    </article>
  );
}
