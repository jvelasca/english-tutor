// @vitest-environment jsdom
/**
 * Vitest de `KaraokeTranscript` (V3.29, Fase 3): karaoke palabra a palabra.
 * Cubre el revelado por política (`hidden`/`partial`/`full`), el resaltado de la
 * palabra activa según `currentTime`, el escalado slow/fast, la degradación sin
 * frases (`sentenceTimings` vacío → línea continua solo en `full`) y el salto
 * por toque (`onSeekToWord`).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { I18nProvider } from "../../hooks/useI18n";
import type { ListeningWordTiming } from "../../types/api";
import { KaraokeTranscript } from "./KaraokeTranscript";
import type { SentenceTiming } from "./microFlow";

const SENTENCE_TIMINGS: SentenceTiming[] = [
  { index: 0, start: 0, end: 1, text: "Hello world.", sync: "coarse_heuristic" },
  { index: 1, start: 1, end: 2, text: "Nice day.", sync: "coarse_heuristic" },
];

const WORDS: ListeningWordTiming[] = [
  { index: 0, text: "Hello", start: 0, end: 0.4, sentence: 0 },
  { index: 1, text: "world", start: 0.5, end: 0.9, sentence: 0 },
  { index: 2, text: "Nice", start: 1.1, end: 1.5, sentence: 1 },
  { index: 3, text: "day", start: 1.6, end: 2, sentence: 1 },
];

function renderKaraoke(
  state: "hidden" | "partial" | "full",
  currentTime: number,
  onSeekToWord: (start: number) => void = () => {},
  overrides: {
    wordTimings?: ListeningWordTiming[];
    sentenceTimings?: SentenceTiming[];
    factor?: number;
  } = {},
) {
  return render(
    <I18nProvider lang="es" setLang={() => {}}>
      <KaraokeTranscript
        wordTimings={overrides.wordTimings ?? WORDS}
        sentenceTimings={overrides.sentenceTimings ?? SENTENCE_TIMINGS}
        state={state}
        currentTime={currentTime}
        activeVariantFactor={overrides.factor ?? 1}
        onSeekToWord={onSeekToWord}
      />
    </I18nProvider>,
  );
}

describe("KaraokeTranscript (palabra a palabra)", () => {
  afterEach(cleanup);

  it("no renderiza nada sin wordTimings", () => {
    const { container } = renderKaraoke("full", 1, () => {}, { wordTimings: [] });
    expect(container.firstChild).toBeNull();
  });

  it("no renderiza nada con transcripción oculta", () => {
    const { container } = renderKaraoke("hidden", 1.2);
    expect(container.firstChild).toBeNull();
  });

  it("full: muestra todas las palabras y resalta la activa según currentTime", () => {
    renderKaraoke("full", 0.6); // segunda palabra ("world", 0.5–0.9)
    expect(screen.getByText("Hello")).toBeTruthy();
    expect(screen.getByText("world")).toBeTruthy();
    expect(screen.getByText("Nice")).toBeTruthy();
    expect(screen.getByText("day")).toBeTruthy();
    const active = screen.getByText("world");
    expect(active.className).toContain("bg-primary/15");
    const inactive = screen.getByText("Hello");
    expect(inactive.className).not.toContain("bg-primary/15");
    expect(screen.getByText("Transcripción (sync palabra)")).toBeTruthy();
  });

  it("partial: solo muestra las palabras de la frase activa", () => {
    renderKaraoke("partial", 0.2); // frase 0
    expect(screen.getByText("Hello")).toBeTruthy();
    expect(screen.getByText("world")).toBeTruthy();
    expect(screen.queryByText("Nice")).toBeNull();
    expect(screen.queryByText("day")).toBeNull();
    expect(screen.getByText("Transcripción (parcial)")).toBeTruthy();
  });

  it("partial cambia de frase según avanza la reproducción", () => {
    renderKaraoke("partial", 1.8); // frase 1
    expect(screen.queryByText("Hello")).toBeNull();
    expect(screen.getByText("Nice")).toBeTruthy();
    expect(screen.getByText("day")).toBeTruthy();
  });

  it("tocar una palabra llama a onSeekToWord con su instante", () => {
    const onSeekToWord = vi.fn();
    renderKaraoke("full", 0, onSeekToWord);
    fireEvent.click(screen.getByText("Nice"));
    expect(onSeekToWord).toHaveBeenCalledWith(1.1);
  });

  it("escala slow/fast: el resaltado usa el tiempo escalado", () => {
    // Factor 2 (slow): "world" (0.5 s) se oye en t=1.0 del audio reproducido.
    renderKaraoke("full", 1.0, () => {}, { factor: 2 });
    const active = screen.getByText("world");
    expect(active.className).toContain("bg-primary/15");
    // El salto por toque recibe el instante escalado (1.1 * 2).
    const onSeekToWord = vi.fn();
    cleanup();
    renderKaraoke("full", 0, onSeekToWord, { factor: 2 });
    fireEvent.click(screen.getByText("Nice"));
    expect(onSeekToWord).toHaveBeenCalledWith(2.2);
  });

  it("sin frases (duration ausente) degrada a línea continua solo en full", () => {
    renderKaraoke("full", 0, () => {}, { sentenceTimings: [] });
    expect(screen.getByText("Hello")).toBeTruthy();
    expect(screen.getByText("day")).toBeTruthy();
    cleanup();
    const { container: partial } = renderKaraoke("partial", 1.2, () => {}, {
      sentenceTimings: [],
    });
    expect(partial.firstChild).toBeNull();
  });
});
