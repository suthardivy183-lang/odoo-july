const BASE = "/api/v1";
const TOKEN_KEY = "eco-token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function detailToMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors
    return detail
      .map((d) => (typeof d?.msg === "string" ? d.msg.replace(/^Value error, /, "") : ""))
      .filter(Boolean)
      .join("; ") || "Invalid input";
  }
  return "Something went wrong";
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}${path}`, { method, headers, body: payload });
  if (res.status === 401) {
    setToken(null);
    window.dispatchEvent(new Event("eco-unauthorized"));
  }
  if (!res.ok) {
    let message = res.statusText;
    try {
      const data = await res.json();
      message = detailToMessage(data.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message);
  }
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};

export async function uploadFile(file: File, context: string): Promise<{ id: number }> {
  const form = new FormData();
  form.append("file", file);
  form.append("context", context);
  return request("POST", "/files", form);
}
