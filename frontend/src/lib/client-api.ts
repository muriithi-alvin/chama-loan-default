"use client";

import type { ApiErrorBody } from "./types";

// Browser calls go to /api/* on this site; Next.js forwards them to the
// Python API. Every change carries the session's CSRF token (X2).

export class ApiProblem extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public ref?: string,
    public field?: string,
  ) {
    super(message);
  }
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)chama_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

export function sessionEnded() {
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.assign(`/signin?ended=1&next=${next}`);
}

type Options = { method?: string; json?: unknown; body?: BodyInit; signal?: AbortSignal };

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const method = options.method ?? (options.json !== undefined || options.body ? "POST" : "GET");
  const headers: Record<string, string> = { accept: "application/json" };
  if (method !== "GET") headers["x-csrf-token"] = csrfToken();
  let body = options.body;
  if (options.json !== undefined) {
    headers["content-type"] = "application/json";
    body = JSON.stringify(options.json);
  }
  let response: Response;
  try {
    response = await fetch(path, { method, headers, body, signal: options.signal, credentials: "same-origin" });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiProblem(0, "offline", "Could not reach Kibaba. Check the connection and try again.");
  }
  if (response.status === 401 && !path.startsWith("/api/session")) {
    sessionEnded();
    throw new ApiProblem(401, "signed_out", "Your session ended. Sign in again to carry on.");
  }
  if (!response.ok) {
    const problem = (await response.json().catch(() => null)) as ApiErrorBody | null;
    throw new ApiProblem(
      response.status,
      problem?.error.code ?? "unknown",
      problem?.error.message ?? "Kibaba could not finish this. Try again.",
      problem?.error.ref,
      problem?.error.field,
    );
  }
  return (await response.json()) as T;
}

/** SWR fetcher for GET requests. */
export const fetcher = <T,>(path: string) => api<T>(path);
