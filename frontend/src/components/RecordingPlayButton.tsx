import { useEffect, useRef, useState } from "react";
import { Play, Square } from "lucide-react";
import { Button } from "./ui/button";
import { cn } from "../lib/utils";

interface RecordingPlayButtonProps {
  /** URL del audio a reproducir (object URL local de la grabación del alumno). */
  src: string | null;
  /** Etiqueta visible y accesible del botón. */
  label: string;
  className?: string;
}

/**
 * Reproduce la grabación real del alumno (blob del micrófono, no TTS).
 *
 * Cada instancia posee su propio `HTMLAudioElement`: la fuente se asigna al
 * pulsar, se detiene al cambiar de grabación o al desmontar (revocando la
 * escucha). No depende del backend — el audio grabado nunca se sube a disco,
 * solo se transcribe — así que la reproducción es local e inmediata.
 */
export function RecordingPlayButton({
  src,
  label,
  className,
}: RecordingPlayButtonProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);

  // Al cambiar la grabación (nuevo src) detener el audio anterior.
  useEffect(() => {
    const audio = audioRef.current;
    if (audio && !audio.paused) audio.pause();
    setPlaying(false);
  }, [src]);

  // Al desmontar, detener y soltar el elemento.
  useEffect(() => {
    return () => {
      audioRef.current?.pause();
    };
  }, []);

  async function toggle() {
    if (!src) return;
    const audio =
      audioRef.current ?? (audioRef.current = new Audio());
    if (playing) {
      audio.pause();
      setPlaying(false);
      return;
    }
    audio.src = src;
    audio.onended = () => setPlaying(false);
    audio.onerror = () => setPlaying(false);
    try {
      await audio.play();
      setPlaying(true);
    } catch {
      setPlaying(false);
    }
  }

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className={cn("min-h-8 gap-1.5 px-2.5 text-xs", className)}
      onClick={toggle}
      disabled={!src}
      aria-pressed={playing}
      title={label}
    >
      {playing ? (
        <Square className="size-3.5" aria-hidden="true" />
      ) : (
        <Play className="size-3.5" aria-hidden="true" />
      )}
      <span>{label}</span>
    </Button>
  );
}
