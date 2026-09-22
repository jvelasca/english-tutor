// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { StudySession } from "./StudySession";
import type { FlashcardStudyItem } from "../../types/api";
import { I18nProvider } from "../../hooks/useI18n";

vi.mock("../../components/ItemReplayButton", () => ({
  ItemReplayButton: () => <button type="button">audio</button>,
}));

function renderSession(ui: ReactElement) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      {ui}
    </I18nProvider>,
  );
}

function card(overrides: Partial<FlashcardStudyItem> = {}): FlashcardStudyItem {
  return {
    card_type: "lexicon",
    card_id: "airport",
    front: "airport",
    back: "aeropuerto",
    definition: "",
    is_new: true,
    state: "new",
    due_at: "",
    reps: 0,
    retrievability: 1,
    ...overrides,
  };
}

describe("StudySession", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("voltea, delega el grado al contenedor y avanza", async () => {
    const onGrade = vi.fn().mockResolvedValue(undefined);

    renderSession(
      <StudySession
        userId="u1"
        items={[card(), card({ card_id: "ticket", front: "ticket" })]}
        deckName="Deck"
        onGrade={onGrade}
        onExit={() => {}}
      />,
    );

    expect(screen.getByText("1 / 2")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Flip card" }));
    expect(screen.getByText("aeropuerto")).toBeTruthy();
    fireEvent.click(screen.getByText("Good"));

    // V3.78.0: la sesión NO conoce el endpoint; el contenedor sí. Lo único que
    // debe garantizar es que le pasa el ítem y el grado EXACTOS.
    expect(onGrade).toHaveBeenCalledTimes(1);
    expect(onGrade.mock.calls[0][0]).toMatchObject({ card_id: "airport" });
    expect(onGrade.mock.calls[0][1]).toBe(3);
  });

  it("al gradear la última tarjeta se ve el resumen, no una recarga silenciosa", async () => {
    // V3.77.2: antes el último grado recargaba la cola y reseteaba el contador,
    // así que la pantalla de fin era inalcanzable. El candado se conserva en el
    // componente generalizado, que es quien podría volver a romperlo.
    const items = [card(), card({ card_id: "ticket", front: "ticket" })];
    const onGrade = vi.fn().mockResolvedValue(undefined);
    const onExit = vi.fn();

    renderSession(
      <StudySession
        userId="u1"
        items={items}
        deckName="Deck"
        onGrade={onGrade}
        onExit={onExit}
      />,
    );

    for (const front of ["airport", "ticket"]) {
      expect(await screen.findByText(front)).toBeTruthy();
      fireEvent.click(screen.getByRole("button", { name: "Flip card" }));
      fireEvent.click(screen.getByText("Good"));
    }

    expect(await screen.findByText("Session done — 2 cards reviewed.")).toBeTruthy();
    expect(onGrade).toHaveBeenCalledTimes(2);
    // La pantalla de fin ofrece salida; con `onRestart` además ofrece actualizar.
    expect(screen.getByRole("button", { name: "Back" })).toBeTruthy();
  });

  it("solo ofrece «Refresh» cuando el contenedor sabe reiniciar la sesión", async () => {
    // Un botón que no puede hacer lo que promete es peor que no tenerlo: el
    // diccionario incrustado no tiene superficie de estudio, así que ahí no se
    // pinta.
    renderSession(
      <StudySession
        userId="u1"
        items={[card()]}
        deckName="Deck"
        onGrade={vi.fn()}
        onExit={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Flip card" }));
    fireEvent.click(screen.getByText("Good"));

    expect(await screen.findByText("Session done — 1 cards reviewed.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Refresh" })).toBeNull();
  });

  it("sale con «Back» desde el resumen y ofrece actualizar si el contenedor sabe reiniciar", async () => {
    const onExit = vi.fn();
    const onRestart = vi.fn();
    renderSession(
      <StudySession
        userId="u1"
        items={[card()]}
        deckName="Deck"
        onGrade={vi.fn().mockResolvedValue(undefined)}
        onExit={onExit}
        onRestart={onRestart}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Flip card" }));
    fireEvent.click(screen.getByText("Good"));

    expect(await screen.findByText("Session done — 1 cards reviewed.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    expect(onRestart).toHaveBeenCalledTimes(1);
    expect(onExit).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(onExit).toHaveBeenCalledTimes(1);
  });

  it("dice que no hay cara cuando el ítem no trae dorso ni definición", () => {
    // Una tarjeta de léxico sin traducción ni glosa es un caso real (la palabra
    // se importó sin traducción): se declara en vez de mostrar un volteo vacío.
    renderSession(
      <StudySession
        userId="u1"
        items={[card({ back: "", definition: "" })]}
        deckName="Deck"
        onGrade={vi.fn()}
        onExit={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Flip card" }));
    expect(
      screen.getByText(
        "No translation cached yet — grade to schedule the review anyway.",
      ),
    ).toBeTruthy();
  });
});
