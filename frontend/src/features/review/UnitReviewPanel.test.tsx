// @vitest-environment jsdom
/**
 * Vitest de componente de `UnitReviewPanel` (V3.17, M1 — deuda de la auditoría
 * externa v3.16). Corre en jsdom y mockea `fetch` por URL (contrato de red),
 * sin backend real:
 *
 * - estado vacío (plan sin unidades) → mensaje honesto.
 * - plan con una unidad y ventana due_now → el bloque lista la unidad con su
 *   ventana repasable y el contador de unidades por repasar.
 * - apertura del micro-review + submit (elegir opción, finish) → el servidor
 *   responde el resultado y la UI revela la ventana superada.
 * - error de red → estado de error con reintento.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { I18nProvider } from "../../hooks/useI18n";
import { UnitReviewPanel } from "./UnitReviewPanel";
import type { UnitReviewPlan } from "../../types/api";

// --- Fixtures -------------------------------------------------------------

const PLAN_EMPTY: UnitReviewPlan = {
  level_id: "a1",
  level: "A1",
  due_count: 0,
  units: [],
};

const PLAN_WITH_DUE: UnitReviewPlan = {
  level_id: "a1",
  level: "A1",
  due_count: 1,
  units: [
    {
      level_id: "a1",
      unit_id: "a1-m01-u01",
      module_id: "a1-m01",
      module_title: "Module 1",
      title: "Greetings and introductions",
      objectives_total: 2,
      objectives_mastered: 2,
      completed: true,
      anchor: "2026-01-01T00:00:00+00:00",
      windows: [
        { window_days: 7, due_at: "2026-01-08T00:00:00+00:00", state: "due_now" },
        { window_days: 30, due_at: "2026-01-31T00:00:00+00:00", state: "upcoming" },
        { window_days: 90, due_at: "2026-04-01T00:00:00+00:00", state: "upcoming" },
      ],
    },
  ],
};

/** Plan tras aprobar la ventana de 7 días: ya no hay nada repasable. */
const PLAN_PASSED: UnitReviewPlan = {
  level_id: "a1",
  level: "A1",
  due_count: 0,
  units: [
    {
      level_id: "a1",
      unit_id: "a1-m01-u01",
      module_id: "a1-m01",
      module_title: "Module 1",
      title: "Greetings and introductions",
      objectives_total: 2,
      objectives_mastered: 2,
      completed: true,
      anchor: "2026-01-01T00:00:00+00:00",
      windows: [
        { window_days: 7, due_at: "2026-01-08T00:00:00+00:00", state: "passed" },
        { window_days: 30, due_at: "2026-01-31T00:00:00+00:00", state: "upcoming" },
        { window_days: 90, due_at: "2026-04-01T00:00:00+00:00", state: "upcoming" },
      ],
    },
  ],
};

/** Sesión de micro-review con un único check MC de 2 opciones (la 0 correcta). */
const SESSION = {
  level_id: "a1",
  unit_id: "a1-m01-u01",
  unit_title: "Greetings and introductions",
  window_days: 7,
  items: [
    {
      item_id: "c1",
      objective_id: "o1",
      objective_title: "Greet politely",
      skill: "vocabulary",
      prompt: "Choose the polite greeting:",
      options: ["Good morning", "Gimme"],
    },
  ],
};

const RESULT_PASSED = {
  unit_id: "a1-m01-u01",
  window_days: 7,
  correct: 1,
  total: 1,
  accuracy: 1,
  passed: true,
  per_objective: [
    { objective_id: "o1", title: "Greet politely", correct: 1, total: 1, accuracy: 1, grade: 4, next_due_at: "2026-01-15T00:00:00+00:00" },
  ],
  items: [
    {
      item_id: "c1",
      objective_id: "o1",
      objective_title: "Greet politely",
      skill: "vocabulary",
      prompt: "Choose the polite greeting:",
      options: ["Good morning", "Gimme"],
      selected_index: 0,
      correct_index: 0,
      correct: true,
    },
  ],
  plan: {
    level_id: "a1",
    unit_id: "a1-m01-u01",
    module_id: "a1-m01",
    module_title: "Module 1",
    title: "Greetings and introductions",
    objectives_total: 2,
    objectives_mastered: 2,
    completed: true,
    anchor: "2026-01-01T00:00:00+00:00",
    windows: [
      { window_days: 7, due_at: "2026-01-08T00:00:00+00:00", state: "passed" },
      { window_days: 30, due_at: "2026-01-31T00:00:00+00:00", state: "upcoming" },
      { window_days: 90, due_at: "2026-04-01T00:00:00+00:00", state: "upcoming" },
    ],
  },
};

