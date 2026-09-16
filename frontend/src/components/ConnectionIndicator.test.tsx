// @vitest-environment jsdom
/**
 * Vitest del indicador de conexión de la cabecera (V3.38.1; V3.71 eje RC).
 *
 * V3.71: el indicador dejó de preguntar a `/api/health` (que responde 200
 * siempre que el proceso esté vivo) y pregunta por las DEPENDENCIAS, así que
 * distingue TRES estados: Conectado, Degradado y Desconectado. El caso
 * «Degradado» es el que antes mentía: la API respondía y la app no servía.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { I18nProvider } from "../hooks/useI18n";
import { ConnectionIndicator } from "./ConnectionIndicator";

const ALL_OK = {
  api: "ok",
  database: "ok",
  ollama: "ok",
  stt: "ok",
  tts: "ok",
  audio_library: "ok",
};

type Stub = "ok" | "degraded" | "offline" | "audio-only";

function stubFetch(kind: Stub) {
  const fn = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/health/dependencies")) {
      if (kind === "offline") return Promise.reject(new Error("offline"));
      return Promise.resolve({
        ok: true,
        json: async () => ({
          ...ALL_OK,
          // Ollama caído: la API responde, pero la app no puede conversar.
          ollama: kind === "degraded" ? "error" : "ok",
          // La biblioteca de audio es opcional por diseño: no debe teñir el estado.
          audio_library: kind === "audio-only" ? "unavailable" : "ok",
        }),
      });
    }
    if (url.includes("/api/health")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ status: "ok", service: "api", version: "3.71.0" }),
      });
    }
    return Promise.reject(new Error(`unexpected fetch: ${url}`));
  });
  vi.stubGlobal("fetch", fn);
}

function renderIndicator() {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      <ConnectionIndicator />
    </I18nProvider>,
  );
}

describe("ConnectionIndicator (V3.38.1)", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("muestra Conectado cuando todas las dependencias clave están listas", async () => {
    stubFetch("ok");
    renderIndicator();
    expect(await screen.findByText("Connected")).toBeTruthy();
  });

  it("muestra Degradado cuando la API responde pero una dependencia falla", async () => {
    stubFetch("degraded");
    renderIndicator();
    expect(await screen.findByText("Degraded")).toBeTruthy();
    expect(screen.queryByText("Connected")).toBeNull();
  });

  it("muestra Desconectado cuando las dependencias no se pueden leer", async () => {
    stubFetch("offline");
    renderIndicator();
    expect(await screen.findByText("Disconnected")).toBeTruthy();
  });

  it("no declara degradación por la biblioteca de audio (es opcional por diseño)", async () => {
    stubFetch("audio-only");
    renderIndicator();
    expect(await screen.findByText("Connected")).toBeTruthy();
  });

  it("abre el popover con el estado del sistema", async () => {
    stubFetch("ok");
    renderIndicator();
    await screen.findByText("Connected");
    fireEvent.click(screen.getByRole("button", { name: "System status" }));
    expect(
      screen.getByRole("dialog", { name: "System status" }),
    ).toBeTruthy();
  });
});
