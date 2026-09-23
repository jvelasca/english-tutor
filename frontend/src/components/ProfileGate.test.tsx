// @vitest-environment jsdom
/**
 * Puerta de entrada: elegir cuenta, entrar con contraseña o crear una (V3.81).
 *
 * Lo que se fija aquí no es «hay un campo de contraseña», sino que la puerta **no
 * promete lo que no puede cumplir**: no deja enviar una contraseña con mala forma
 * (el backend la rechazaría con 400), no se queda muda cuando no cuadra, no ofrece
 * crear una cuenta desde la LAN (fuera del equipo el backend responde 403) y no
 * atrapa a nadie en la pantalla.
 *
 * Quién decide que hace falta contraseña es el servidor: estos tests reciben el
 * estado ya resuelto por props (que es como se lo pasa `useChat`), porque lo que se
 * prueba es el contrato de la vista.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { I18nProvider } from "../hooks/useI18n";
import type { ProfileRequest, User } from "../types/api";
import { ProfileGate } from "./ProfileGate";

function user(id: string, name: string, hasPassword = false): User {
  return {
    id,
    name,
    avatar_color: "",
    avatar_emoji: "",
    avatar_image: "",
    has_password: hasPassword,
    created_at: "2026-01-01T00:00:00Z",
  };
}

const ANA = user("a", "Ana", true);
const BETO = user("b", "Beto");

afterEach(cleanup);

function renderGate(props: Partial<Parameters<typeof ProfileGate>[0]> = {}) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      <ProfileGate
        users={[ANA, BETO]}
        onSelect={() => {}}
        onRequest={async () => ({ ok: true, request: PEDIDA })}
        {...props}
      />
    </I18nProvider>,
  );
}

/** La solicitud tal como la devuelve el backend, para el caso de éxito. */
const PEDIDA: ProfileRequest = {
  id: 1,
  kind: "create",
  display_name: "Ana",
  user_id: "",
  note: "",
  requested_at: "2026-09-21T22:00:00Z",
  status: "pending",
  decided_at: "",
  decided_note: "",
  resolved_user_id: "",
};

describe("ProfileGate · lista de cuentas", () => {
  it("elegir una cuenta avisa con su id", () => {
    const onSelect = vi.fn();
    renderGate({ onSelect });
    fireEvent.click(screen.getByRole("option", { name: /Beto/ }));
    expect(onSelect).toHaveBeenCalledWith("b");
  });

  it("sin paso de contraseña no aparece el campo", () => {
    renderGate();
    expect(screen.queryByLabelText("Password")).toBeNull();
  });
});

