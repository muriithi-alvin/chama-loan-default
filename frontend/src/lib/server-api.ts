import "server-only";

import { headers } from "next/headers";
import { forbidden, redirect } from "next/navigation";

import type { ApiErrorBody } from "./types";

// Server components call the Python API directly, passing on the visitor's
// cookies, so pages arrive with their data already in them (fast first paint).
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

export class ApiUnavailableError extends Error {
  constructor(
    message: string,
    public ref?: string,
  ) {
    super(message);
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const incoming = await headers();
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      headers: { cookie: incoming.get("cookie") ?? "", accept: "application/json" },
      cache: "no-store",
    });
  } catch {
    throw new ApiUnavailableError("Kibaba is not answering. Try again in a minute.");
  }
  if (response.status === 401) redirect("/signin?ended=1");
  if (response.status === 403) forbidden();
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorBody | null;
    throw new ApiUnavailableError(
      body?.error.message ?? "Kibaba could not load this page. Try again.",
      body?.error.ref,
    );
  }
  return (await response.json()) as T;
}

/** Like apiGet, but returns null instead of redirecting when nobody is signed in. */
export async function apiGetOptional<T>(path: string): Promise<T | null> {
  const incoming = await headers();
  try {
    const response = await fetch(`${API_URL}${path}`, {
      headers: { cookie: incoming.get("cookie") ?? "", accept: "application/json" },
      cache: "no-store",
    });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}
