import { getJson, patchJson } from "./client";
import type { User } from "../types/api";

export function listUsers(): Promise<User[]> {
  return getJson<User[]>("/api/users");
}

/**
 * V3.81: el alta de una cuenta vive en `api/session.ts` (`createAccount`), junto al
 * resto del ciclo de vida de la cuenta —registro, contraseña, email y baja— porque
 * son un solo flujo. Lo que **no** se hace aquí es un `createUser(name)`: desde la
 * Fase 3 del P0 un alta sin email ni contraseña no existe.
 */

export interface UserPatch {
  name?: string;
  avatar_color?: string;
  avatar_emoji?: string;
  avatar_image?: string;
}

export function updateUser(id: string, patch: UserPatch): Promise<User> {
  return patchJson<User>(`/api/users/${id}`, patch);
}
