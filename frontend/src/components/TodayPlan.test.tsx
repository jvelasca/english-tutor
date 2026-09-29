// @vitest-environment jsdom
/**
 * Vitest de `TodayPlan` (V3.17 D6/M1 + V3.90 Plan diario).
 *
 * Mockea `fetch` para `getStudentModel`; el plan diario entra como PROP (lo lee
 * Home) y se construye aquí, de modo que cada test fija exactamente el estado del
 * día que quiere probar. Verifica que:
 *
 * - un paso con `can_do` + `limiting_factor` del Evidence Graph dibuja las dos
 *   micro-líneas informativas dentro de la fila-botón (D6);
 * - un paso SIN objetivo o sin nodo (D7) no dibuja el bloque de grafo (silente);
 * - el chip del factor limitante pinta la etiqueta humana (H5);
 * - V3.90: la barra «OBJETIVO DE HOY» publica el porcentaje del objetivo, el
 *   aviso de que los minutos son estimación del motor, los repasos pendientes con
 *   su origen y la precisión de hoy (o «sin datos», nunca un 0 disfrazado);
 * - V3.90: con el objetivo cumplido no se lista trabajo y se dice que está
 *   cumplido;
 * - V3.90: el formulario guarda el plan diario completo (modo, unidades, tope de
 *   nuevas, destrezas incluidas) en el MISMO objeto del objetivo.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { I18nProvider } from "../hooks/useI18n";
import { TodayPlan } from "./TodayPlan";
import type {
  DailyPlan,
  DailyPlanMetrics,
  DailyPlanPending,
  DailyPlanProgress,
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
  plan_mode: "time",
  target_units: 0,
  max_new: 1,
  include_listening: true,
  include_speaking: true,
};

const MODEL: StudentModel = {
  level_id: "a1",
  current_level: "A1",
  demonstrated_level: null,
  level_progress: 0,
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

const EMPTY_SESSION: SessionData = {
  total_minutes: 0,
  review_count: 0,
  practice_count: 0,
  items: [],
};

function progress(over: Partial<DailyPlanProgress> = {}): DailyPlanProgress {
  return {
    units_done: 1,
    units_target: 0,
    minutes_done: 10,
    minutes_target: 30,
    units_ratio: null,
    minutes_ratio: 0.333,
    percent: 0.333,
    done: false,
    ...over,
  };
}

function metrics(over: Partial<DailyPlanMetrics> = {}): DailyPlanMetrics {
  return {
    day: "2026-09-29",
    units: 1,
    unknown_units: 0,
    minutes: 10,
    reviews: 0,
    new: 1,
    listening: 0,
    practice: 0,
    speaking: 0,
    listening_attempts: 0,
    listening_accuracy: null,
    accuracy: null,
    difficulty_evidence: 0,
    words_flagged: 0,
    by_kind: { new: 1 },
    by_skill: { vocabulary: 1 },
    ...over,
  };
}

function pending(over: Partial<DailyPlanPending> = {}): DailyPlanPending {
  return { fsrs: 0, listening: 0, total: 0, ...over };
}

function plan(over: Partial<DailyPlan> = {}): DailyPlan {
  return {
    goal: GOAL,
    plan_mode: "time",
    minutes_target: 30,
    units_target: 0,
    units_remaining: null,
    minutes_remaining: 20,
    include_listening: true,
    include_speaking: true,
    pending: pending(),
    progress: progress(),
    metrics: metrics(),
    session: SESSION_GRAPH,
    ...over,
  };
}

// --- Helpers ---------------------------------------------------------------

function routeModel(model: StudentModel | null) {
  const fn = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (!url.includes("/student-model")) {
      return Promise.reject(new Error(`unexpected fetch: ${url}`));
    }
    return Promise.resolve({ ok: true, json: async () => model });
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
    routeModel(MODEL);
    renderPlan(<TodayPlan userId="u1" plan={plan()} />);

    // El can-do del grafo aparece como micro-línea informativa de la fila.
    expect(await screen.findByText("I can greet people politely.")).toBeTruthy();
    // Chip del factor limitante: etiqueta de destreza (inmersión en inglés) + pct.
    const note = screen.getByRole("note");
    expect(note.textContent).toContain("Grammar");
    expect(note.textContent).toContain("42%");
  });

  it("D7: sin can_do o sin nodo la fila no dibuja el bloque de grafo", async () => {
    routeModel(MODEL);
    renderPlan(
      <TodayPlan userId="u1" plan={plan({ session: SESSION_NO_GRAPH })} />,
    );

    expect(await screen.findByText("Greetings")).toBeTruthy();
    expect(screen.queryByRole("note")).toBeNull();
  });

  it("H5: un limiting factor de dimensión no-skill pinta su etiqueta (Transfer)", async () => {
    routeModel(MODEL);
    renderPlan(
      <TodayPlan userId="u1" plan={plan({ session: SESSION_TRANSFER })} />,
    );

    expect(await screen.findByText("I can greet people politely.")).toBeTruthy();
    const note = screen.getByRole("note");
    expect(note.textContent).toContain("Transfer");
    expect(note.textContent).not.toContain(": transfer ·");
    expect(note.textContent).toContain("30%");
  });

  it("F2 (V3.72): el readiness se lee una sola vez en Home", async () => {
    // `TodayPlan` es la ÚNICA superficie de readiness de Home desde V3.72: la
    // tríada (`TriadCard`) se reserva a Progreso/Trayecto (hallazgo F2 de la
    // auditoría UX). Si este test empieza a encontrar dos barras, la duplicidad
    // ha vuelto.
    routeModel(MODEL);
    renderPlan(<TodayPlan userId="u1" plan={plan()} />);

    await screen.findByText("Greetings");

    const bars = screen.getAllByRole("progressbar");
    expect(bars).toHaveLength(2); // objetivo del día (V3.90) + readiness
    // V3.90: la barra del plan diario se etiqueta; el readiness conserva la suya
    // y sigue siendo la única superficie de lectura de readiness en Home.
    const goalBar = screen.getByRole("progressbar", {
      name: "Today's goal",
    });
    expect(goalBar).toBeTruthy();
    const readiness = bars.filter((b) => b !== goalBar);
    expect(readiness).toHaveLength(1);
    expect(readiness[0].getAttribute("aria-valuenow")).toBe("55");
  });
});

describe("TodayPlan plan diario (V3.90)", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("publica el porcentaje del objetivo y aclara que los minutos son estimación", async () => {
    routeModel(MODEL);
    renderPlan(<TodayPlan userId="u1" plan={plan()} />);

    await screen.findByText("Greetings");
    expect(screen.getByTestId("goal-progress-pct").textContent).toBe("33%");
    // El porcentaje sale del dato del backend, no de una regla de tres local.
    const bar = screen.getByRole("progressbar", { name: "Today's goal" });
    expect(bar.getAttribute("aria-valuenow")).toBe("33");
    expect(screen.getByText(/engine estimate/)).toBeTruthy();
  });

  it("los objetivos se declaran por separado: unidades y minutos", async () => {
    routeModel(MODEL);
    renderPlan(
      <TodayPlan
        userId="u1"
        plan={plan({
          goal: { ...GOAL, plan_mode: "mixed", target_units: 3 },
          plan_mode: "mixed",
          units_target: 3,
          units_remaining: 2,
          progress: progress({
            units_done: 1,
            units_target: 3,
            units_ratio: 0.333,
            minutes_ratio: 0.5,
            percent: 0.333,
          }),
        })}
      />,
    );

    await screen.findByText("Greetings");
    const detail = document.querySelector(".goal-progress-detail")?.textContent;
    expect(detail).toContain("1 / 3");
    expect(detail).toContain("10 / 30");
  });

  it("los repasos pendientes se publican con su origen", async () => {
    routeModel(MODEL);
    renderPlan(
      <TodayPlan
        userId="u1"
        plan={plan({ pending: pending({ fsrs: 4, listening: 2, total: 6 }) })}
      />,
    );

    await screen.findByText("Greetings");
    expect(screen.getByText(/Pending reviews: 6/)).toBeTruthy();
    expect(screen.getByText(/4 FSRS/)).toBeTruthy();
  });

  it("la precisión de hoy se declara, y sin datos dice que no hay datos", async () => {
    routeModel(MODEL);
    const { unmount } = renderPlan(
      <TodayPlan userId="u1" plan={plan({ metrics: metrics({ accuracy: 0.75 }) })} />,
    );
    await screen.findByText("Greetings");
    expect(screen.getByText(/75%/)).toBeTruthy();
    unmount();

    cleanup();
    routeModel(MODEL);
    renderPlan(<TodayPlan userId="u1" plan={plan()} />);
    await screen.findByText("Greetings");
    expect(screen.getByText(/No data yet/)).toBeTruthy();
  });

  it("con el objetivo cumplido no se lista trabajo y se dice que está cumplido", async () => {
    routeModel(MODEL);
    renderPlan(
      <TodayPlan
        userId="u1"
        plan={plan({
          session: EMPTY_SESSION,
          minutes_remaining: 0,
          progress: progress({
            minutes_done: 30,
            minutes_ratio: 1,
            percent: 1,
            done: true,
          }),
        })}
      />,
    );

    expect(await screen.findByText("Today's goal is met")).toBeTruthy();
    expect(screen.queryByText("Greetings")).toBeNull();
  });

  it("V3.92: la evidencia de dificultad se declara aparte y solo si la hay", async () => {
    routeModel(MODEL);
    const { unmount } = renderPlan(
      <TodayPlan
        userId="u1"
        plan={plan({
          metrics: metrics({ difficulty_evidence: 3, words_flagged: 2 }),
        })}
      />,
    );
    await screen.findByText("Greetings");
    // Se nombra como evidencia (cuántas palabras) y se aclara que no es repaso.
    expect(screen.getByText(/Words that got harder: 2/)).toBeTruthy();
    expect(screen.getByText(/3 listening misses; it's evidence, not a review/)).toBeTruthy();
    // Y no se confunde con repaso pendiente: la cola sigue a cero.
    expect(screen.getAllByText(/Pending reviews: 0/).length).toBeGreaterThan(0);
    unmount();

    cleanup();
    routeModel(MODEL);
    renderPlan(<TodayPlan userId="u1" plan={plan()} />);
    await screen.findByText("Greetings");
    // Sin evidencia, el bloque no aparece: no se inventa un cero.
    expect(screen.queryByTestId("goal-difficulty-evidence")).toBeNull();
  });

  it("el formulario guarda el plan diario completo del objetivo", async () => {
    const fetchMock = routeModel(MODEL);
    renderPlan(<TodayPlan userId="u1" plan={plan()} />);
    await screen.findByText("Greetings");

    fireEvent.click(screen.getByText("Edit"));
    fireEvent.change(screen.getByLabelText("Daily plan"), {
      target: { value: "units" },
    });
    // En modo unidades el campo aparece; en modo tiempo no se pide.
    fireEvent.change(screen.getByLabelText("Units"), { target: { value: "4" } });
    fireEvent.change(screen.getByLabelText("New items max"), {
      target: { value: "0" },
    });
    fireEvent.click(screen.getByLabelText("Include Listening"));
    fireEvent.click(screen.getByText("Save"));

    const put = await vi.waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([, init]) => (init as RequestInit | undefined)?.method === "PUT",
      );
      expect(call).toBeTruthy();
      return call as [RequestInfo | URL, RequestInit];
    });
    const body = JSON.parse(String(put[1].body));
    expect(body.plan_mode).toBe("units");
    expect(body.target_units).toBe(4);
    expect(body.max_new).toBe(0);
    expect(body.include_listening).toBe(false);
    expect(body.include_speaking).toBe(true);
  });
});

describe("TodayPlan replegado sin plan diario (V3.90)", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  /** Stub que sirve student-model + goal + session y registra las rutas pedidas. */
  function routeFallback() {
    const fn = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/student-model")) {
        return Promise.resolve({ ok: true, json: async () => MODEL });
      }
      if (url.includes("/academy/goal")) {
        return Promise.resolve({ ok: true, json: async () => GOAL });
      }
      if (url.includes("/academy/session")) {
        return Promise.resolve({ ok: true, json: async () => SESSION_GRAPH });
      }
      return Promise.reject(new Error(`unexpected fetch: ${url}`));
    });
    vi.stubGlobal("fetch", fn);
    return fn;
  }

  it("sin plan diario se relee objetivo y sesión y el plan no desaparece", async () => {
    routeFallback();
    renderPlan(<TodayPlan userId="u1" plan={null} />);

    // El objetivo y los pasos siguen ahí (comportamiento V3.89)…
    expect(await screen.findByText("General conversation")).toBeTruthy();
    expect(await screen.findByText("Greetings")).toBeTruthy();
    // …y NO se inventa la barra del objetivo: sus métricas solo las trae el plan.
    expect(
      screen.queryByRole("progressbar", { name: "Today's goal" }),
    ).toBeNull();
    // La única barra que queda es el readiness de siempre.
    expect(screen.getAllByRole("progressbar")).toHaveLength(1);
  });

  it("con plan diario no se relee goal ni session: Home hace una sola lectura", async () => {
    const fetchMock = routeFallback();
    renderPlan(<TodayPlan userId="u1" plan={plan()} />);

    await screen.findByText("Greetings");
    const urls = fetchMock.mock.calls.map(([input]) => String(input));
    expect(urls.some((u) => u.includes("/student-model"))).toBe(true);
    expect(urls.some((u) => u.includes("/academy/goal"))).toBe(false);
    expect(urls.some((u) => u.includes("/academy/session"))).toBe(false);
  });

  it("mientras el plan carga no se piden goal ni session por duplicado", async () => {
    const fetchMock = routeFallback();
    renderPlan(<TodayPlan userId="u1" plan={null} planStatus="loading" />);

    // El Student Model sí se lee (lo necesita el readiness del plan)…
    await vi.waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).includes("/student-model"),
        ),
      ).toBe(true);
    });
    // …pero el replegado no dispara una segunda lectura de objetivo y sesión.
    const urls = fetchMock.mock.calls.map(([input]) => String(input));
    expect(urls.some((u) => u.includes("/academy/goal"))).toBe(false);
    expect(urls.some((u) => u.includes("/academy/session"))).toBe(false);
  });

  it("tras fallar la lectura del plan sí se relee goal y session", async () => {
    const fetchMock = routeFallback();
    renderPlan(<TodayPlan userId="u1" plan={null} planStatus="error" />);

    expect(await screen.findByText("General conversation")).toBeTruthy();
    const urls = fetchMock.mock.calls.map(([input]) => String(input));
    expect(urls.some((u) => u.includes("/academy/goal"))).toBe(true);
    expect(urls.some((u) => u.includes("/academy/session"))).toBe(true);
  });
});
