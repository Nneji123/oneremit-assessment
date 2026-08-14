import type { ApiErrorBody, CreateTransferPayload, Transfer } from "./types";

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

  let body: ApiErrorBody | T | null = null;
  try {
    body = (await response.json()) as ApiErrorBody | T;
  } catch {
    body = null;
  }

  if (!response.ok) {
    const detail =
      (body as ApiErrorBody | null)?.detail ??
      `Request failed with status ${response.status}.`;
    throw new ApiError(detail, response.status);
  }

  return body as T;
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