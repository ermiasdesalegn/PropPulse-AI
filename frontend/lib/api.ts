export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

/** Call the FastAPI backend through the Next.js proxy (which adds the admin key server-side). */
export async function api<T>(path: string, init?: { method?: string; body?: unknown }): Promise<T> {
  const res = await fetch(`/api/backend/${path.replace(/^\//, "")}`, {
    method: init?.method ?? (init?.body ? "POST" : "GET"),
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    body: init?.body ? JSON.stringify(init.body) : undefined,
    cache: "no-store",
  });
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const detail = (data as { detail?: unknown } | null)?.detail;
    const message =
      typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : `Request failed (${res.status})`;
    throw new ApiError(message, res.status);
  }
  return data as T;
}
