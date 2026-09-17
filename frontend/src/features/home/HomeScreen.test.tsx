// @vitest-environment jsdom
/**
 * Vitest de los hallazgos F2/F3 de la auditoría UX (V3.0) cerrados en V3.72.
 *
 * - **F2 (duplicidad de readiness):** la tríada (`TriadCard`) se reserva a
 *   Progreso/Trayecto; en Home el readiness se lee **una sola vez** (en
 *   `TodayPlan`). Este test fija que Home no vuelve a montar la tríada.
 * - **F3 (ancla «estás aquí»):** el nivel estimado se ancla con una etiqueta
 *   textual y la posición en la ruta (nivel meta), en vez de dejar el badge
 *   suelto sin decir qué es ni hacia dónde va.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { getFsrsSummary, getNextBestActivity } from "../../api/academy";
import { I18nProvider } from "../../hooks/useI18n";
import type { LearningProfile } from "../../types/api";
import { HomeScreen } from "./HomeScreen";

vi.mock("../../api/academy", () => ({
  getNextBestActivity: vi.fn(),
  getFsrsSummary: vi.fn(),
}));
vi.mock("../../components/TodayPlan", () => ({
  TodayPlan: () => <div data-testid="today-plan" />,
}));
vi.mock("../../features/review/UnitReviewPanel", () => ({
  UnitReviewPanel: () => <div data-testid="unit-review" />,
}));
vi.mock("../../components/NextBestCard", () => ({
  NextBestCard: () => <div data-testid="next-best" />,
}));

const getNextBestMock = vi.mocked(getNextBestActivity);
const getFsrsSummaryMock = vi.mocked(getFsrsSummary);

/** Perfil mínimo real: el resto de campos no los usa Home. */
function profile(): LearningProfile {
  return {
    user_id: "u1",
    current_level: "A2",
    estimated_level: "A2",
    estimated_bands: {
      listening: 0.5,
      speaking: 0.5,
      reading: 0.5,
      writing: 0.5,
      grammar: 0.5,
      pronunciation: 0.5,
    },
    estimated_descriptor: "Elementary",
    estimated_confidence: 0.8,
    overall_ability: 0.5,
    target_level: "B1",
    skills: [],
    competence_states: [],
    readiness: {
      overall: 42,
      band: "developing",
      skills: [],
      blocking_skills: [],
    },
    cefr_history: [],
    vocabulary_size: 0,
    vocabulary_exposed: 0,
    vocabulary_mastered: 0,
    top_words: [],
    recurring_errors: [],
    mastered_errors: [],
    mastered_count: 0,
    pronunciation_average: null,
    recommendations: [],
  } as unknown as LearningProfile;
}

function renderHome() {
  return render(
    <I18nProvider lang="es" setLang={() => {}}>
      <HomeScreen
        userId="u1"
        profile={profile()}
        history={null}
        userName="Ana"
        onStart={() => {}}
        onStep={() => {}}
      />
    </I18nProvider>,
  );
}

describe("HomeScreen · F2/F3 (V3.72)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getNextBestMock.mockResolvedValue(null);
    getFsrsSummaryMock.mockResolvedValue({ due_count: 0 } as never);
  });

  afterEach(cleanup);

  it("no duplica la tríada de readiness en Home (F2)", () => {
    renderHome();

    // La tríada se reserva a Progreso/Trayecto: sus tres etiquetas no deben
    // reaparecer en Home (era el origen de la duplicidad de readiness).
    expect(screen.queryByText("Preparación")).toBeNull();
    expect(screen.queryByText("Dominio")).toBeNull();
    expect(screen.queryByText("Progreso")).toBeNull();
  });

  it("ancla «estás aquí» con el nivel estimado y la meta (F3)", () => {
    renderHome();

    const anchor = screen.getByTestId("home-level-anchor");
    expect(anchor.textContent).toContain("Estás aquí");
    expect(anchor.textContent).toContain("A2");
    expect(anchor.textContent).toContain("Meta: B1");
  });
});
