// @vitest-environment jsdom
/**
 * Vitest de componente de la fila de sesión enriquecida de `TodayPlan`
 * (V3.17, D6 + M1). Mockea `fetch` por URL para `getStudentModel`/`getSession`/
 * `getGoal` y verifica que:
 *
 * - un paso con `can_do` + `limiting_factor` del Evidence Graph dibuja las dos
 *   micro-líneas informativas dentro de la fila-botón: el can-do en itálica y
 *   el chip del factor limitante con su porcentaje (D6).
 * - un paso SIN objetivo o sin nodo (D7) no dibuja el bloque de grafo (silente).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { I18nProvider } from "../hooks/useI18n";
import { TodayPlan } from "./TodayPlan";
import type {
  LearningGoal,
  Session as SessionData,
  StudentModel,
} from "../types/api";

// --- Fixtures -------------------------------------------------------------

const GOAL: LearningGoal = {
  goal_type: "general",
  minutes_per_day: 30,
  days_per_week: 5,
  target_level: "B1",
};

const MODEL: StudentModel = {
  level_id: "a1",
  current_level: "A1",
  estimated_level: "A1",
  estimated_numeric: 1,
  confidence: 0.5,
  target_level: "B1",
  skills: [],
  critical_skills: [],
  readiness: {
    target_level: "B1",
    skills: [],
    overall: 55,
    blocking_skills: [],
    ready: false,
    band: "emerging",
  },
  reassessment: null,
  mastery: [],
};

const SESSION_GRAPH: SessionData = {
  total_minutes: 30,
  review_count: 0,
  practice_count: 1,
  items: [
    {
      kind: "new",
      step_key: "new-a1-m01-u01-l01-o01",
      skill: "vocabulary",
      subskill: null,
      objective_id: "a1-m01-u01-l01-o01",
      level_id: "a1",
      skills: ["vocabulary"],
      title: "Greetings",
      reason: "next in path",
      minutes: 30,
      can_do: "I can greet people politely.",
      limiting_factor: { id: "grammar", score: 0.42, missing: false },
      graph_mastery: 0.42,
      because: ["Grammar is the limiting factor of this can-do."],
    },
  ],
};

/** Paso sin objetivo (listening, curva de olvido): sin campos de grafo (D7). */
const SESSION_NO_GRAPH: SessionData = {
  total_minutes: 30,
  review_count: 0,
  practice_count: 1,
  items: [
    {
      kind: "new",
      step_key: "new-a1-m01-u01-l01-o01",
      skill: "vocabulary",
      subskill: null,
      objective_id: "a1-m01-u01-l01-o01",
      level_id: "a1",
      skills: ["vocabulary"],
      title: "Greetings",
      reason: "next in path",
      minutes: 30,
    },
  ],
};

/** Paso con factor limitante de dimensión no-skill (`transfer`): el chip debe
 *  pintar la etiqueta humana, no el id en crudo (V3.18, D5/H5). */
const SESSION_TRANSFER: SessionData = {
  total_minutes: 30,
  review_count: 0,
  practice_count: 1,
  items: [
    {
      kind: "new",
      step_key: "new-a1-m01-u01-l01-o01",
      skill: "vocabulary",
      subskill: null,
      objective_id: "a1-m01-u01-l01-o01",
      level_id: "a1",
      skills: ["vocabulary"],
      title: "Greetings",
      reason: "next in path",
      minutes: 30,
      can_do: "I can greet people politely.",
      limiting_factor: { id: "transfer", score: 0.3, missing: false },
      graph_mastery: 0.3,
      because: ["Transfer is the limiting factor of this can-do."],
    },
  ],
};

// --- Helpers ---------------------------------------------------------------

function routeFetch(data: {
  student_model: StudentModel;
  session: SessionData;
  goal: LearningGoal;
}) {
  const fn = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    const payload = url.includes("/student-model")
      ? data.student_model
      : url.includes("/session")
        ? data.session
        : url.includes("/goal")
          ? data.goal
          : null;
    if (payload === null) {
      return Promise.reject(new Error(`unexpected fetch: ${url}`));
    }
    return Promise.resolve({ ok: true, json: async () => payload });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

function renderPlan(ui: ReactElement) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      {ui}
    </I18nProvider>,
  );
}

describe("TodayPlan sesión enriquecida (V3.17, D6/M1)", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("D6: un paso con can_do y limiting_factor dibuja el can-do y el chip con pct", async () => {
    routeFetch({ student_model: MODEL, session: SESSION_GRAPH, goal: GOAL });
    renderPlan(<TodayPlan userId="u1" />);

    // El can-do del grafo aparece como micro-línea informativa de la fila.
    expect(await screen.findByText("I can greet people politely.")).toBeTruthy();
    // Chip del factor limitante: etiqueta de destreza (inmersión en inglés) + pct.
    const note = screen.getByRole("note");
    expect(note.textContent).toContain("Grammar");
    expect(note.textContent).toContain("42%");
  });

  it("D7: sin can_do o sin nodo la fila no dibuja el bloque de grafo", async () => {
    routeFetch({ student_model: MODEL, session: SESSION_NO_GRAPH, goal: GOAL });
    renderPlan(<TodayPlan userId="u1" />);

    expect(await screen.findByText("Greetings")).toBeTruthy();
    expect(screen.queryByRole("note")).toBeNull();
  });

  it("H5: un limiting factor de dimensión no-skill pinta su etiqueta (Transfer)", async () => {
    routeFetch({ student_model: MODEL, session: SESSION_TRANSFER, goal: GOAL });
    renderPlan(<TodayPlan userId="u1" />);

    expect(await screen.findByText("I can greet people politely.")).toBeTruthy();
    const note = screen.getByRole("note");
    expect(note.textContent).toContain("Transfer");
    expect(note.textContent).not.toContain(": transfer ·");
    expect(note.textContent).toContain("30%");
  });
});
