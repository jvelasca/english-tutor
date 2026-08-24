import { getJson, patchJson, postJson } from "./client";
import type { User } from "../types/api";

export function listUsers(): Promise<User[]> {
  return getJson<User[]>("/api/users");
}

export function createUser(name: string): Promise<User> {
  return postJson<User>("/api/users", { name });
}

export interface UserPatch {
  name?: string;
  avatar_color?: string;
  avatar_emoji?: string;
  avatar_image?: string;
}

export function updateUser(id: string, patch: UserPatch): Promise<User> {
  return patchJson<User>(`/api/users/${id}`, patch);
}
