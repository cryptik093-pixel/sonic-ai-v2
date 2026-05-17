import type { ApiErrorEnvelope } from "@/types";

export const API_ENDPOINTS = {
  health: "/health",
  analyze: "/api/v2/analyze",
  promptMidi: "/api/v2/prompt-midi",
} as const;

export type ApiEndpoint = (typeof API_ENDPOINTS)[keyof typeof API_ENDPOINTS];

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export async function postJSON<T>(
  path: ApiEndpoint,
  body: unknown,
  options: RequestInit = {},
): Promise<T> {
  const { headers, ...restOptions } = options;
  const response = await fetch(buildApiUrl(path), {
    ...restOptions,
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(headers || {}),
    },
    body: JSON.stringify(body),
  });

  return readJSONResponse<T>(response);
}

export async function getJSON<T>(path: ApiEndpoint, options: RequestInit = {}): Promise<T> {
  const response = await fetch(buildApiUrl(path), {
    ...options,
    method: "GET",
  });

  return readJSONResponse<T>(response);
}

export async function uploadFile<T>(
  path: ApiEndpoint,
  file: File,
  extraFields: Record<string, string | number> = {},
): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);
  Object.entries(extraFields).forEach(([key, value]) => {
    formData.append(key, String(value));
  });

  const response = await fetch(buildApiUrl(path), {
    method: "POST",
    body: formData,
  });

  return readJSONResponse<T>(response);
}

export async function postBinary(
  path: ApiEndpoint,
  body: unknown,
  options: RequestInit = {},
): Promise<{ blob: Blob; headers: Headers; status: number }> {
  const { headers, ...restOptions } = options;
  const response = await fetch(buildApiUrl(path), {
    ...restOptions,
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "audio/midi",
      ...(headers || {}),
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    await throwApiError(response);
  }

  return {
    blob: await response.blob(),
    headers: response.headers,
    status: response.status,
  };
}

export function getConfiguredApiBaseUrl(): string {
  return API_BASE_URL || "same-origin";
}

function buildApiUrl(path: ApiEndpoint): string {
  return `${API_BASE_URL}${path}`;
}

async function readJSONResponse<T>(response: Response): Promise<T> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError(response.status, "The backend response was not valid JSON.");
  }

  if (!response.ok || isErrorEnvelope(payload)) {
    throw new ApiError(
      response.status,
      isErrorEnvelope(payload) ? payload.error.message : `API error ${response.status}.`,
      isErrorEnvelope(payload) ? payload.error.code : undefined,
    );
  }

  return payload as T;
}

async function throwApiError(response: Response): Promise<never> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError(response.status, `API error ${response.status}.`);
  }

  if (isErrorEnvelope(payload)) {
    throw new ApiError(response.status, payload.error.message, payload.error.code);
  }

  throw new ApiError(response.status, `API error ${response.status}.`);
}

function isErrorEnvelope(payload: unknown): payload is ApiErrorEnvelope {
  if (!payload || typeof payload !== "object") {
    return false;
  }
  const candidate = payload as {
    status?: unknown;
    error?: { code?: unknown; message?: unknown };
  };
  return (
    candidate.status === "error" &&
    typeof candidate.error?.code === "string" &&
    typeof candidate.error?.message === "string"
  );
}
