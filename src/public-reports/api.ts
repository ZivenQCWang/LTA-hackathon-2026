import type { PublicReport } from "../public-app/types";

export interface ReportInbox {
  reports: PublicReport[];
  total: number;
  page: number;
  page_size: number;
  summary: { total: number; received: number; photos: number };
  storage: { backend: string; destination: string };
}

export class InboxError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

const API = (import.meta.env.VITE_API_URL ?? "/api") + "/operator/reports";

export async function requestInbox(
  path: string,
  authorization: string,
  signal?: AbortSignal,
): Promise<Response> {
  const response = await fetch(API + path, {
    signal,
    headers: authorization ? { Authorization: authorization } : {},
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new InboxError(
      typeof body?.detail === "string"
        ? body.detail
        : "Could not load public reports. Please retry.",
      response.status,
    );
  }
  return response;
}

export function basicAuthorization(username: string, password: string): string {
  return (
    "Basic " +
    btoa(
      String.fromCharCode(
        ...new TextEncoder().encode(`${username}:${password}`),
      ),
    )
  );
}