describe("ProfileGate · paso de contraseña (V3.81)", () => {
  const passwordInput = () => screen.getByLabelText("Password") as HTMLInputElement;
  const submit = () => screen.getByRole("button", { name: "Sign in" });

  it("pide la contraseña de la cuenta que la tiene", () => {
    renderGate({ passwordUser: ANA });
    expect(screen.getByText("Ana")).toBeTruthy();
    expect(passwordInput().type).toBe("password");
    // El formulario de «pedir cuenta» no se ofrece mientras se teclea: no son dos
    // cosas que se puedan hacer a la vez.
    expect(screen.queryByLabelText("Name")).toBeNull();
  });

  it("no deja enviar con el campo vacío", () => {
    renderGate({ passwordUser: ANA, onSubmitPassword: async () => false });
    expect((submit() as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(passwordInput(), { target: { value: "c" } });
    expect((submit() as HTMLButtonElement).disabled).toBe(false);
  });

  it("envía la contraseña de la cuenta correcta", async () => {
    const onSubmitPassword = vi.fn().mockResolvedValue(true);
    renderGate({ passwordUser: ANA, onSubmitPassword });
    fireEvent.change(passwordInput(), { target: { value: "caballo-bateria" } });
    fireEvent.click(submit());
    expect(onSubmitPassword).toHaveBeenCalledWith("a", "caballo-bateria");
  });

  it("una contraseña incorrecta no se queda en silencio", () => {
    renderGate({ passwordUser: ANA, passwordFeedback: "password-invalid" });
    expect(screen.getByText("That password is not right.")).toBeTruthy();
  });

  it("el freno se explica con su propio mensaje", () => {
    renderGate({ passwordUser: ANA, passwordFeedback: "password-throttled" });
    expect(
      screen.getByText("Too many attempts. Wait a moment and try again."),
    ).toBeTruthy();
  });

  it("dice quién puede restablecerla, porque no hay correo garantizado", () => {
    renderGate({ passwordUser: ANA });
    // Dos textos hablan del webmaster en este paso (el aviso y la ayuda). Se fija
    // el de la recuperación, que es el que dice qué hacer si no te acuerdas.
    expect(screen.getByText(/resets it from the management console/)).toBeTruthy();
  });

  it("se puede volver sin quedarse atrapado en el paso de contraseña", () => {
    const onCancelPassword = vi.fn();
    renderGate({ passwordUser: ANA, onCancelPassword });
    fireEvent.click(screen.getByRole("button", { name: "Back to users" }));
    expect(onCancelPassword).toHaveBeenCalled();
  });
});

describe("ProfileGate · crear una cuenta en el equipo (V3.81)", () => {
  const openCreate = () =>
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

  it("no ofrece crear cuenta desde la LAN: el backend la cerraría con 403", () => {
    renderGate({ canCreateAccount: false, onCreateAccount: async () => ({ ok: true, user: BETO }) });
    expect(screen.queryByRole("button", { name: "Create account" })).toBeNull();
  });

  it("en el equipo ofrece el alta y pide nombre, email y contraseña", () => {
    renderGate({
      canCreateAccount: true,
      onCreateAccount: async () => ({ ok: true, user: BETO }),
    });
    openCreate();
    expect(screen.getByLabelText("Name")).toBeTruthy();
    expect(screen.getByLabelText("Email")).toBeTruthy();
    expect(screen.getByLabelText("Password")).toBeTruthy();
    expect(screen.getByLabelText("Repeat the password")).toBeTruthy();
  });

  it("no manda el alta con dos contraseñas distintas", async () => {
    const onCreateAccount = vi.fn();
    renderGate({ canCreateAccount: true, onCreateAccount });
    openCreate();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Marta" } });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "marta@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "caballo-bateria" },
    });
    fireEvent.change(screen.getByLabelText("Repeat the password"), {
      target: { value: "caballo-bateriaX" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(onCreateAccount).not.toHaveBeenCalled();
    expect(await screen.findByText(/do not match/)).toBeTruthy();
  });

  it("no manda el alta con un email que no lo es", async () => {
    const onCreateAccount = vi.fn();
    renderGate({ canCreateAccount: true, onCreateAccount });
    openCreate();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Marta" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "marta" } });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "caballo-bateria" },
    });
    fireEvent.change(screen.getByLabelText("Repeat the password"), {
      target: { value: "caballo-bateria" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(onCreateAccount).not.toHaveBeenCalled();
    expect(await screen.findByText(/does not look valid/)).toBeTruthy();
  });

  it("no manda el alta con una contraseña corta", async () => {
    const onCreateAccount = vi.fn();
    renderGate({ canCreateAccount: true, onCreateAccount });
    openCreate();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Marta" } });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "marta@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "corta" } });
    fireEvent.change(screen.getByLabelText("Repeat the password"), {
      target: { value: "corta" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(onCreateAccount).not.toHaveBeenCalled();
  });

  it("cuenta el nombre o el email ya usados con mensajes distintos", async () => {
    const onCreateAccount = vi.fn().mockResolvedValue({ ok: false, reason: "email-taken" });
    renderGate({ canCreateAccount: true, onCreateAccount });
    openCreate();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Marta" } });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "marta@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "caballo-bateria" },
    });
    fireEvent.change(screen.getByLabelText("Repeat the password"), {
      target: { value: "caballo-bateria" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("That email is already in use.")).toBeTruthy();
  });
});

describe("ProfileGate · pedir una cuenta (V3.77)", () => {
  const nameInput = () => screen.getByLabelText("Name") as HTMLInputElement;
  const submit = () => screen.getByRole("button", { name: "Ask for a user" });

  it("sigue existiendo la vía de pedir, que es la de la LAN", () => {
    // Desde otro dispositivo no se crea nada: se deja una solicitud que el
    // webmaster resuelve. Ese camino no desaparece con el registro local.
    renderGate();
    expect(submit()).toBeTruthy();
  });

  it("manda el nombre recortado y cuenta que la solicitud está enviada", async () => {
    const onRequest = vi.fn().mockResolvedValue({ ok: true, request: PEDIDA });
    renderGate({ onRequest });

    fireEvent.change(nameInput(), { target: { value: "  Ana  " } });
    fireEvent.click(submit());

    expect(onRequest).toHaveBeenCalledWith("Ana");
    expect(await screen.findByText(/Request sent/)).toBeTruthy();
    // Y no desaparece: no hay cuenta a la que entrar todavía, así que la puerta se
    // queda explicando que falta la autorización del webmaster.
    expect(nameInput().disabled).toBe(true);
    expect((submit() as HTMLButtonElement).disabled).toBe(true);
  });

  it("no deja pedir con el campo vacío", () => {
    renderGate();
    expect((submit() as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(nameInput(), { target: { value: "   " } });
    expect((submit() as HTMLButtonElement).disabled).toBe(true);
  });

  it("un nombre ya pedido se explica como espera, no como fallo", async () => {
    renderGate({
      onRequest: async () => ({ ok: false, reason: "duplicate" }),
    });
    fireEvent.change(nameInput(), { target: { value: "Ana" } });
    fireEvent.click(submit());
    expect(
      await screen.findByText("There is already a pending request with that name."),
    ).toBeTruthy();
  });

  it("la cola llena y la caída del servidor dicen cosas distintas", async () => {
    const { unmount } = renderGate({
      onRequest: async () => ({ ok: false, reason: "full" }),
    });
    fireEvent.change(nameInput(), { target: { value: "Ana" } });
    fireEvent.click(submit());
    expect(await screen.findByText(/too many pending requests/i)).toBeTruthy();
    unmount();

    renderGate({ onRequest: async () => ({ ok: false, reason: "offline" }) });
    fireEvent.change(nameInput(), { target: { value: "Ana" } });
    fireEvent.click(submit());
    expect(await screen.findByText(/Could not send the request/)).toBeTruthy();
  });

  it("tras un fallo se puede rectificar sin recargar", async () => {
    const onRequest = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, reason: "invalid" })
      .mockResolvedValueOnce({ ok: true, request: PEDIDA });
    renderGate({ onRequest });

    fireEvent.change(nameInput(), { target: { value: "Ana" } });
    fireEvent.click(submit());
    expect(await screen.findByText("That name is not valid.")).toBeTruthy();

    fireEvent.change(nameInput(), { target: { value: "Ana María" } });
    // Al escribir, el error viejo se retira: dejaría de hablar del nombre actual.
    expect(screen.queryByText("That name is not valid.")).toBeNull();
    fireEvent.click(submit());
    expect(onRequest).toHaveBeenLastCalledWith("Ana María");
    expect(await screen.findByText(/Request sent/)).toBeTruthy();
  });

  it("la puerta dice a quién hay que pedirle la autorización", () => {
    renderGate();
    expect(screen.getByText(/webmaster/)).toBeTruthy();
  });
});

describe("ProfileGate · la lista que no se pudo leer (V3.80.2)", () => {
  it("no confunde «no hay usuarios» con «no se pudo leer»", () => {
    renderGate({ users: [], loadFailed: true });
    expect(screen.getByRole("alert")).toBeTruthy();
    // La mentira que dejaba al alumno sin salida era pintar «todavía no hay
    // usuarios» cuando lo que había era un fallo de lectura.
    expect(screen.queryByText(/no users yet/i)).toBeNull();
  });

  it("ofrece reintentar en el sitio y avisa al hacerlo", () => {
    const onRetry = vi.fn();
    renderGate({ users: [], loadFailed: true, onRetry });
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("con la lista cargada bien, el aviso no aparece", () => {
    renderGate();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("option", { name: /Ana/ })).toBeTruthy();
  });

  it("ni se ofrece reintentar cuando no hace falta", () => {
    renderGate();
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});
