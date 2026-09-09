// @vitest-environment jsdom
/**
 * Vitest de `AuditoryProfileCard` (V3.27, Listening Engine 4.0): la tarjeta del
 * perfil auditivo visible en la UI. Cubre los tres estados del perfil: sin
 * perfil (no renderiza), con muestra insuficiente (needsMore) y con intervención
 * activa (capa de trabajo + recomendación por casos A-D).
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { I18nProvider } from "../../hooks/useI18n";
import { translate } from "../../utils/i18n";
import { AuditoryProfileCard } from "./AuditoryProfileCard";
import type { ListeningAuditoryProfile } from "../../types/api";

const t = (key: string) => translate("es", key);

function renderCard(profile: ListeningAuditoryProfile | null | undefined) {
  return render(
    <I18nProvider lang="es" setLang={() => {}}>
      <AuditoryProfileCard profile={profile} t={t} />
    </I18nProvider>,
  );
}

const NEEDS_MORE: ListeningAuditoryProfile = {
  layer: null,
  intervention: null,
  reason: "",
  needs_min_attempts: true,
};

const CASE_A: ListeningAuditoryProfile = {
  layer: "recognition",
  intervention: "bottom_up_path",
  reason: "recognition",
  needs_min_attempts: false,
};

const CASE_B: ListeningAuditoryProfile = {
  layer: "comprehension",
  intervention: "comprehension_path",
  reason: "comprehension",
  needs_min_attempts: false,
};

const CASE_D: ListeningAuditoryProfile = {
  layer: null,
  intervention: "connected_speech_path",
  reason: "connected_speech",
  needs_min_attempts: false,
};

describe("AuditoryProfileCard", () => {
  afterEach(cleanup);

  it("no renderiza sin perfil", () => {
    renderCard(null);
    expect(screen.queryByText("Tu perfil auditivo")).toBeNull();
  });

  it("no renderiza un perfil vacío sin señal", () => {
    renderCard({ layer: null, intervention: null, reason: "", needs_min_attempts: false });
    expect(screen.queryByText("Tu perfil auditivo")).toBeNull();
  });

  it("muestra needsMore cuando no hay muestra suficiente", () => {
    renderCard(NEEDS_MORE);
    expect(screen.getByText("Tu perfil auditivo")).toBeTruthy();
    expect(screen.getByText(/preguntas más/)).toBeTruthy();
  });

  it("caso A: muestra capa de trabajo e intervención bottom-up", () => {
    renderCard(CASE_A);
    expect(screen.getByText("Reconocimiento")).toBeTruthy();
    expect(screen.getByText(/reconocimiento de palabras/)).toBeTruthy();
  });

  it("caso B: muestra comprensión y su intervención", () => {
    renderCard(CASE_B);
    expect(screen.getByText("Comprensión")).toBeTruthy();
    expect(screen.getByText(/significado y la estructura/)).toBeTruthy();
  });

  it("caso D: muestra intervención de cadena hablada sin capa", () => {
    renderCard(CASE_D);
    expect(screen.queryByText("Reconocimiento")).toBeNull();
    expect(screen.getByText(/cadena hablada/)).toBeTruthy();
  });
});
