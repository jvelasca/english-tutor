// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import type { ReactElement } from "react";
import { StudySession } from "./StudySession";
import type { FlashcardStudyItem } from "../../types/api";
import { I18nProvider } from "../../hooks/useI18n";
import { lookupDictionaryWord, setVocabularyTranslation } from "../../api/vocabulary";

vi.mock("../../components/ItemReplayButton", () => ({
  ItemReplayButton: () => <button type="button">audio</button>,
}));

// V3.80.0: la sesión hidrata la cara B y guarda la traducción propia. Se mockean
// las dos llamadas para no depender de red y para poder afirmar QUÉ se pidió.
vi.mock("../../api/vocabulary", () => ({
  lookupDictionaryWord: vi.fn(),
  setVocabularyTranslation: vi.fn(),
}));

const lookupMock = vi.mocked(lookupDictionaryWord);
const saveMock = vi.mocked(setVocabularyTranslation);

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
    // `reset` (no `clear`): las implementaciones de los mocks de la sesión no
    // deben sobrevivir de un test a otro, o una hidratación resuelta en un test
    // se colaría en el siguiente y el orden de ejecución pasaría a importar.
    vi.resetAllMocks();
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

  it("dice que no hay cara cuando el ítem no trae dorso ni definición", async () => {
    // Una tarjeta de léxico sin traducción ni glosa es un caso real (la palabra
    // se importó sin traducción): se declara en vez de mostrar un volteo vacío.
    // V3.80.0: primero se intenta generarla; el aviso es el final del camino, no
    // la primera parada.
    lookupMock.mockResolvedValue({
      word: "airport",
      translation: "",
      definition: "",
      definition_source: "none",
    } as never);

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
      screen.getByText("Generating the reverse with the local model…"),
    ).toBeTruthy();
    expect(
      await screen.findByText(
        "No reverse side yet — write it with the pencil, or grade to schedule the review anyway.",
      ),
    ).toBeTruthy();
  });

  // --- V3.80.0: la cara B deja de ser un callejón sin salida -----------------

  it("al voltear sin reverso pide la traducción al diccionario y la pinta", async () => {
    lookupMock.mockResolvedValue({
      word: "airport",
      translation: "aeropuerto",
      definition: "A place where planes land.",
      definition_source: "llm",
    } as never);

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
    // Solo se pide para la tarjeta que se está mirando, con su cara A como clave.
    expect(lookupMock).toHaveBeenCalledTimes(1);
    expect(lookupMock.mock.calls[0][1]).toBe("airport");
    expect(await screen.findByText("aeropuerto")).toBeTruthy();
    expect(screen.getByText("A place where planes land.")).toBeTruthy();
  });

  it("con reverso ya servido no paga una generación", () => {
    // El pack y la caché ya resolvieron la cara B: pedir otra cosa sería
    // contradecir lo que el backend acaba de decidir.
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
    expect(lookupMock).not.toHaveBeenCalled();
  });

  it("si el modelo no responde lo dice y la sesión se puede calificar igual", async () => {
    lookupMock.mockRejectedValue(new Error("ollama caído"));

    const onGrade = vi.fn().mockResolvedValue(undefined);
    renderSession(
      <StudySession
        userId="u1"
        items={[card({ back: "", definition: "" })]}
        deckName="Deck"
        onGrade={onGrade}
        onExit={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Flip card" }));
    expect(
      await screen.findByText(
        "The local model did not answer. You can write the reverse yourself, or grade anyway.",
      ),
    ).toBeTruthy();
    // Un reverso que falta no bloquea el repaso: la tarjeta se programa igual.
    fireEvent.click(screen.getByText("Good"));
    expect(onGrade).toHaveBeenCalledTimes(1);
  });

  it("el lápiz guarda la traducción propia y pasa a mandar en la sesión", async () => {
    saveMock.mockResolvedValue({ word: "airport", translation: "mi aeropuerto", updated: true });

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
    fireEvent.click(screen.getByRole("button", { name: "Correct the reverse" }));

    const field = screen.getByLabelText("Reverse side (Spanish)");
    fireEvent.change(field, { target: { value: "mi aeropuerto" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(saveMock).toHaveBeenCalledWith("u1", "airport", "mi aeropuerto");
    // Lo escrito sustituye a la cara de la sesión y se declara como propia.
    expect(await screen.findByText("mi aeropuerto")).toBeTruthy();
    expect(screen.getByText("Your version")).toBeTruthy();
    expect(screen.queryByText("aeropuerto")).toBeNull();
  });

  it("el lápiz no se ofrece en tarjetas manuales (su sitio es Tarjetas)", () => {
    // Una tarjeta manual no tiene fila de léxico que corregir: el PATCH daría
    // 404. Ofrecer un lápiz que no puede guardar sería prometer de más.
    renderSession(
      <StudySession
        userId="u1"
        items={[card({ card_type: "flashcard", card_id: "7", back: "" })]}
        deckName="Deck"
        onGrade={vi.fn()}
        onExit={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Flip card" }));
    expect(screen.queryByRole("button", { name: "Write the reverse" })).toBeNull();
  });

  it("avisa si la traducción propia no se pudo guardar", async () => {
    saveMock.mockRejectedValue(new Error("500"));

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
    fireEvent.click(screen.getByRole("button", { name: "Correct the reverse" }));
    fireEvent.change(screen.getByLabelText("Reverse side (Spanish)"), {
      target: { value: "otra" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("The reverse could not be saved.")).toBeTruthy();
    // Y no se pinta como guardada: la cara sigue siendo la que había.
    expect(screen.getByText("aeropuerto")).toBeTruthy();
  });

  // --- V3.80.1: la carrera generación ↔ edición, y el badge al borrar ---------

  it("una hidratación tardía no pisa la traducción que el alumno acaba de guardar", async () => {
    // Carrera real: el modelo tarda, el alumno escribe y guarda su versión, y la
    // respuesta del modelo llega después. Debe descartarse: la verdad es lo que
    // el alumno acaba de escribir, no lo que el modelo generó tarde.
    let resolveLookup: (value: unknown) => void = () => {};
    lookupMock.mockReturnValue(
      new Promise((resolve) => {
        resolveLookup = resolve;
      }) as never,
    );
    saveMock.mockResolvedValue({
      word: "airport",
      translation: "casa",
      updated: true,
    });

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
    // Mientras el modelo piensa, el lápiz se puede usar: eso es la carrera.
    fireEvent.click(screen.getByRole("button", { name: "Write the reverse" }));
    fireEvent.change(screen.getByLabelText("Reverse side (Spanish)"), {
      target: { value: "casa" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("casa")).toBeTruthy();
    expect(screen.getByText("Your version")).toBeTruthy();

    // Ahora responde el modelo, tarde: su reverso NO puede sustituir al del alumno.
    await act(async () => {
      resolveLookup({
        word: "airport",
        translation: "aeropuerto",
        definition: "A place where planes land.",
        definition_source: "llm",
      });
    });

    expect(screen.getByText("casa")).toBeTruthy();
    expect(screen.queryByText("aeropuerto")).toBeNull();
  });

  it("borrar la traducción propia quita el badge y devuelve el reverso del pack", async () => {
    // La API acepta `translation=''` para volver a la precedencia del pack. La
    // pantalla no puede quedarse diciendo «Tu versión» sobre un texto borrado.
    saveMock
      .mockResolvedValueOnce({
        word: "airport",
        translation: "mi aeropuerto",
        updated: true,
      })
      .mockResolvedValueOnce({
        word: "airport",
        translation: "",
        updated: true,
      });

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

    // 1) Escribe su versión: manda y se declara propia.
    fireEvent.click(screen.getByRole("button", { name: "Correct the reverse" }));
    fireEvent.change(screen.getByLabelText("Reverse side (Spanish)"), {
      target: { value: "mi aeropuerto" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("mi aeropuerto")).toBeTruthy();
    expect(screen.getByText("Your version")).toBeTruthy();

    // 2) La borra: vuelve el reverso del pack y deja de ser «suya».
    fireEvent.click(screen.getByRole("button", { name: "Correct the reverse" }));
    fireEvent.change(screen.getByLabelText("Reverse side (Spanish)"), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(saveMock).toHaveBeenLastCalledWith("u1", "airport", "");
    expect(await screen.findByText("aeropuerto")).toBeTruthy();
    expect(screen.queryByText("mi aeropuerto")).toBeNull();
    expect(screen.queryByText("Your version")).toBeNull();
  });

  it("declara lang solo cuando el idioma se conoce, nunca en tarjetas manuales", () => {
    // Una tarjeta manual puede ser de cualquier idioma: `lang="en"` sería mentir.
    renderSession(
      <StudySession
        userId="u1"
        items={[card({ card_type: "flashcard", card_id: "7", back: "lucky" })]}
        deckName="Deck"
        onGrade={vi.fn()}
        onExit={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Flip card" }));

    const front = screen.getByText("airport");
    const back = screen.getByText("lucky");
    expect(front.getAttribute("lang")).toBeNull();
    expect(back.getAttribute("lang")).toBeNull();
  });

  it("declara lang en→es en las tarjetas del léxico, que sí lo tienen por construcción", () => {
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

    expect(screen.getByText("airport").getAttribute("lang")).toBe("en");
    expect(screen.getByText("aeropuerto").getAttribute("lang")).toBe("es");
  });

  // --- V3.83.0: la sesión como juego (progreso, atajos, celebración) ---------

  it("muestra una barra de progreso que avanza con la sesión", async () => {
    renderSession(
      <StudySession
        userId="u1"
        items={[card(), card({ card_id: "ticket", front: "ticket" })]}
        deckName="Deck"
        onGrade={vi.fn().mockResolvedValue(undefined)}
        onExit={() => {}}
      />,
    );

    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe(
      "50",
    );

    fireEvent.click(screen.getByRole("button", { name: "Flip card" }));
    fireEvent.click(screen.getByText("Good"));

    // La segunda tarjeta llega con la barra al 100 %.
    await screen.findByText("ticket");
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe(
      "100",
    );
  });

  it("califica con los atajos 1–4 sin tocar el ratón", async () => {
    const onGrade = vi.fn().mockResolvedValue(undefined);
    renderSession(
      <StudySession
        userId="u1"
        items={[card()]}
        deckName="Deck"
        onGrade={onGrade}
        onExit={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Flip card" }));
    // Solo cuentan cuando la tarjeta ya está revelada.
    fireEvent.keyDown(window, { key: "3" });

    expect(await screen.findByText("Session done — 1 cards reviewed.")).toBeTruthy();
    expect(onGrade).toHaveBeenCalledTimes(1);
    expect(onGrade.mock.calls[0][1]).toBe(3);
  });

  it("declara el acierto de la sesión y reserva el atajo en el botón de nota", async () => {
    renderSession(
      <StudySession
        userId="u1"
        items={[card(), card({ card_id: "ticket", front: "ticket" })]}
        deckName="Deck"
        onGrade={vi.fn().mockResolvedValue(undefined)}
        onExit={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Flip card" }));
    // El atajo va declarado en el propio botón (accesibilidad), pero el nombre
    // accesible sigue siendo «Good», no «3Good».
    expect(
      screen
        .getByText("Good")
        .closest("button")
        ?.getAttribute("aria-keyshortcuts"),
    ).toBe("3");

    fireEvent.click(screen.getByText("Good"));
    await screen.findByText("ticket");
    fireEvent.click(screen.getByRole("button", { name: "Flip card" }));
    fireEvent.click(screen.getByText("Good"));

    expect(
      await screen.findByText("Session done — 2 cards reviewed."),
    ).toBeTruthy();
    // Acierto de ESTA sesión, no una nota de dominio (D5/E3).
    expect(
      screen.getByText("100% of this session rated Good or Easy."),
    ).toBeTruthy();
  });
});
