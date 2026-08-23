import { getJson, postJson } from "./client";
import type { User } from "../types/api";

export function listUsers(): Promise<User[]> {
  return getJson<User[]>("/api/users");
}

export function createUser(name: string): Promise<User> {
  return postJson<User>("/api/users", { name });
}
