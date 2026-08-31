import { useCallback, useEffect, useRef, useState } from "react";
import { useI18n } from "../hooks/useI18n";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import {
  deleteAudioLibraryEntry,
  fetchAudioLibraryBlob,
  getAdminPin,
  getAudioLibraryAudit,
  getAudioLibrarySlots,
  getAudioLibraryStatus,
  setAdminPin,
  uploadAudioLibraryWav,
  type AudioUploadFields,
} from "../api/audioLibrary";
import type {
  AudioLibrarySlot,
  AudioLibraryStatusResponse,
  AudioQualityPanel,
  ContentValidationReport,
} from "../types/api";

const CEFR_OPTIONS = ["unknown", "A1", "A2", "B1", "B2"];
const GENDER_OPTIONS = ["unknown", "female", "male"];
const CONTEXT_OPTIONS = [
  "unknown",
  "conversation",
  "announcement",
  "message",
  "instructions",
  "news",
  "interview",
  "narrative",
  "presentation",
];

interface SlotForm {
  transcript: string;
  speaker_id: string;
  accent: string;
  cefr: string;
  speech_rate: string;
  noise_level: string;
  gender: string;
  region: string;
  context: string;
}

function initialForm(slot: AudioLibrarySlot): SlotForm {
  const e = slot.entry;
  const cefr =
    e?.cefr && e.cefr !== "unknown"
      ? e.cefr
      : slot.level === "B1" || slot.level === "B2"
        ? slot.level
        : "unknown";
  return {
    transcript: e?.transcript ?? slot.transcript,
    speaker_id: e?.speaker_id ?? slot.speaker_id,
    accent: e?.accent ?? slot.accent,
    cefr,
    speech_rate:
      e?.speech_rate != null
        ? String(e.speech_rate)
        : slot.speech_rate
          ? String(slot.speech_rate)
          : "",
    noise_level: String(e?.noise_level ?? slot.noise_level),
    gender: e?.gender ?? "unknown",
    region: e?.region && e.region !== "unknown" ? e.region : "",
    context: e?.context ?? "unknown",
  };
}

function stateBadge(slot: AudioLibrarySlot): {
  label: string;
  variant: "default" | "destructive" | "secondary";
} {
  if (slot.state === "recorded") return { label: "recorded", variant: "default" };
  if (slot.state === "missing") return { label: "missing", variant: "destructive" };
  return { label: "empty", variant: "secondary" };
}

function gradeVariant(grade: string): "default" | "destructive" | "outline" {
  if (grade === "REJECT") return "destructive";
  if (grade === "WARNING") return "outline";
  return "default";
}

function severityVariant(severity: string): "default" | "destructive" | "secondary" {
  if (severity === "error") return "destructive";
  if (severity === "warning") return "secondary";
  return "default";
}

function fmtDb(value: number | null): string {
  return value == null ? "—" : `${value.toFixed(1)} dBFS`;
}

