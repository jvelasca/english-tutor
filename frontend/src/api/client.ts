async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export function getJson<T>(url: string): Promise<T> {
  return request<T>(url);
}

function sendJson<T>(url: string, method: string, body: unknown): Promise<T> {
  return request<T>(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function postJson<T>(url: string, body: unknown): Promise<T> {
  return sendJson<T>(url, "POST", body);
}

export function postForm<T>(url: string, form: FormData): Promise<T> {
  return request<T>(url, { method: "POST", body: form });
}

export function putJson<T>(url: string, body: unknown): Promise<T> {
  return sendJson<T>(url, "PUT", body);
}

export function patchJson<T>(url: string, body: unknown): Promise<T> {
  return sendJson<T>(url, "PATCH", body);
}

export function deleteJson<T>(url: string): Promise<T> {
  return request<T>(url, { method: "DELETE" });
}
