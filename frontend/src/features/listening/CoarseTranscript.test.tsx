// @vitest-environment jsdom
/**
 * Vitest de `CoarseTranscript` (V3.28, Bloque D): transcripción dinámica con
 * sync grueso. Cubre el revelado por política (`hidden`/`partial`/`full`) y el
 * resaltado de la frase activa según tiempos simulados de `currentTime`.
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { I18nProvider } from "../../hooks/useI18n";
import { CoarseTranscript } from "./CoarseTranscript";
import type { SentenceTiming } from "./microFlow";

const TIMINGS: SentenceTiming[] = [
  { index: 0, start: 0, end: 2, text: "First sentence.", sync: "coarse_heuristic" },
  { index: 1, start: 2, end: 4, text: "Second sentence.", sync: "coarse_heuristic" },
  { index: 2, start: 4, end: 6, text: "Third sentence.", sync: "coarse_heuristic" },
];

function renderTranscript(
  state: "hidden" | "partial" | "full",
  currentTime: number,
  timings: SentenceTiming[] = TIMINGS,
) {
  return render(
    <I18nProvider lang="es" setLang={() => {}}>
      <CoarseTranscript timings={timings} state={state} currentTime={currentTime} />
    </I18nProvider>,
  );
}

describe("CoarseTranscript (sync grueso)", () => {
  afterEach(cleanup);

  it("no renderiza nada con transcripción oculta", () => {
    const { container } = renderTranscript("hidden", 1.5);
    expect(container.firstChild).toBeNull();
  });

  it("no renderiza nada sin timings", () => {
    const { container } = renderTranscript("full", 1.5, []);
    expect(container.firstChild).toBeNull();
  });

  it("full: muestra todas las frases y resalta la activa según currentTime", () => {
    renderTranscript("full", 3.2); // frase 1 (index 1, 2s–4s)
    expect(screen.getByText("First sentence.")).toBeTruthy();
    expect(screen.getByText("Second sentence.")).toBeTruthy();
    expect(screen.getByText("Third sentence.")).toBeTruthy();
    const active = screen.getByText("Second sentence.");
    expect(active.className).toContain("bg-primary/15");
    const inactive = screen.getByText("First sentence.");
    expect(inactive.className).not.toContain("bg-primary/15");
    expect(screen.getByText("Transcripción")).toBeTruthy();
    // Marca explícita de sync heurístico (nunca alineación acústica).
    expect(screen.getByText("Sync aproximado")).toBeTruthy();
  });

  it("partial: solo muestra la frase permitida en esa etapa", () => {
    renderTranscript("partial", 1.2); // frase 0
    expect(screen.getByText("First sentence.")).toBeTruthy();
    expect(screen.queryByText("Second sentence.")).toBeNull();
    expect(screen.queryByText("Third sentence.")).toBeNull();
    expect(screen.getByText("Transcripción (parcial)")).toBeTruthy();
  });

  it("partial cambia de frase según avanza la reproducción", () => {
    const first = renderTranscript("partial", 3.8); // frase 1
    expect(first.getByText("Second sentence.")).toBeTruthy();
    cleanup();
    const second = renderTranscript("partial", 5.0); // frase 2
    expect(second.queryByText("First sentence.")).toBeNull();
    expect(second.getByText("Third sentence.")).toBeTruthy();
  });
});
