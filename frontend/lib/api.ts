import type { ApiEnvelope, CreateTransferPayload, Transfer } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(detail: string, status: number) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function createIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  let payload: ApiEnvelope<T> | null = null;
  try {
    payload = (await response.json()) as ApiEnvelope<T>;
  } catch {
    payload = null;
  }

  if (!response.ok || payload?.success === false) {
    const message = payload?.message ?? `Request failed (${response.status})`;
    throw new ApiError(message, response.status);
  }

  return payload?.data as T;
}

export function listTransfers(): Promise<Transfer[]> {
  return request<Transfer[]>("/transfers/");
}

export function getTransfer(id: string): Promise<Transfer> {
  return request<Transfer>(`/transfers/${id}/`);
}

export function createTransfer(payload: CreateTransferPayload): Promise<Transfer> {
  return request<Transfer>("/transfers/", {
    method: "POST",
    headers: { "Idempotency-Key": createIdempotencyKey() },
    body: JSON.stringify(payload),
  });
}

export function submitTransfer(id: string): Promise<Transfer> {
  return request<Transfer>(`/transfers/${id}/submit/`, { method: "POST" });
}

export function cancelTransfer(id: string): Promise<Transfer> {
  return request<Transfer>(`/transfers/${id}/cancel/`, { method: "POST" });
}

export function simulateWebhook(
  id: string,
  status: "completed" | "failed",
): Promise<Transfer> {
  return request<Transfer>(`/transfers/${id}/simulate-webhook/`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
}

export function transferWebSocketUrl(id: string): string {
  const explicit = process.env.NEXT_PUBLIC_WS_BASE_URL;
  if (explicit) {
    return `${explicit}/ws/transfers/${id}/`;
  }
  const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";
  if (/^https?:\/\//.test(api)) {
    const wsBase = api
      .replace(/^http/, "ws")
      .replace(/\/api\/?$/, "");
    return `${wsBase}/ws/transfers/${id}/`;
  }
  const protocol =
    typeof window !== "undefined" && window.location.protocol === "https:"
      ? "wss:"
      : "ws:";
  const host =
    typeof window !== "undefined" ? window.location.host : "localhost";
  return `${protocol}//${host}/ws/transfers/${id}/`;
}
