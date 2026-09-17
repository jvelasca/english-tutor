// @vitest-environment jsdom
/**
 * Vitest de `NextStep` (V3.72, deuda UX «por qué esta actividad»): es el pie
 * «Next» del bucle Activity → Result → Feedback → Next, así que es la
 * superficie que ve el alumno al terminar **cualquier** drill o repaso.
 *
 * V3.72 le añade el `why` que el Adaptive Engine ya declaraba en
 * `GET /api/academy/next-best` (el mismo contrato que pinta `NextBestCard`) y
 * que este pie descartaba. El cliente no calcula nada: solo renderiza.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { I18nProvider } from "../hooks/useI18n";
import { NextStep } from "./NextStep";
import type { NextBestActivity } from "../types/api";

const mocks = vi.hoisted(() => ({
  getNextBestActivity: vi.fn(),
}));

vi.mock("../api/academy", () => ({
  getNextBestActivity: mocks.getNextBestActivity,
}));

function activity(payload: Partial<NextBestActivity> = {}): NextBestActivity {
  return {
    kind: "weakness",
    step_key: "grammar-present-simple",
    skill: "grammar",
    subskill: null,
    objective_id: "g1",
    level_id: "a1",
    title: "Present simple",
    reason: "weakest",
    minutes: 10,
    priority: 0.8,
    ...payload,
  };
}

function renderNextStep() {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      <NextStep userId="u1" onNext={() => {}} />
    </I18nProvider>,
  );
}

describe("NextStep · «por qué esta actividad» (V3.72)", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("declara el `why` del motor junto a la actividad sugerida", async () => {
    mocks.getNextBestActivity.mockResolvedValue(
      activity({
        why: "Grammar is your weakest skill right now, so it comes first today.",
      }),
    );
    renderNextStep();

    const line = await screen.findByText(/weakest skill right now/);
    expect(line.textContent).toContain("Why?");
    expect(line.textContent).toContain(
      "Grammar is your weakest skill right now, so it comes first today.",
    );
  });

  it("sin `why` declarado el pie no inventa un porqué", async () => {
    mocks.getNextBestActivity.mockResolvedValue(activity());
    renderNextStep();

    expect(await screen.findByText(/Present simple/)).toBeTruthy();
    expect(screen.queryByText("Why?")).toBeNull();
  });
});