function fmtPct(value: number | null): string {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function fmtSec(value: number | null): string {
  return value == null ? "—" : `${value.toFixed(1)} s`;
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

function RecordingPreview({
  audioId,
  refreshKey,
}: {
  audioId: string;
  refreshKey: number;
}) {
  const { t } = useI18n();
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let url: string | null = null;
    let cancelled = false;
    setSrc(null);
    setFailed(false);
    fetchAudioLibraryBlob(audioId)
      .then((u) => {
        url = u;
        if (!cancelled) setSrc(u);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [audioId, refreshKey]);

  if (failed) {
    return <span className="text-xs text-destructive">{t("audio.preview")}</span>;
  }
  if (!src) {
    return <span className="text-xs text-muted-foreground">{t("common.loading")}</span>;
  }
  return (
    <audio controls className="h-9 max-w-full" src={src}>
      <track kind="captions" />
    </audio>
  );
}

function QualityPanel({ panel }: { panel: AudioQualityPanel }) {
  const { t } = useI18n();
  return (
    <Card className="gap-2">
      <CardHeader className="px-4 pt-4">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-xs font-semibold uppercase tracking-wide">
            {t("audio.qa.title")}
          </CardTitle>
          <Badge variant={gradeVariant(panel.grade)}>{panel.grade}</Badge>
        </div>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-x-4 gap-y-1 px-4 pb-4 text-xs sm:grid-cols-3">
        <div>
          <span className="text-muted-foreground">{t("audio.qa.duration")}:</span>{" "}
          {fmtSec(panel.duration)}
        </div>
        <div>
          <span className="text-muted-foreground">{t("audio.qa.sampleRate")}:</span>{" "}
          {panel.framerate ? `${panel.framerate} Hz` : "—"}
        </div>
        <div>
          <span className="text-muted-foreground">{t("audio.qa.channels")}:</span>{" "}
          {panel.channels}
        </div>
        <div>
          <span className="text-muted-foreground">{t("audio.qa.peak")}:</span>{" "}
          {fmtDb(panel.peak_dbFS)}
        </div>
        <div>
          <span className="text-muted-foreground">{t("audio.qa.clipping")}:</span>{" "}
          {fmtPct(panel.clipping_ratio)}
        </div>
        <div>
          <span className="text-muted-foreground">{t("audio.qa.silence")}:</span>{" "}
          {fmtPct(panel.silence_ratio)}
        </div>
        <div>
          <span className="text-muted-foreground">{t("audio.qa.dc")}:</span>{" "}
          {panel.dc_offset == null ? "—" : panel.dc_offset.toFixed(4)}
        </div>
      </CardContent>
    </Card>
  );
}

const inputClass =
  "h-9 w-full rounded-md border border-border bg-background px-2.5 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50";

export function AudioLibrary() {
  const { t } = useI18n();
  const [slots, setSlots] = useState<AudioLibrarySlot[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [forms, setForms] = useState<Record<string, SlotForm>>({});
  const [files, setFiles] = useState<Record<string, File | null>>({});
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [refreshKey, setRefreshKey] = useState(0);
  const [quality, setQuality] = useState<Record<string, AudioQualityPanel>>({});
  const [status, setStatus] = useState<AudioLibraryStatusResponse | null>(null);
  const [pinInput, setPinInput] = useState("");
  const [unlocked, setUnlocked] = useState(false);
  const [unlockError, setUnlockError] = useState(false);
  const [tab, setTab] = useState<"library" | "audit">("library");
  const [audit, setAudit] = useState<ContentValidationReport | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState(false);
  const fileInputs = useRef<Record<string, HTMLInputElement | null>>({});

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getAudioLibrarySlots();
      setSlots(res.slots);
      setForms(
        Object.fromEntries(res.slots.map((s) => [s.audio_id, initialForm(s)])),
      );
    } catch {
      setError(t("audio.error.load"));
    }
  }, [t]);

  const loadStatus = useCallback(async () => {
    try {
      const s = await getAudioLibraryStatus();
      setStatus(s);
      if (!s.admin_required) {
        setUnlocked(true);
      } else if (getAdminPin()) {
        try {
          const report = await getAudioLibraryAudit();
          setAudit(report);
          setUnlocked(true);
        } catch {
          setAdminPin("");
        }
      }
    } catch {
      // La biblioteca sigue siendo consultable sin el estado admin.
    }
  }, []);

  const loadAudit = useCallback(async () => {
    setAuditLoading(true);
    setAuditError(false);
    try {
      setAudit(await getAudioLibraryAudit());
    } catch {
      setAuditError(true);
    } finally {
      setAuditLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    void loadStatus();
  }, [load, loadStatus]);

  const adminRequired = status?.admin_required ?? false;
  const isUnlocked = !adminRequired || unlocked;

  useEffect(() => {
    if (tab === "audit" && isUnlocked) void loadAudit();
  }, [tab, isUnlocked, loadAudit]);

  const setForm = (audioId: string, patch: Partial<SlotForm>) => {
    setForms((prev) => ({ ...prev, [audioId]: { ...prev[audioId], ...patch } }));
  };

  const unlock = async () => {
    setUnlockError(false);
    setError(null);
    setAdminPin(pinInput);
    try {
      const report = await getAudioLibraryAudit();
      setAudit(report);
      setUnlocked(true);
    } catch {
      setAdminPin("");
      setUnlockError(true);
    }
  };

  const lock = () => {
    setAdminPin("");
    setUnlocked(false);
    setAudit(null);
    setPinInput("");
  };

  const handleUpload = async (audioId: string) => {
    const file = files[audioId];
    if (!file) return;
    setBusy((b) => ({ ...b, [audioId]: true }));
    setError(null);
    const form = forms[audioId];
    try {
      const fields: AudioUploadFields = {
        audio_id: audioId,
        transcript: form.transcript,
        speaker_id: form.speaker_id,
        accent: form.accent,
        cefr: form.cefr,
        speech_rate: form.speech_rate.trim() === "" ? null : Number(form.speech_rate),
        noise_level: form.noise_level.trim() === "" ? 0 : Number(form.noise_level),
        gender: form.gender,
        region: form.region,
        context: form.context,
      };
      const res = await uploadAudioLibraryWav(file, fields);
      setQuality((q) => ({ ...q, [audioId]: res.quality }));
      setFiles((f) => ({ ...f, [audioId]: null }));
      setRefreshKey((k) => k + 1);
      await load();
    } catch {
      setError(t("audio.error.upload"));
    } finally {
      setBusy((b) => ({ ...b, [audioId]: false }));
    }
  };

  const handleRemove = async (audioId: string) => {
    setBusy((b) => ({ ...b, [audioId]: true }));
    setError(null);
    try {
      await deleteAudioLibraryEntry(audioId);
      setQuality((q) => {
        const next = { ...q };
        delete next[audioId];
        return next;
      });
      setRefreshKey((k) => k + 1);
      await load();
    } catch {
      setError(t("audio.error.remove"));
    } finally {
      setBusy((b) => ({ ...b, [audioId]: false }));
    }
  };

  if (slots === null) {
    return <p className="text-sm text-muted-foreground">{t("common.loading")}</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">{t("audio.subtitle")}</p>

      {adminRequired && !isUnlocked && (
        <Card className="gap-3">
          <CardContent className="flex flex-wrap items-center gap-2 px-4 py-3">
            <p className="text-sm text-muted-foreground">
              {t("audio.admin.required")}
            </p>
            <input
              type="password"
              className="h-9 w-40 rounded-md border border-border bg-background px-2.5 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
              value={pinInput}
              placeholder={t("audio.admin.pin")}
              onChange={(e) => setPinInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void unlock();
              }}
            />
            <Button type="button" size="sm" onClick={() => void unlock()}>
              {t("audio.admin.unlock")}
            </Button>
            {unlockError && (
              <p role="alert" className="text-sm text-destructive">
                {t("audio.admin.error")}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {adminRequired && isUnlocked && (
        <div className="flex items-center gap-2">
          <Badge variant="outline">{t("audio.admin.unlocked")}</Badge>
          <Button type="button" variant="ghost" size="sm" onClick={lock}>
            {t("audio.admin.lock")}
          </Button>
        </div>
      )}

      <div className="flex gap-2">
        <Button
          type="button"
          variant={tab === "library" ? "default" : "outline"}
          size="sm"
          onClick={() => setTab("library")}
        >
          {t("audio.tab.library")}
        </Button>
        <Button
          type="button"
          variant={tab === "audit" ? "default" : "outline"}
          size="sm"
          onClick={() => setTab("audit")}
        >
          {t("audio.tab.audit")}
        </Button>
      </div>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      {tab === "audit" ? (
        <AuditDashboard
          report={audit}
          loading={auditLoading}
          errored={auditError}
        />
      ) : slots.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("audio.none")}</p>
      ) : (
        slots.map((slot) => {
          const badge = stateBadge(slot);
          const form = forms[slot.audio_id];
          const isOpen = expanded[slot.audio_id];
          const isBusy = busy[slot.audio_id];
          const panel = quality[slot.audio_id];
          return (
            <Card key={slot.audio_id} className="gap-3">
              <CardHeader className="px-4 pt-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 flex-col gap-1">
                    <CardTitle className="text-sm">
                      <span className="font-mono">{slot.audio_id}</span>
                      <span className="ml-2 font-normal text-muted-foreground">
                        {slot.level} · {slot.skill} · {slot.topic}
                      </span>
                    </CardTitle>
                    <p className="truncate text-xs text-muted-foreground">
                      {slot.transcript}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge variant={badge.variant}>
                      {t(`audio.state.${badge.label}`)}
                    </Badge>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        setExpanded((e) => ({ ...e, [slot.audio_id]: !isOpen }))
                      }
                      aria-expanded={isOpen}
                    >
                      {isOpen ? t("common.close") : t("common.edit")}
                    </Button>
                  </div>
                </div>
              </CardHeader>

              {isOpen && form && (
                <CardContent className="flex flex-col gap-4 px-4 pb-4">
                  {slot.state !== "empty" && (
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-medium text-muted-foreground">
                        {t("audio.preview")}
                      </span>
                      <RecordingPreview
                        audioId={slot.audio_id}
                        refreshKey={refreshKey}
                      />
                    </div>
                  )}

                  {panel && <QualityPanel panel={panel} />}

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <Field label={t("audio.field.transcript")}>
                      <input
                        className={inputClass}
                        value={form.transcript}
                        onChange={(e) =>
                          setForm(slot.audio_id, { transcript: e.target.value })
                        }
                      />
                    </Field>
                    <Field label={t("audio.field.speaker")}>
                      <input
                        className={inputClass}
                        value={form.speaker_id}
                        onChange={(e) =>
                          setForm(slot.audio_id, { speaker_id: e.target.value })
                        }
                      />
                    </Field>
                    <Field label={t("audio.field.accent")}>
                      <input
                        className={inputClass}
                        value={form.accent}
                        onChange={(e) =>
                          setForm(slot.audio_id, { accent: e.target.value })
                        }
                      />
                    </Field>
                    <Field label={t("audio.field.cefr")}>
                      <select
                        className={inputClass}
                        value={form.cefr}
                        onChange={(e) =>
                          setForm(slot.audio_id, { cefr: e.target.value })
                        }
                      >
                        {CEFR_OPTIONS.map((o) => (
                          <option key={o} value={o}>
                            {o}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label={t("audio.field.speechRate")}>
                      <input
                        className={inputClass}
                        inputMode="decimal"
                        value={form.speech_rate}
                        onChange={(e) =>
                          setForm(slot.audio_id, { speech_rate: e.target.value })
                        }
                      />
                    </Field>
                    <Field label={t("audio.field.noise")}>
                      <input
                        className={inputClass}
                        inputMode="numeric"
                        min={0}
                        max={5}
                        value={form.noise_level}
                        onChange={(e) =>
                          setForm(slot.audio_id, { noise_level: e.target.value })
                        }
                      />
                    </Field>
                    <Field label={t("audio.field.gender")}>
                      <select
                        className={inputClass}
                        value={form.gender}
                        onChange={(e) =>
                          setForm(slot.audio_id, { gender: e.target.value })
                        }
                      >
                        {GENDER_OPTIONS.map((o) => (
                          <option key={o} value={o}>
                            {o}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label={t("audio.field.region")}>
                      <input
                        className={inputClass}
                        value={form.region}
                        onChange={(e) =>
                          setForm(slot.audio_id, { region: e.target.value })
                        }
                      />
                    </Field>
                    <Field label={t("audio.field.context")}>
                      <select
                        className={inputClass}
                        value={form.context}
                        onChange={(e) =>
                          setForm(slot.audio_id, { context: e.target.value })
                        }
                      >
                        {CONTEXT_OPTIONS.map((o) => (
                          <option key={o} value={o}>
                            {o}
                          </option>
                        ))}
                      </select>
                    </Field>
                  </div>

                  <p className="text-xs text-muted-foreground">
                    {t("audio.hint.wav")}
                  </p>

                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      ref={(el) => {
                        fileInputs.current[slot.audio_id] = el;
                      }}
                      type="file"
                      accept=".wav,audio/wav,audio/x-wav,audio/wave"
                      className="hidden"
                      onChange={(e) =>
                        setFiles((f) => ({
                          ...f,
                          [slot.audio_id]: e.target.files?.[0] ?? null,
                        }))
                      }
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => fileInputs.current[slot.audio_id]?.click()}
                    >
                      {t("audio.chooseFile")}
                    </Button>
                    {files[slot.audio_id] && (
                      <span className="max-w-[14rem] truncate text-xs text-muted-foreground">
                        {files[slot.audio_id]?.name}
                      </span>
                    )}
                    <Button
                      type="button"
                      size="sm"
                      disabled={!files[slot.audio_id] || isBusy}
                      onClick={() => void handleUpload(slot.audio_id)}
                    >
                      {isBusy ? t("common.saving") : t("audio.upload")}
                    </Button>
                    {slot.state !== "empty" && (
                      <Button
                        type="button"
                        variant="destructive"
                        size="sm"
                        disabled={isBusy}
                        onClick={() => void handleRemove(slot.audio_id)}
                      >
                        {t("audio.remove")}
                      </Button>
                    )}
                  </div>
                </CardContent>
              )}
            </Card>
          );
        })
      )}
    </div>
  );
}

function AuditDashboard({
  report,
  loading,
  errored,
}: {
  report: ContentValidationReport | null;
  loading: boolean;
  errored: boolean;
}) {
  const { t } = useI18n();

  if (loading && !report) {
    return <p className="text-sm text-muted-foreground">{t("common.loading")}</p>;
  }
  if (errored && !report) {
    return <p className="text-sm text-destructive">{t("audio.audit.error")}</p>;
  }
  if (!report) return null;

  const severityCounts = Object.entries(report.by_severity);
  const validatedItems =
    report.total_validated_learning_items ??
    report.stats?.total_validated_learning_items;
  const listeningCorpus = report.stats?.listening.total;
  const speakingScenarios = report.stats?.speaking_scenarios;

  return (
    <div className="flex flex-col gap-3">
      <Card className="gap-3">
        <CardHeader className="px-4 pt-4">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-sm">{t("audio.audit.title")}</CardTitle>
            <Badge variant={report.ok ? "default" : "destructive"}>
              {report.ok ? "OK" : t("audio.audit.fail")}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="grid grid-cols-3 gap-3 px-4 pb-4 text-center">
          <div>
            <div className="text-lg font-semibold">{report.total_items}</div>
            <div className="text-xs text-muted-foreground">
              {t("audio.audit.items")}
            </div>
          </div>
          <div>
            <div className="text-lg font-semibold">{report.recorded}</div>
            <div className="text-xs text-muted-foreground">
              {t("audio.audit.recorded")}
            </div>
          </div>
          <div>
            <div className="text-lg font-semibold">{report.tts}</div>
            <div className="text-xs text-muted-foreground">
              {t("audio.audit.tts")}
            </div>
          </div>
        </CardContent>
      </Card>

      {validatedItems != null && (
        <Card className="gap-3">
          <CardHeader className="px-4 pt-4">
            <CardTitle className="text-sm">
              {t("audio.audit.validatedItems")}
            </CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-3 gap-3 px-4 pb-4 text-center">
            <div>
              <div className="text-lg font-semibold tabular-nums">
                {validatedItems}
              </div>
              <div className="text-xs text-muted-foreground">
                {t("audio.audit.validatedItems")}
              </div>
            </div>
            {listeningCorpus != null && (
              <div>
                <div className="text-lg font-semibold tabular-nums">
                  {listeningCorpus}
                </div>
                <div className="text-xs text-muted-foreground">
                  {t("audio.audit.listeningCorpus")}
                </div>
              </div>
            )}
            {speakingScenarios != null && (
              <div>
                <div className="text-lg font-semibold tabular-nums">
                  {speakingScenarios}
                </div>
                <div className="text-xs text-muted-foreground">
                  {t("audio.audit.speakingScenarios")}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card className="gap-3">
        <CardHeader className="px-4 pt-4">
          <CardTitle className="text-sm">{t("audio.audit.bySeverity")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 px-4 pb-4">
          {severityCounts.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("audio.audit.empty")}</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {severityCounts.map(([severity, count]) => (
                <li
                  key={severity}
                  className="flex items-center justify-between text-sm"
                >
                  <Badge variant={severityVariant(severity)}>{severity}</Badge>
                  <span>{count}</span>
                </li>
              ))}
            </ul>
          )}

          {report.issues.length > 0 && (
            <ul className="mt-2 flex max-h-64 flex-col gap-1 overflow-y-auto text-xs">
              {report.issues.map((issue, i) => (
                <li
                  key={`${issue.id}-${i}`}
                  className="flex items-start gap-2 rounded-md border border-border px-2 py-1"
                >
                  <Badge variant={severityVariant(issue.severity)}>
                    {issue.severity}
                  </Badge>
                  <span className="font-mono text-muted-foreground">
                    {issue.id || "—"}
                  </span>
                  <span className="min-w-0 flex-1">{issue.message}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
