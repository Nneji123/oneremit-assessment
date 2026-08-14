"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
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
        <Image
          className="hero__texture"
          src="/oneremit-hero-bg.png"
          alt=""
          fill
          priority
          sizes="(max-width: 960px) 100vw, 1120px"
        />
        <div className="hero__wash" aria-hidden="true" />
        <div className="hero__content">
          <p className="eyebrow">Oneremit PayOut</p>
          <h1 id="hero-heading" className="hero-title">
            Fast payments from Africa to the world.
          </h1>
          <p className="hero-subtitle">
            Create, submit, and track mock payouts with clear state visibility
            from a single dashboard.
          </p>
          <div className="hero__actions">
            <a className="button button--hero-primary" href="#create-transfer">
              Create transfer <span aria-hidden="true">→</span>
            </a>
            <a className="button button--hero-secondary" href="#transfers">
              View activity <span aria-hidden="true">→</span>
            </a>
          </div>
          <div className="hero__trust">
            <span className="hero__trust-dot" aria-hidden="true" />
            Signed provider events keep every status change traceable
          </div>
        </div>
        <Image
          className="hero__phone"
          src="/oneremit-phone-hand.png"
          alt="Oneremit payment app illustration"
          width={520}
          height={740}
          priority
          sizes="(max-width: 960px) 260px, 520px"
        />
      </section>

      <div className="dashboard-grid">
        <section
          id="create-transfer"
          className="dashboard-column"
          aria-labelledby="create-heading"
        >
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

        <section
          id="transfers"
          className="dashboard-column"
          aria-labelledby="list-heading"
        >
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
          <div className="list-panel">
            <Image
              className="list-panel__map"
              src="/oneremit-world-map-dots.png"
              alt=""
              fill
              sizes="(max-width: 960px) 100vw, 700px"
            />
            <div className="list-panel__content">
              <TransferList
                transfers={transfers}
                loading={loading}
                error={error}
                onRetry={() => void loadTransfers()}
              />
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
