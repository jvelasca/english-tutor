import { translate, type Lang } from "../utils/i18n";

/** Idioma de la UI persistido (localStorage, igual que `useI18n`). */
function currentLang(): Lang {
  try {
    const v = window.localStorage.getItem("english-tutor.lang");
    return v === "es" ? "es" : "en";
  } catch {
    return "en";
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    // El rate limiter del backend devuelve un 429 con `code: RATE_LIMITED`
    // cuando el servidor local está saturado: se traduce a la lengua de la UI
    // en vez de pintar el texto interno del backend.
    if (res.status === 429) {
      const err = (await res.json().catch(() => ({}))) as {
        detail?: string;
        code?: string;
      };
      if (err.code === "RATE_LIMITED") {
        throw new Error(translate(currentLang(), "errors.rateLimited"));
      }
      throw new Error(err.detail ?? `HTTP ${res.status}`);
    }
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

/**
 * Limita una petición a `ms` milisegundos. Si se excede, rechaza con un error
 * legible en vez de dejar la promesa colgada para siempre (una petición que no
 * termina dejaba pantallas sin salida, p. ej. el botón "Continuar" de listening
 * cuando el backend tarda o la conexión se cae a medias).
 */
export function withTimeout<T>(
  promise: Promise<T>,
  ms: number,
  label: string,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error(`Timeout (${label}): no response after ${ms / 1000}s`)),
      ms,
    );
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (err) => {
        clearTimeout(timer);
        reject(err);
      },
    );
  });
}

export function getJson<T>(
  url: string,
  headers?: Record<string, string>,
): Promise<T> {
  return request<T>(url, headers ? { headers } : undefined);
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

export function postForm<T>(
  url: string,
  form: FormData,
  headers?: Record<string, string>,
): Promise<T> {
  return request<T>(url, {
    method: "POST",
    body: form,
    ...(headers ? { headers } : {}),
  });
}

export function putJson<T>(url: string, body: unknown): Promise<T> {
  return sendJson<T>(url, "PUT", body);
}

export function patchJson<T>(url: string, body: unknown): Promise<T> {
  return sendJson<T>(url, "PATCH", body);
}

export function deleteJson<T>(
  url: string,
  headers?: Record<string, string>,
): Promise<T> {
  return request<T>(url, {
    method: "DELETE",
    ...(headers ? { headers } : {}),
  });
}
