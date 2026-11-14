import type { ApiErrorBody } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(0, "network", "The analytics service could not be reached.");
  }
  const body = (await response.json().catch(() => null)) as ApiErrorBody | T | null;
  if (!response.ok) {
    const error = body && typeof body === "object" && "error" in body ? body.error : undefined;
    throw new ApiError(response.status, error?.code ?? "http_error", error?.message ?? "The request failed.", error?.details);
  }
  return body as T;
}

export function mapHasVerifiedGeometry(payload: { geometry_available: boolean; communities: { geometry?: unknown; latitude: number | null; longitude: number | null }[] }) {
  if (!payload.geometry_available) return false;
  return payload.communities.some((community) => community.geometry || (community.latitude != null && community.longitude != null));
}
