// @vitest-environment jsdom
/**
 * Vitest del aviso global de voz degradada (V3.72, RD-04): cuando el backend
 * sirve el audio con una voz de otro idioma, la UI lo dice (con la voz usada) y
 * el aviso se puede descartar sin bloquear la pantalla.
 */
import { afterEach, describe, expect, it } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { I18nProvider } from "../hooks/useI18n";
import {
  clearDegradedVoice,
  reportDegradedVoice,
} from "../hooks/useDegradedVoice";
import { DegradedVoiceNotice } from "./DegradedVoiceNotice";

function renderNotice() {
  return render(
    <I18nProvider lang="es" setLang={() => {}}>
      <DegradedVoiceNotice />
    </I18nProvider>,
  );
}

describe("DegradedVoiceNotice (V3.72, RD-04)", () => {
  afterEach(() => {
    cleanup();
    clearDegradedVoice();
  });

  it("no muestra nada mientras no haya degradación", () => {
    renderNotice();
    expect(screen.queryByTestId("degraded-voice-notice")).toBeNull();
  });

  it("explica el idioma que falta y la voz realmente usada", () => {
    renderNotice();

    act(() => {
      reportDegradedVoice("en_US-hfc_female-medium", "es");
    });

    const notice = screen.getByTestId("degraded-voice-notice");
    expect(notice.getAttribute("role")).toBe("status");
    expect(notice.textContent).toContain("Español");
    expect(notice.textContent).toContain("en_US-hfc_female-medium");
  });

  it("se descarta al cerrarlo", () => {
    reportDegradedVoice("en_US-hfc_female-medium", "es");
    renderNotice();

    fireEvent.click(screen.getByRole("button", { name: "Cerrar" }));

    expect(screen.queryByTestId("degraded-voice-notice")).toBeNull();
  });
});
