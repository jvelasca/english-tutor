import { useEffect, useRef, useState } from "react";
import {
  createBackup,
  downloadBackup,
  listBackups,
  restoreBackup,
  type BackupEntry,
} from "../api/system";
import { useI18n } from "../hooks/useI18n";

function formatBytes(bytes: number): string {
  if (!bytes || bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

export function BackupPanel() {
  const { t } = useI18n();
  const [backups, setBackups] = useState<BackupEntry[]>([]);
  const [message, setMessage] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function refresh() {
    try {
      const res = await listBackups();
      setBackups(res.backups);
    } catch {
      setError(t("backup.adminRequired"));
    }
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreate() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await createBackup();
      setMessage(t("backup.created"));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("backup.error"));
    } finally {
      setBusy(false);
    }
  }

  async function handleDownload(name?: string) {
    setError("");
    setMessage("");
    try {
      await downloadBackup(name);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("backup.error"));
    }
  }

  async function handleRestore(file: File) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await restoreBackup(file);
      setMessage(t("backup.restored"));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("backup.error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="system-status">
      <div className="system-status__section">
        <p className="system-status__section-title">{t("backup.title")}</p>
        <p className="status-bar-muted">{t("backup.subtitle")}</p>

        <div className="backup-actions">
          <button
            type="button"
            className="dialog-primary"
            onClick={handleCreate}
            disabled={busy}
          >
            {t("backup.create")}
          </button>
          <button
            type="button"
            className="dialog-secondary"
            onClick={() => handleDownload()}
            disabled={busy || backups.length === 0}
          >
            {t("backup.download")}
          </button>
        </div>
        <p className="status-bar-muted">{t("backup.keep")}</p>

        {message && (
          <p className="backup-message" role="status">
            {message}
          </p>
        )}
        {error && (
          <p className="backup-error" role="alert">
            {error}
          </p>
        )}
      </div>

      <div className="system-status__section">
        <p className="system-status__section-title">{t("backup.list")}</p>
        {backups.length === 0 ? (
          <p className="status-bar-muted">{t("backup.empty")}</p>
        ) : (
          <ul className="system-status__list">
            {backups.map((b) => (
              <li className="system-status__item" key={b.name}>
                <span>{formatDate(b.created_at)}</span>
                <span className="status-bar-muted">{formatBytes(b.size_bytes)}</span>
                <button
                  type="button"
                  className="dialog-secondary"
                  onClick={() => handleDownload(b.name)}
                >
                  {t("backup.download")}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="system-status__section">
        <p className="system-status__section-title">{t("backup.restoreTitle")}</p>
        <input
          ref={fileRef}
          type="file"
          accept=".zip,application/zip"
          className="sr-only"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void handleRestore(file);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          className="dialog-secondary"
          disabled={busy}
          onClick={() => fileRef.current?.click()}
        >
          {t("backup.chooseFile")}
        </button>
      </div>
    </div>
  );
}
