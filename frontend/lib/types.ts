export const TRANSFER_STATUSES = [
  "pending",
  "processing",
  "completed",
  "failed",
  "cancelled",
] as const;

export type TransferStatus = (typeof TRANSFER_STATUSES)[number];

export const CURRENCIES = ["NGN", "USD", "GBP", "EUR"] as const;

export type TransferCurrency = (typeof CURRENCIES)[number];

export interface Transfer {
  id: string;
  reference: string;
  amount: string;
  currency: string;
  recipient_ref: string;
  status: TransferStatus;
  provider_transfer_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateTransferPayload {
  amount: string;
  currency: string;
  recipient_ref: string;
}

export interface ApiErrorBody {
  detail: string;
}