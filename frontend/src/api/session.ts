import type { User } from "../types/api";
import { deleteJson, getJsonOptional, postJson } from "./client";

/**
 * Sesión del perfil activo (V3.75, Fase 2 del P0 de identidad).
 *
 * Hasta V3.74 la identidad viajaba en **cada** URL (`?user_id=…`), así que
 * cualquiera que alcanzara la API podía pedir los datos de otro perfil. Ahora la
 * identidad la firma el servidor y viaja en una cookie `et_session` **HttpOnly**:
 * esta capa ya no manda el perfil en cada petición, solo lo **abre** una vez.
 *
 * `getSession()` recupera esa identidad al arrancar: el cliente no puede leer la
 * cookie (es HttpOnly, y ese es justo el punto), así que se la **pregunta** al
 * servidor. Es la razón de que la UI no pueda fiarse de nada guardado en el
 * navegador para saber quién es.
 */

/** Abre sesión para un perfil existente (404 si no existe). */
export function openSession(userId: string): Promise<User> {
  return postJson<User>("/api/session", { user_id: userId });
}

/** El perfil de la sesión actual; `null` si no hay sesión (401). */
export function getSession(): Promise<User | null> {
  return getJsonOptional<User>("/api/session");
}

/**
 * Cierra sesión (caduca la cookie en el navegador).
 *
 * La app **no** la llama hoy: cambiar de perfil es `openSession` con otro id (el
 * selector del `Header`), y cerrar sin abrir no aporta nada al alumno —el producto
 * no tiene cuentas ni pantalla de salida—. Se conserva porque es la mitad que
 * falta del ciclo (`POST`/`GET`/`DELETE`) y porque el test de integración de la
 * API la fija: si el endpoint cambia, esto se entera.
 */
export function closeSession(): Promise<{ closed: boolean }> {
  return deleteJson<{ closed: boolean }>("/api/session");
}
