"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { TransferDetail } from "../../../components/transfer-detail";
import type { TransferAction } from "../../../components/transfer-actions";
import {
  ApiError,
  cancelTransfer,
  getTransfer,
  submitTransfer,
} from "../../../lib/api";
import type { Transfer } from "../../../lib/types";

const POLL_INTERVAL_MS = 2000;

export default function TransferDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [transfer, setTransfer] = useState<Transfer | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState<TransferAction | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await getTransfer(id);
      setTransfer(data);
      setLoadError(null);
      setNotFound(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setNotFound(true);
        setTransfer(null);
      } else {
        setLoadError(
          err instanceof Error ? err.message : "Could not load the transfer.",
        );
      }
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void Promise.resolve().then(load);
  }, [load]);

  const status = transfer?.status;

  useEffect(() => {
    if (status !== "processing") {
      return;
    }
    const interval = setInterval(() => {
      void load();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [status, load]);

  const handleAction = async (action: TransferAction) => {
    setBusy(action);
    setActionError(null);
    try {
      const updated =
        action === "submit"
          ? await submitTransfer(id)
          : await cancelTransfer(id);
      setTransfer(updated);
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Action failed. Please retry.",
      );
    } finally {
      setBusy(null);
    }
  };

  let content;
  if (loading) {
    content = (
      <div className="page-status" role="status">
        <h1>Loading transfer…</h1>
      </div>
    );
  } else if (notFound) {
    content = (
      <div className="page-status" role="alert">
        <h1>Transfer not found</h1>
        <p>The transfer could not be found or is no longer available.</p>
        <Link href="/" className="button button--ghost">
          Back to dashboard
        </Link>
      </div>
    );
  } else if (loadError && !transfer) {
    content = (
      <div className="page-status" role="alert">
        <h1>Something went wrong</h1>
        <p>{loadError}</p>
        <button
          type="button"
          className="button button--ghost"
          onClick={() => void load()}
        >
          Retry
        </button>
      </div>
    );
  } else if (transfer) {
    content = (
      <TransferDetail
        transfer={transfer}
        busy={busy}
        actionError={actionError}
        onAction={(action) => void handleAction(action)}
        onRefresh={() => void load()}
      />
    );
  }

  return (
    <div>
      <Link href="/" className="back-link">
        ← Back to dashboard
      </Link>
      {content}
      <p className="webhook-note">
        Provider outcomes (completed / failed) are delivered by a signed
        webhook. Simulate one from your terminal with <code>curl</code> — see{" "}
        <code>docs/api.md</code> for the exact payload and signature. The
        signing secret is never exposed in the browser.
      </p>
    </div>
  );
}