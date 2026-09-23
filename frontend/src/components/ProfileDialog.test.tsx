// @vitest-environment jsdom
/**
 * Vitest de `ProfileDialog` (V3.79.0): la baja del perfil.
 *
 * Lo que se fija aquí es lo que hizo que «Pedir dar de baja mi perfil» no
 * funcionara en la mano del alumno:
 *
 * 1. Un clic no se convierte en dos peticiones. El botón solo se deshabilitaba
 *    *después* del éxito, así que la impaciencia mandaba otra y gastaba cupo
 *    justo cuando el backend pedía esperar.
 * 2. Un 429 por cupo dice CUÁNDO reintentar. El backend manda `Retry-After` y
 *    antes se tiraba: el alumno veía «el servidor está saturado» y ahí se
 *    quedaba, sin saber si era un fallo de verdad.
 * 3. El éxito dice qué pasa ahora (la cola del webmaster). No promete que el
 *    perfil desaparece porque ni la app ni el alumno lo borran.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ProfileRequestOutcome } from "../api/profileRequests";
import type { User } from "../types/api";
import { I18nProvider } from "../hooks/useI18n";
import { ProfileDialog } from "./ProfileDialog";

const USER: User = {
  id: "u1",
  name: "Ana",
  avatar_color: "",
  avatar_emoji: "",
  avatar_image: "",
  status: "active",
  created_at: "",
} as User;

function renderDialog(
  onRequestDelete: (note: string) => Promise<ProfileRequestOutcome>,
) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      {/* Un envoltorio con la MARCA del header real: el menú de usuario vive
          dentro de un `<header>` con `backdrop-filter`, que crea bloque
          contenedor para `position: fixed`. Si el diálogo no sale de aquí, el
          `inset: 0` de su backdrop no mide el viewport y se recorta. */}
      <div className="app-header-stub" style={{ backdropFilter: "blur(24px)" }}>
        <ProfileDialog
          user={USER}
          onClose={() => {}}
          onSave={vi.fn().mockResolvedValue(USER)}
          onRequestDelete={onRequestDelete}
        />
      </div>
    </I18nProvider>,
  );
}

const requestButton = () =>
  screen.getByRole("button", { name: "Ask the webmaster to remove me" }) as HTMLButtonElement;

describe("ProfileDialog · pedir la baja", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("se monta fuera del header, que es lo que hacía inalcanzable su cabecera", () => {
    // El fallo de verdad del recorte: el diálogo se abría desde el menú de
    // usuario, dentro de un `<header>` con `backdrop-filter`, que **crea bloque
    // contenedor para `position: fixed`**. El `inset: 0` del backdrop medía la
    // franja del header (~80 px) en vez del viewport, así que el diálogo —más
    // alto— se recortaba por arriba y el asa de cerrar quedaba fuera.
    //
    // El candado: el backdrop tiene que ser hijo DIRECTO de `document.body`, no
    // del envoltorio donde se escribió el componente.
    renderDialog(vi.fn().mockResolvedValue({ ok: true, request: { id: 1 } as never }));

    const backdrop = document.querySelector(".dialog-backdrop");
    expect(backdrop).not.toBeNull();
    expect(backdrop!.parentElement).toBe(document.body);
    expect(backdrop!.closest(".app-header-stub")).toBeNull();
  });

  it("un clic no se convierte en dos peticiones", async () => {
    // La promesa se resuelve a mano: mientras está en vuelo, el botón tiene que
    // estar deshabilitado, o el segundo clic manda otra petición al servidor.
    let release: (outcome: ProfileRequestOutcome) => void = () => {};
    const pending = new Promise<ProfileRequestOutcome>((resolve) => {
      release = resolve;
    });
    const onRequestDelete = vi.fn().mockReturnValue(pending);

    renderDialog(onRequestDelete);
    fireEvent.click(requestButton());
    fireEvent.click(requestButton());
    fireEvent.click(requestButton());

    expect(onRequestDelete).toHaveBeenCalledTimes(1);
    expect(requestButton().disabled).toBe(true);

    release({ ok: true, request: { id: 1 } as never });
    await waitFor(() => expect(requestButton().disabled).toBe(true));
    // Tras el éxito sigue deshabilitado: la baja ya está pedida.
    expect(screen.getByText(/Request sent/)).toBeTruthy();
  });

  it("un 429 dice cuántos segundos esperar en vez de quedarse en «saturado»", async () => {
    renderDialog(
      vi.fn().mockResolvedValue({
        ok: false,
        reason: "throttled",
        retryAfterSeconds: 5,
      }),
    );

    fireEvent.click(requestButton());

    expect(
      await screen.findByText("The server asked to wait 5s before trying again."),
    ).toBeTruthy();
    // Se puede reintentar: un aviso de espera no bloquea la acción.
    expect(requestButton().disabled).toBe(false);
  });

  it("un 429 sin Retry-After cae al mensaje genérico del cupo", async () => {
    // El backend puede no mandar la cabecera; el aviso tiene que seguir siendo
    // legible y no quedarse en un «{n}» sin sustituir.
    renderDialog(vi.fn().mockResolvedValue({ ok: false, reason: "throttled" }));

    fireEvent.click(requestButton());

    expect(
      await screen.findByText(
        "The local server is busy: wait a few seconds and try again",
      ),
    ).toBeTruthy();
  });

  it("una baja ya pedida se cuenta como tal", async () => {
    renderDialog(vi.fn().mockResolvedValue({ ok: false, reason: "duplicate" }));

    fireEvent.click(requestButton());

    expect(
      await screen.findByText("You have already asked for this user to be removed."),
    ).toBeTruthy();
  });
});
