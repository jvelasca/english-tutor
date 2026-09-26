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

interface RequestOptions {
  /** 404 → resuelve `null` en vez de lanzar (V3.18, D7.1). */
  notFoundAsNull?: boolean;
  /**
   * 401 → resuelve `null` en vez de lanzar (V3.75). Lo usa `GET /api/session`:
   * «no hay sesión» no es un error, es el estado normal del primer arranque.
   */
  unauthorizedAsNull?: boolean;
}

/**
 * Error de la API con su código HTTP y el `detail` del backend (V3.76).
 *
 * `detail` es el canal por el que el backend distingue desenlaces que comparten
 * código (`401 SESSION_REQUIRED` vs `401 PIN_REQUIRED` vs `401 PIN_INVALID`).
 * Antes esa distinción se perdía al convertirlo todo en un `Error` de texto: la
 * UI solo podía decir «algo falló». Se conserva el `message` legible, así que
 * quien capturaba `Error` sigue funcionando igual.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  /** Segundos de espera sugeridos por el backend (`Retry-After`), si los manda. */
  readonly retryAfterSeconds: number;

  constructor(
    status: number,
    detail: string,
    options?: { message?: string; retryAfterSeconds?: number },
  ) {
    super(options?.message ?? detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.retryAfterSeconds = options?.retryAfterSeconds ?? 0;
  }
}

/** `Retry-After` en segundos → número. Ignora cabeceras ausentes o basura. */
function _retryAfter(res: Response): number {
  const raw = res.headers?.get?.("retry-after");
  const value = raw ? Number.parseInt(raw, 10) : Number.NaN;
  return Number.isFinite(value) && value > 0 ? value : 0;
}

async function request<T>(
  url: string,
  init?: RequestInit,
  options?: RequestOptions,
): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    if (options?.notFoundAsNull && res.status === 404) {
      return null as T;
    }
    if (options?.unauthorizedAsNull && res.status === 401) {
      return null as T;
    }
    // El rate limiter del backend devuelve un 429 con `code: RATE_LIMITED`
    // cuando el servidor local está saturado: se traduce a la lengua de la UI
    // en vez de pintar el texto interno del backend.
    if (res.status === 429) {
      const err = (await res.json().catch(() => ({}))) as {
        detail?: string;
        code?: string;
      };
      if (err.code === "RATE_LIMITED") {
        throw new ApiError(429, "RATE_LIMITED", {
          message: translate(currentLang(), "errors.rateLimited"),
          retryAfterSeconds: _retryAfter(res),
        });
      }
      throw new ApiError(429, err.detail ?? `HTTP ${res.status}`, {
        retryAfterSeconds: _retryAfter(res),
      });
    }
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(res.status, err.detail ?? `HTTP ${res.status}`, {
      retryAfterSeconds: _retryAfter(res),
    });
  }
  return (await readJson<T>(res)) as T;
}

/**
 * Cuerpo JSON de una respuesta OK, tolerante a los `204 No Content` (V3.86.0).
 *
 * Los endpoints de borrado responden 204 sin cuerpo: `res.json()` lanzaría un
 * `SyntaxError` que la UI leería como «falló el borrado» cuando en realidad se
 * aplicó. Un cuerpo vacío se resuelve como `undefined` y el llamante tipa `void`.
 */
async function readJson<T>(res: Response): Promise<T | undefined> {
  if (res.status === 204) return undefined;
  try {
    return (await res.json()) as T;
  } catch {
    return undefined;
  }
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

/**
 * GET que resuelve `null` cuando el backend responde 404 (recurso sin datos
 * esperado, p. ej. un nodo del Evidence Graph que aún no existe) y lanza con
 * el detalle del backend para el resto de errores (red/5xx…). V3.18 (D7.1):
 * permite a la UI distinguir "sin datos" de "error real".
 */
export function getJsonNullable<T>(
  url: string,
  headers?: Record<string, string>,
): Promise<T | null> {
  return request<T | null>(url, headers ? { headers } : undefined, {
    notFoundAsNull: true,
  });
}

/**
 * GET que resuelve `null` cuando el backend responde 401 (V3.75): sin sesión no
 * es un error, es «todavía no hay perfil». Lo usa `api/session.ts`.
 */
export function getJsonOptional<T>(
  url: string,
  headers?: Record<string, string>,
): Promise<T | null> {
  return request<T | null>(url, headers ? { headers } : undefined, {
    unauthorizedAsNull: true,
  });
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
