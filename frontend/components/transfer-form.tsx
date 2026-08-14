"use client";

import { useState, type FormEvent } from "react";
import type { CreateTransferPayload, Transfer } from "../lib/types";
import { CURRENCIES } from "../lib/types";

export function TransferForm({
  onCreate,
  onCreated,
}: {
  onCreate: (payload: CreateTransferPayload) => Promise<Transfer>;
  onCreated?: (transfer: Transfer) => void;
}) {
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState<string>(CURRENCIES[0]);
  const [recipientRef, setRecipientRef] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const transfer = await onCreate({
        amount,
        currency,
        recipient_ref: recipientRef,
      });
      setAmount("");
      setRecipientRef("");
      onCreated?.(transfer);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not create the transfer.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="card" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="transfer-amount">Amount</label>
        <input
          id="transfer-amount"
          name="amount"
          type="text"
          inputMode="decimal"
          autoComplete="off"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          required
        />
      </div>

      <div className="field">
        <label htmlFor="transfer-currency">Currency</label>
        <select
          id="transfer-currency"
          name="currency"
          value={currency}
          onChange={(event) => setCurrency(event.target.value)}
        >
          {CURRENCIES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>

      <div className="field">
        <label htmlFor="transfer-recipient">Recipient reference</label>
        <input
          id="transfer-recipient"
          name="recipient_ref"
          type="text"
          autoComplete="off"
          maxLength={255}
          value={recipientRef}
          onChange={(event) => setRecipientRef(event.target.value)}
          required
        />
      </div>

      {error && (
        <p className="form-error" role="alert" aria-live="assertive">
          {error}
        </p>
      )}

      <button
        type="submit"
        className="button button--primary"
        disabled={submitting}
        aria-busy={submitting}
      >
        {submitting ? "Creating…" : "Create transfer"}
      </button>
    </form>
  );
}