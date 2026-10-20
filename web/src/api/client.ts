// Mock mode is the default. Set VITE_USE_MOCKS=0 to talk to the real server.
export const USE_MOCKS = (import.meta.env.VITE_USE_MOCKS ?? '1') !== '0';
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
export const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000/ws';

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : 'Request failed');
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const isForm = body instanceof FormData;
  let response: Response;
  try {
    response = await fetch(API_BASE + path, {
      method,
      headers: body !== undefined && !isForm ? { 'Content-Type': 'application/json' } : undefined,
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    });
  } catch {
    // The server is down, the address is wrong or the browser blocked the call.
    throw new ApiError(0, 'network');
  }
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const data = (await response.json()) as { detail?: unknown };
      if (typeof data.detail === 'string' || Array.isArray(data.detail)) detail = data.detail;
    } catch {
      // The server sent no JSON; the status text is the best sentence we have.
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}