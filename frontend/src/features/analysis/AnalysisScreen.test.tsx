// @vitest-environment jsdom
/**
 * Vitest de `AnalysisScreen` (V3.75.3).
 *
 * Es la pantalla que sustituye al panel flotante «Analysis»: se abre desde la
 * cabecera en `/analisis` y **sintetiza** la evolución del alumno (posición,
 * actividad, tríada, destrezas y escalera CEFR) reutilizando los endpoints que ya
 * existían. Aquí se fija lo que esa síntesis promete y lo que no:
 *
 * - pinta la posición, las destrezas con su tendencia y la escalera con «estás
 *   aquí»;
 * - **no** inventa la calidad del tutor cuando la sesión no tiene turns del
 *   asistente (el panel retirado hacía el mismo filtro para no dejar una
 *   cabecera huérfana);
 * - sin perfil no rompe: dice que hace falta uno.
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import {
  getCefrLadder,
  getDashboard,
  getStudentModel,
} from "../../api/academy";
import { getEvents } from "../../api/learning";
import { getProgressHistory } from "../../api/progress";
import { I18nProvider } from "../../hooks/useI18n";
import type { Message, StudentModel } from "../../types/api";
import { AnalysisScreen } from "./AnalysisScreen";

vi.mock("../../api/academy", () => ({
  getStudentModel: vi.fn(),
  getCefrLadder: vi.fn(),
  getDashboard: vi.fn(),
}));
vi.mock("../../api/learning", () => ({ getEvents: vi.fn() }));
vi.mock("../../api/progress", () => ({ getProgressHistory: vi.fn() }));
// El panel de calidad es una heurística de cliente con su propio test; aquí solo
// interesa **si** se monta.
vi.mock("../../components/TutorQualityPanel", () => ({
  TutorQualityPanel: () => <div data-testid="tutor-quality" />,
}));

const modelMock = vi.mocked(getStudentModel);
const ladderMock = vi.mocked(getCefrLadder);
const dashboardMock = vi.mocked(getDashboard);
const historyMock = vi.mocked(getProgressHistory);
const eventsMock = vi.mocked(getEvents);

/** Modelo mínimo real: solo lo que consume la pantalla. */
function model(): StudentModel {
  return {
    level_id: "a2",
    current_level: "A2",
    demonstrated_level: null,
    level_progress: 0.4,
    estimated_level: "A2",
    estimated_numeric: 2.4,
    confidence: 0.7,
    target_level: "B1",
    skills: [
      {
        skill: "listening",
        score: 0.62,
        confidence: 0.6,
        evidence_count: 12,
        last_evidence: "2026-09-19",
        review_due: false,
        stability: 0.5,
        trend: 0.08,
        subskills: [],
      },
      {
        skill: "grammar",
        score: 0.45,
        confidence: 0.5,
        evidence_count: 8,
        last_evidence: "2026-09-18",
        review_due: false,
        stability: 0.4,
        trend: null,
        subskills: [],
      },
    ],
    critical_skills: ["grammar"],
    readiness: {
      overall: 52,
      band: "developing",
      skills: [],
      blocking_skills: [],
    },
    reassessment: null,
    mastery: [],
  } as unknown as StudentModel;
}

function renderScreen({
  userId = "u1",
  messages = [] as Message[],
}: { userId?: string | null; messages?: Message[] } = {}) {
  return render(
    <I18nProvider lang="es" setLang={() => {}}>
      <AnalysisScreen userId={userId} messages={messages} />
    </I18nProvider>,
  );
}

describe("AnalysisScreen · V3.75.3", () => {
  beforeAll(() => {
    // jsdom no implementa `IntersectionObserver` y `SkillBar` usa `whileInView`
    // de framer-motion: sin el stub, montar la tarjeta de destrezas revienta.
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
  });

  beforeEach(() => {
    vi.clearAllMocks();
    modelMock.mockResolvedValue(model());
    ladderMock.mockResolvedValue({
      dimensions: [],
      bands: [
        { id: "a1", label: "A1", title: "Principiante", numeric: 1, description: "" },
        { id: "a2", label: "A2", title: "Básico", numeric: 2, description: "" },
        { id: "b1", label: "B1", title: "Intermedio", numeric: 3, description: "" },
      ],
      estimated_band: "a2",
      estimated_numeric: 2.4,
    } as never);
    dashboardMock.mockResolvedValue({
      progress: 40,
      mastery: 30,
      readiness: { overall: 52, band: "developing" },
    } as never);
    historyMock.mockResolvedValue({
      user_id: "u1",
      bucket: "week",
      series: [],
      streak: { current_days: 3, best_days: 5, last_active_date: "2026-09-19" },
      mastery: { active: [], resolved: [] },
      milestones: [],
    } as never);
    eventsMock.mockResolvedValue([]);
  });

  afterEach(cleanup);

  it("sintetiza posición, destrezas y escalera con «estás aquí»", async () => {
    renderScreen();

    expect(await screen.findByText("Tu evolución")).toBeTruthy();
    // Posición: la lectura de «dónde estás» con la destreza limitante.
    expect(await screen.findByText("Dónde estás")).toBeTruthy();
    const limiting = await screen.findByRole("note");
    expect(limiting.textContent).toContain("Grammar");
    // Destrezas: nombre (en inglés, decisión V3.6.1) y tendencia del modelo.
    expect(await screen.findByText("Listening")).toBeTruthy();
    expect(await screen.findByText("mejorando")).toBeTruthy();
    expect(await screen.findByText("estable")).toBeTruthy();
    // Escalera: el ancla «tú» sobre la banda estimada (`journey.you` en es).
    expect(await screen.findByText("Tú")).toBeTruthy();
  });

  it("no monta la calidad del tutor si la sesión no tiene turns del asistente", async () => {
    renderScreen();

    await waitFor(() => expect(modelMock).toHaveBeenCalled());
    expect(screen.queryByTestId("tutor-quality")).toBeNull();
  });

  it("monta la calidad del tutor cuando hay turns del asistente", async () => {
    renderScreen({
      messages: [
        { id: "m1", role: "assistant", content: "Good morning!" },
      ] as Message[],
    });

    expect(await screen.findByTestId("tutor-quality")).toBeTruthy();
  });

  it("sin perfil pide uno en vez de quedarse en blanco", async () => {
    renderScreen({ userId: null });

    expect(await screen.findByText(/Aún no hay perfil/)).toBeTruthy();
    expect(modelMock).not.toHaveBeenCalled();
  });
});