// --- Helpers ---------------------------------------------------------------

/** Mock de fetch que enruta por (método, subcadena de URL). `data` puede ser
 * un valor fijo o una función evaluada en el momento de la llamada. */
function routeFetch(
  routes: Array<{
    method?: "GET" | "POST";
    url: string;
    data: unknown | (() => unknown);
  }>,
) {
  const fn = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();
    const hit = routes.find(
      (r) => (r.method ?? "GET") === method && url.includes(r.url),
    );
    if (!hit) {
      return Promise.reject(new Error(`unexpected fetch: ${method} ${url}`));
    }
    const data = typeof hit.data === "function" ? hit.data() : hit.data;
    return Promise.resolve({ ok: true, json: async () => data });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

function renderPanel(ui: ReactElement) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      {ui}
    </I18nProvider>,
  );
}

describe("UnitReviewPanel (V3.17, M1)", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("estado vacío: sin unidades no hay ventanas y se muestra el mensaje honesto", async () => {
    routeFetch([{ url: "/api/academy/review/unit-plan", data: PLAN_EMPTY }]);
    renderPanel(<UnitReviewPanel userId="u1" />);
    expect(
      await screen.findByText(
        "No finished units yet — finish a unit to start its retention windows.",
      ),
    ).toBeTruthy();
    expect(screen.queryByText("Due now")).toBeNull();
  });

  it("lista la unidad completada con su ventana due y el contador de repaso", async () => {
    routeFetch([{ url: "/api/academy/review/unit-plan", data: PLAN_WITH_DUE }]);
    renderPanel(<UnitReviewPanel userId="u1" />);
    expect(await screen.findByText("Greetings and introductions")).toBeTruthy();
    // Contador de unidades por repasar (due_count → 1).
    expect(screen.getByText(/Units to review/)).toBeTruthy();
    // La ventana 7 está due_now (botón de repaso) y las siguientes, upcoming,
    // se muestran como chips pasivos con su label.
    expect(screen.getByText("Due now")).toBeTruthy();
    expect(screen.getByText("7 days")).toBeTruthy();
    expect(screen.getByText("30 days")).toBeTruthy();
    expect(screen.getByText("90 days")).toBeTruthy();
  });

  it("abre el micro-review, responde y revela la ventana superada (submit y refresh)", async () => {
    // Estado mutable del plan: el POST de la respuesta lo pasa a `passed`, y el
    // refresh posterior (GET unit-plan) ya no debe ofrecer la ventana como due.
    let currentPlan: UnitReviewPlan = PLAN_WITH_DUE;
    routeFetch([
      { url: "/api/academy/review/unit-plan", data: () => currentPlan },
      { url: "/api/academy/review/unit/a1-m01-u01/micro-review", data: SESSION },
      {
        method: "POST",
        url: "/api/academy/review/unit/a1-m01-u01/micro-review",
        data: () => {
          currentPlan = PLAN_PASSED;
          return RESULT_PASSED;
        },
      },
    ]);
    renderPanel(<UnitReviewPanel userId="u1" />);

    // Abrimos la ventana due (botón de la ventana de 7 días).
    fireEvent.click(await screen.findByText("7 days"));

    // La nota honesta (D5) acompaña las preguntas del micro-review.
    expect(
      await screen.findByText(
        "Retention review · it does not count as a demonstration of mastery.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("Choose the polite greeting:")).toBeTruthy();

    // Elegimos la opción correcta y enviamos (el servidor puntúa).
    fireEvent.click(screen.getByText("Good morning"));
    fireEvent.click(screen.getByText("Finish review"));

    // Resultado: ventana superada y revelación de la respuesta correcta.
    expect(await screen.findByText("Window passed")).toBeTruthy();
    expect(screen.getByText(/Correct answer/)).toBeTruthy();

    // Volver refresca el plan: la ventana 7 ya no es repasable (estado passed).
    fireEvent.click(screen.getByText("Back to units"));
    await waitFor(() => {
      expect(screen.queryByText("Due now")).toBeNull();
    });
    expect(screen.getByText("No windows to review right now.")).toBeTruthy();
  });

  it("error de red: estado de error con reintento", async () => {
    routeFetch([]);
    renderPanel(<UnitReviewPanel userId="u1" />);
    expect(
      await screen.findByText("Unit review is not available right now."),
    ).toBeTruthy();
    expect(screen.getByText("Try again")).toBeTruthy();
  });
});
