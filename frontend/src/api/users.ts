import { patchJson } from "./client";
import type { User } from "../types/api";

/**
 * V3.81/V3.82: este módulo ya **no** enumera cuentas.
 *
 * `listUsers()` desapareció en V3.82, y con él el `GET /api/users` público: era
 * la forma de descubrir quién tiene cuenta sin sesión, y el selector de nombres
 * lo usaba para entrar «eligiendo» a alguien. Ahora la identidad se demuestra
 * (email + contraseña) y la app solo conoce la cuenta **de su sesión**.
 *
 * El alta de una cuenta tampoco vive aquí: es una **solicitud** que el webmaster
 * autoriza (`api/profileRequests.ts`), y la contraseña la pone la persona desde
 * el correo (`api/session.ts`).
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
