import { getAdminPin } from "./audioLibrary";

export interface BackupEntry {
  name: string;
  size_bytes: number;
  created_at: string;
}

export interface BackupStatus {
  admin_required: boolean;
  keep_backups: number;
  backup_count: number;
}

export interface CreateBackupResult {
  name: string;
  created_at: string;
  size_bytes: number;
}

function adminHeaders(): Record<string, string> {
  const pin = getAdminPin();
  return pin ? { "X-Admin-Pin": pin } : {};
}

async function systemFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export function getBackupStatus(): Promise<BackupStatus> {
  return systemFetch<BackupStatus>("/api/system/backup/status", {
    headers: adminHeaders(),
  });
}

export function createBackup(): Promise<CreateBackupResult> {
  return systemFetch<CreateBackupResult>("/api/system/backup", {
    method: "POST",
    headers: adminHeaders(),
  });
}

export function listBackups(): Promise<{ backups: BackupEntry[] }> {
  return systemFetch<{ backups: BackupEntry[] }>("/api/system/backups", {
    headers: adminHeaders(),
  });
}

/** Descarga un backup ZIP (el más reciente si no se indica nombre). */
export async function downloadBackup(name?: string): Promise<void> {
  const query = name ? `?name=${encodeURIComponent(name)}` : "";
  const res = await fetch(`/api/system/backup/export${query}`, {
    headers: adminHeaders(),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name ?? "backup.zip";
  a.click();
  URL.revokeObjectURL(url);
}

export function restoreBackup(file: File): Promise<{ restored: boolean }> {
  const form = new FormData();
  form.append("file", file);
  return systemFetch<{ restored: boolean }>("/api/system/restore", {
    method: "POST",
    headers: adminHeaders(),
    body: form,
  });
}
