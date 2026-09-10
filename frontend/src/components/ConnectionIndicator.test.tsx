// @vitest-environment jsdom
/**
 * Vitest del indicador de conexión de la cabecera (V3.38.1): sustituye a la
 * barra de estado inferior. Comprueba los dos estados (conectado/desconectado)
 * y que el popover con el estado completo del sistema se abre al pulsarlo.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { I18nProvider } from "../hooks/useI18n";
import { ConnectionIndicator } from "./ConnectionIndicator";

function stubFetch(online: boolean) {
  const fn = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/health/dependencies")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          api: "ok",
          database: "ok",
          ollama: "ok",
          stt: "ok",
          tts: "ok",
          audio_library: "ok",
        }),
      });
    }
    if (url.includes("/api/health")) {
      return online
        ? Promise.resolve({
            ok: true,
            json: async () => ({ status: "ok", service: "api", version: "3.38.1" }),
          })
        : Promise.reject(new Error("offline"));
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

  it("muestra Conectado cuando /api/health responde", async () => {
    stubFetch(true);
    renderIndicator();
    expect(await screen.findByText("Connected")).toBeTruthy();
  });

  it("muestra Desconectado cuando /api/health falla", async () => {
    stubFetch(false);
    renderIndicator();
    expect(await screen.findByText("Disconnected")).toBeTruthy();
  });

  it("abre el popover con el estado del sistema", async () => {
    stubFetch(true);
    renderIndicator();
    await screen.findByText("Connected");
    fireEvent.click(screen.getByRole("button", { name: "System status" }));
    expect(
      screen.getByRole("dialog", { name: "System status" }),
    ).toBeTruthy();
  });
});
