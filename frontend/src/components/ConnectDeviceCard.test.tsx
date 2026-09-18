// @vitest-environment jsdom
/**
 * Vitest de la tarjeta "Conectar un dispositivo" (V3.73.x): con el **modo LAN**
 * apagado la app solo escucha en loopback, así que la tarjeta no puede ofrecer
 * un QR ni un enlace a una URL que no responde. Ese es el fallo que este test
 * impide: un código escaneable que lleva a «no se puede conectar».
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { I18nProvider } from "../hooks/useI18n";

const getNetworkMock = vi.fn();

vi.mock("../api/network", () => ({
  getNetwork: () => getNetworkMock(),
}));

import { ConnectDeviceCard } from "./ConnectDeviceCard";

function renderCard() {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      <ConnectDeviceCard />
    </I18nProvider>,
  );
}

const RED = {
  ip: "192.168.1.42",
  hostname: "english-tutor-pc",
  frontend_port: "8000",
  backend_port: "8000",
  lan_mode: true,
  bind: "0.0.0.0",
  url: "https://192.168.1.42:8000",
  local_url: "https://english-tutor-pc.local:8000",
  local_url_available: true,
};

describe("ConnectDeviceCard (V3.73.x)", () => {
  afterEach(() => {
    cleanup();
    getNetworkMock.mockReset();
  });

  it("sin modo LAN no ofrece QR ni enlace, y explica el paso que falta", async () => {
    getNetworkMock.mockResolvedValue({
      ...RED,
      lan_mode: false,
      bind: "127.0.0.1",
      url: "",
      local_url_available: false,
    });

    renderCard();

    await waitFor(() =>
      expect(screen.getByText(/only answers on this device/i)).toBeTruthy(),
    );
    expect(screen.queryAllByRole("link")).toHaveLength(0);
    expect(screen.queryByText("https://192.168.1.42:8000")).toBeNull();
    expect(screen.getByText(/ENGLISH_TUTOR_LAN=1/)).toBeTruthy();
  });

  it("con modo LAN declarado muestra la URL de acceso y su enlace", async () => {
    getNetworkMock.mockResolvedValue(RED);

    renderCard();

    await waitFor(() =>
      expect(screen.getByText("https://192.168.1.42:8000")).toBeTruthy(),
    );
    const enlaces = screen.queryAllByRole("link");
    expect(enlaces.length).toBeGreaterThan(0);
    expect(enlaces[0].getAttribute("href")).toBe("https://192.168.1.42:8000");
  });
});
