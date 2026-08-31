import { useCallback, useEffect, useRef, useState } from "react";
import { useI18n } from "../hooks/useI18n";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import {
  deleteAudioLibraryEntry,
  getAudioLibrarySlots,
  uploadAudioLibraryWav,
  type AudioUploadFields,
} from "../api/audioLibrary";
import type { AudioLibrarySlot } from "../types/api";

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

function previewUrl(audioId: string, refreshKey: number): string {
  return `/api/audio-library/${encodeURIComponent(audioId)}/audio?v=${refreshKey}`;
}

function stateBadge(slot: AudioLibrarySlot): {
  label: string;
  variant: "default" | "destructive" | "secondary";
} {
  if (slot.state === "recorded") return { label: "recorded", variant: "default" };
  if (slot.state === "missing") return { label: "missing", variant: "destructive" };
  return { label: "empty", variant: "secondary" };
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

  useEffect(() => {
    void load();
  }, [load]);

  const setForm = (audioId: string, patch: Partial<SlotForm>) => {
    setForms((prev) => ({ ...prev, [audioId]: { ...prev[audioId], ...patch } }));
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
      await uploadAudioLibraryWav(file, fields);
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

  if (slots.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("audio.none")}</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">{t("audio.subtitle")}</p>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      {slots.map((slot) => {
        const badge = stateBadge(slot);
        const form = forms[slot.audio_id];
        const isOpen = expanded[slot.audio_id];
        const isBusy = busy[slot.audio_id];
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
                    <audio
                      controls
                      className="h-9 max-w-full"
                      src={previewUrl(slot.audio_id, refreshKey)}
                    >
                      <track kind="captions" />
                    </audio>
                  </div>
                )}

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

                <p className="text-xs text-muted-foreground">{t("audio.hint.wav")}</p>

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
      })}
    </div>
  );
}
