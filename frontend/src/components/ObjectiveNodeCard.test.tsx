// @vitest-environment jsdom
/**
 * Vitest de `ObjectiveNodeCard` (V3.18, D7.1/H5): distingue el 404/sin-datos
 * (copia vacía) del error real (copia de error + reintento), y pinta las
 * dimensiones con etiqueta humana en inglés de inmersión (nunca el id crudo).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { I18nProvider } from "../hooks/useI18n";
import { ObjectiveNodeCard } from "./ObjectiveNodeCard";

const NODE = {
  objective_id: "a1-m01-u01-l01-o01",
  title: "Greetings",
  can_do: "I can greet people politely.",
  level: "A1",
  level_id: "a1",
  mastery: 0.42,
  dimensions: [
    { id: "grammar", score: 0.3, missing: false },
    { id: "transfer", score: 0.2, missing: false },
  ],
  limiting_factor: { id: "transfer", score: 0.2, missing: false },
  recommended_focus: { dimension: "transfer", phase: "transfer" },
  graph_mastery: 0.2,
  because: ["Transfer is the limiting factor of this can-do."],
};

type ResponseLike = {
  ok: boolean;
  status?: number;
  json: () => Promise<unknown>;
};

function okJson(payload: unknown): ResponseLike {
  return { ok: true, status: 200, json: async () => payload };
}
function http(status: number): ResponseLike {
  return { ok: false, status, json: async () => ({ detail: "x" }) };
}

function stubFetch(responses: ResponseLike[]) {
  const fn = vi.fn();
  responses.forEach((r) => fn.mockResolvedValueOnce(r));
  vi.stubGlobal("fetch", fn);
  return fn;
}

function renderCard() {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      <ObjectiveNodeCard userId="u1" objectiveId="a1-m01-u01-l01-o01" />
    </I18nProvider>,
  );
}

describe("ObjectiveNodeCard (V3.18, D7.1/H5)", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("404/sin-datos: copia vacía, sin botón de reintento", async () => {
    stubFetch([http(404)]);
    renderCard();
    expect(
      await screen.findByText("No evidence graph yet."),
    ).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("error real (5xx): copia de error y reintento que recupera el nodo", async () => {
    stubFetch([http(500), okJson(NODE)]);
    renderCard();

    // Primera petición falla → copia de error + botón reintento.
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(
      screen.getByText("Could not load the evidence graph."),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    // El reintento refetches y muestra el nodo.
    expect(await screen.findByText("I can greet people politely.")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("nodo con dimensión no-skill: etiqueta humana, no el id en crudo", async () => {
    stubFetch([okJson(NODE)]);
    renderCard();

    expect(await screen.findByText("I can greet people politely.")).toBeTruthy();
    // Dimensiones: etiqueta humana ("Grammar", "Transfer · limiting"); nunca
    // el id en crudo ("grammar"/"transfer" como texto exacto).
    expect(screen.getByText("Grammar")).toBeTruthy();
    expect(screen.getByText("Transfer · limiting")).toBeTruthy();
    expect(screen.queryByText("grammar")).toBeNull();
    expect(screen.queryByText("transfer")).toBeNull();
    // Foco recomendado: la DIMENSIÓN se etiqueta; la fase es un valor máquina.
    expect(screen.getByText(/Recommended focus/).textContent).toContain(
      "Transfer → transfer",
    );
  });
});
