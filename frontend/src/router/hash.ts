import { useSyncExternalStore } from "react";

/**
 * Ruta canónica de la aplicación: string normalizado que SIEMPRE empieza por
 * "/" (la raíz es "/"). Los segmentos se conservan codificados con
 * `encodeURIComponent` (p. ej. "/formacion/b1%20intermediate"), de modo que la
 * comparación entre rutas es un simple `===` entre strings.
 */
export type Path = string;

/**
 * Normaliza cualquier valor que pueda devolver `window.location.hash` o que
 * reciba un deep-link: "#/inicio", "#/", "", "/inicio", "/aprender/listening",
 * etc. Devuelve la ruta canónica correspondiente. Colapsa barras duplicadas
 * ("/a//b" -> "/a/b"), recorta la barra final ("/inicio/" -> "/inicio"),
 * garantiza que el resultado empiece por "/" y representa la raíz como "/".
 * No decodifica los segmentos: el contenido percent-encoded se conserva tal
 * cual.
 */
export function normalizeHash(raw: string): Path {
  let value = raw.startsWith("#") ? raw.slice(1) : raw;
  value = value.replace(/\/{2,}/g, "/");
  if (value === "" || value === "/") return "/";
  value = value.replace(/\/+$/, "");
  if (!value.startsWith("/")) value = "/" + value;
  return value;
}

/**
 * Convierte una ruta canónica en el valor que debe asignarse a
 * `window.location.hash` (p. ej. "/inicio" -> "#/inicio", "/" -> "#/").
 * Normaliza la entrada primero, de modo que es simétrica con `normalizeHash`.
 */
export function pathToHash(path: Path): string {
  return `#${normalizeHash(path)}`;
}

/**
 * Divide una ruta canónica en sus segmentos decodificados. Cada segmento se
 * decodifica con `decodeURIComponent`; si una secuencia de escape es inválida,
 * se conserva el segmento literal para no romper la navegación. La raíz "/"
 * devuelve un array vacío.
 */
export function parseSegments(path: Path): string[] {
  const normalized = normalizeHash(path);
  if (normalized === "/") return [];
  return normalized
    .slice(1)
    .split("/")
    .map((segment) => {
      try {
        return decodeURIComponent(segment);
      } catch {
        return segment;
      }
    });
}

/**
 * Construye una ruta canónica a partir de segmentos en crudo: cada segmento se
 * codifica con `encodeURIComponent` y se une con "/". Los segmentos vacíos se
 * ignoran. Un array vacío devuelve la raíz "/" (p. ej. [] -> "/" y
 * ["formacion", "b1"] -> "/formacion/b1").
 */
export function formatPath(segments: readonly string[]): Path {
  const encoded = segments
    .filter((segment) => segment.length > 0)
    .map((segment) => encodeURIComponent(segment));
  return encoded.length === 0 ? "/" : `/${encoded.join("/")}`;
}

/**
 * Determina si una ruta actual debe considerarse "activa" para un destino de
 * navegación. Con `exact: false` (por defecto): la raíz "/" solo está activa
 * cuando `current` es la raíz; para cualquier otro destino está activo si
 * `current` es igual al destino o desciende de él (frontera de segmento, por
 * ejemplo "/formacion/b1" activa "/formacion" pero "/formacion-b1" no). Con
 * `exact: true` exige igualdad exacta.
 */
export function isActive(
  current: Path,
  target: Path,
  opts?: { exact?: boolean },
): boolean {
  const c = normalizeHash(current);
  const t = normalizeHash(target);
  const exact = opts?.exact ?? false;
  if (exact) return c === t;
  if (t === "/") return c === "/";
  return c === t || c.startsWith(`${t}/`);
}

/**
 * Une una ruta base con segmentos en crudo y normaliza el resultado. Los
 * segmentos se percent-codifican, por lo que pueden incluir espacios o
 * caracteres no ASCII (p. ej. joinPath("/formacion", "b1") -> "/formacion/b1"
 * y joinPath("/", "inicio") -> "/inicio").
 */
export function joinPath(base: Path, ...segments: string[]): Path {
  return formatPath([...parseSegments(base), ...segments]);
}

/**
 * Lee la ruta actual desde `window.location.hash` y la devuelve normalizada.
 * Sin `window` (SSR / tests en node) devuelve la raíz "/".
 */
export function readHashPath(): Path {
  if (typeof window === "undefined") return "/";
  return normalizeHash(window.location.hash);
}

/**
 * Navega a una ruta asignando `window.location.hash`. Si ya estamos en esa
 * ruta no hace nada (evita duplicar entradas de historial). Sin `window`
 * (SSR / tests en node) es un no-op.
 */
export function navigateTo(path: Path): void {
  if (typeof window === "undefined") return;
  const nextHash = pathToHash(path);
  if (window.location.hash === nextHash) return;
  window.location.hash = nextHash;
}

/**
 * Se suscribe a los cambios del hash del navegador (evento "hashchange", que
 * cubre el botón atrás/adelante y los enlaces manuales). Devuelve la función
 * para cancelar la suscripción. Sin `window` (SSR / tests en node) devuelve un
 * no-op.
 */
export function subscribeHash(callback: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("hashchange", callback);
  return () => window.removeEventListener("hashchange", callback);
}

/**
 * Hook React que devuelve la ruta canónica actual y re-renderiza el componente
 * en cada cambio del hash (incluido el botón atrás/adelante del navegador).
 * Usa `useSyncExternalStore`; el snapshot de servidor es "/".
 */
export function useHashPath(): Path {
  return useSyncExternalStore(subscribeHash, readHashPath, () => "/");
}
