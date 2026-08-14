"use client";

import { useCallback, useEffect, useState } from "react";
import { TransferForm } from "../components/transfer-form";
import { TransferList } from "../components/transfer-list";
import { createTransfer, listTransfers } from "../lib/api";
import type { Transfer } from "../lib/types";

export default function DashboardPage() {
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadTransfers = useCallback(async () => {
    try {
      const data = await listTransfers();
      setTransfers(data);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load transfers.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(loadTransfers);
  }, [loadTransfers]);

  return (
    <>
      <section className="hero" aria-labelledby="hero-heading">
        <p className="eyebrow">Oneremit PayOut</p>
        <h1 id="hero-heading" className="hero-title">
          Fast, transparent payouts
        </h1>
        <p className="hero-subtitle">
          Create and track payouts to recipients around the world from a single
          dashboard.
        </p>
      </section>

      <div className="dashboard-grid">
        <section className="dashboard-column" aria-labelledby="create-heading">
          <h2 id="create-heading">Create a transfer</h2>
          <TransferForm
            onCreate={createTransfer}
            onCreated={() => void loadTransfers()}
          />
          <p className="webhook-note">
            Provider outcomes (completed / failed) are delivered by a signed
            webhook. Simulate one from your terminal with <code>curl</code> — see{" "}
            <code>docs/api.md</code> for the exact payload and signature. The
            signing secret is never exposed in the browser.
          </p>
        </section>

        <section className="dashboard-column" aria-labelledby="list-heading">
          <div className="list-heading">
            <h2 id="list-heading">Transfers</h2>
            <button
              type="button"
              className="button button--ghost"
              onClick={() => void loadTransfers()}
              disabled={loading}
            >
              Refresh
            </button>
          </div>
          <TransferList
            transfers={transfers}
            loading={loading}
            error={error}
            onRetry={() => void loadTransfers()}
          />
        </section>
      </div>
    </>
  );
}
