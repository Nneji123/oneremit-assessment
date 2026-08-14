"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ConnectionStatus, type ConnectionStatus as WsStatus } from "../../../components/connection-status";
import { TransferDetail } from "../../../components/transfer-detail";
import type { TransferAction } from "../../../components/transfer-actions";
import type { SimulateStatus } from "../../../components/transfer-simulate";
import {
  ApiError,
  cancelTransfer,
  getTransfer,
  simulateWebhook,
  submitTransfer,
  transferWebSocketUrl,
} from "../../../lib/api";
import type { Transfer } from "../../../lib/types";
import {
  notifyTransferCompleted,
  requestTransferNotificationPermission,
} from "../../../lib/notifications";

export default function TransferDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [transfer, setTransfer] = useState<Transfer | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState<TransferAction | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [simBusy, setSimBusy] = useState<SimulateStatus | null>(null);
  const [simError, setSimError] = useState<string | null>(null);
  const [wsStatus, setWsStatus] = useState<WsStatus>("connecting");
  const wsStatusRef = useRef<WsStatus>("connecting");
  const transferRef = useRef<Transfer | null>(null);
  const loadedRef = useRef(false);

  const updateWsStatus = (status: WsStatus) => {
    wsStatusRef.current = status;
    setWsStatus(status);
  };

  const load = useCallback(async () => {
    try {
      const data = await getTransfer(id);
      transferRef.current = data;
      setTransfer(data);
      loadedRef.current = true;
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

  useEffect(() => {
    let socket: WebSocket | null = null;
    let closed = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let retries = 0;
    const MAX_RETRIES = 5;

    const connect = () => {
      if (closed) {
        return;
      }
      updateWsStatus(retries > 0 ? "reconnecting" : "connecting");
      socket = new WebSocket(transferWebSocketUrl(id));

      socket.onopen = () => {
        retries = 0;
        updateWsStatus("connected");
      };

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data as string) as {
            type?: string;
            transfer?: Transfer;
          };
          if (message.type === "transfer.status" && message.transfer) {
            const previous = transferRef.current;
            transferRef.current = message.transfer;
            setTransfer(message.transfer);
            setNotFound(false);
            setLoadError(null);
            setLoading(false);
            if (
              loadedRef.current &&
              previous?.status !== "completed" &&
              message.transfer.status === "completed"
            ) {
              void notifyTransferCompleted(message.transfer);
            }
          }
        } catch {
          // Ignore malformed frames.
        }
      };

      socket.onclose = () => {
        if (closed) {
          return;
        }
        retries += 1;
        if (retries >= MAX_RETRIES) {
          updateWsStatus("offline");
        } else {
          reconnectTimer = setTimeout(connect, 1500 * retries);
        }
      };

      socket.onerror = () => {
        socket?.close();
      };
    };

    connect();

    return () => {
      closed = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      socket?.close();
    };
  }, [id]);

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

  const handleSimulate = async (status: SimulateStatus) => {
    setSimBusy(status);
    setSimError(null);
    if (status === "completed") {
      void requestTransferNotificationPermission();
    }
    try {
      const updated = await simulateWebhook(id, status);
      // The WebSocket broadcast normally drives the UI; the API response is a
      // graceful fallback when the socket is offline.
      if (wsStatusRef.current === "offline") {
        const previous = transferRef.current;
        transferRef.current = updated;
        setTransfer(updated);
        if (previous?.status !== "completed" && updated.status === "completed") {
          void notifyTransferCompleted(updated);
        }
      }
    } catch (err) {
      setSimError(
        err instanceof Error ? err.message : "Simulation failed. Please retry.",
      );
    } finally {
      setSimBusy(null);
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
        simBusy={simBusy}
        simError={simError}
        onAction={(action) => void handleAction(action)}
        onSimulate={(status) => void handleSimulate(status)}
        onRefresh={() => void load()}
      />
    );
  }

  return (
    <div>
      <div className="detail-topbar">
        <Link href="/" className="back-link">
          ← Back to dashboard
        </Link>
        <ConnectionStatus status={wsStatus} />
      </div>
      {content}
    </div>
  );
}
