// @vitest-environment jsdom
/**
 * Vitest del hub de APRENDER (cierre GUI pre-V4.0, V3.73.1).
 *
 * Fija dos hallazgos de la auditoría de cierre:
 * - **GUI-01:** el `aria-labelledby` de la sección del grid debe apuntar a un
 *   nodo real (antes referenciaba un `id` inexistente, así que la sección no
 *   tenía nombre accesible).
 * - **GUI-02:** las 4 actividades caben en una fila en desktop
 *   (`xl:grid-cols-4`), sin dejar la cuarta tarjeta aislada.
 *
 * Se renderiza con `userId=null` a propósito: en ese caso el hub no llama a la
 * API del Adaptive Engine y el bloque «Recomendado para ti» queda en error.
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { I18nProvider } from "../../hooks/useI18n";
import { translate } from "../../utils/i18n";
import { LearnHub } from "./LearnHub";

/** Etiqueta accesible de una tarjeta de actividad en el idioma del proveedor. */
function activityAriaLabel(skillKey: string): string {
  return `${translate("es", "learn.activityAria")}: ${translate("es", skillKey)}`;
}

function renderHub() {
  return render(
    <I18nProvider lang="es" setLang={() => {}}>
      <LearnHub userId={null} onStart={() => {}} />
    </I18nProvider>,
  );
}

describe("LearnHub · cierre GUI (V3.73.1)", () => {
  afterEach(cleanup);

  it("la sección del grid tiene un nombre accesible resoluble (GUI-01)", () => {
    renderHub();

    // `getByRole("region", { name })` solo encuentra la sección si el
    // `aria-labelledby` apunta a un elemento existente: es exactamente la
    // regresión que fijamos.
    const section = screen.getByRole("region", {
      name: "¿Qué quieres practicar hoy?",
    });
    const labelledBy = section.getAttribute("aria-labelledby");
    expect(labelledBy).toBeTruthy();
    expect(document.getElementById(labelledBy as string)).toBeTruthy();
  });

  it("el grid de actividades usa 4 columnas en desktop (GUI-02)", () => {
    renderHub();

    const grid = screen.getByTestId("learn-hub-grid");
    const classes = grid.className;
    expect(classes).toContain("sm:grid-cols-2");
    expect(classes).toContain("xl:grid-cols-4");
    expect(classes).not.toContain("lg:grid-cols-3");
  });

  it("mantiene las 4 actividades del hub", () => {
    renderHub();

    // Etiquetas resueltas en el idioma del proveedor (es), no literales en
    // inglés: el hub ya se renderiza traducido y el test debe seguir al Render.
    for (const key of [
      "skill.listening",
      "skill.speaking",
      "skill.vocabulary",
      "skill.grammar",
    ]) {
      expect(
        screen.getByRole("button", { name: activityAriaLabel(key) }),
      ).toBeTruthy();
    }
  });

  it("expone Reading y Writing como práctica con el tutor (GUI-04)", () => {
    renderHub();

    const tutor = screen.getByTestId("learn-hub-tutor");
    expect(tutor.className).toContain("sm:grid-cols-2");
    // Las dos destrezas existen como superficie propia dentro de APRENDER...
    for (const key of ["skill.reading", "skill.writing"]) {
      expect(
        screen.getByRole("button", { name: activityAriaLabel(key) }),
      ).toBeTruthy();
    }
    // ...y no compiten con las 4 tarjetas del hub.
    expect(screen.getByTestId("learn-hub-grid").contains(tutor)).toBe(false);
  });
});
