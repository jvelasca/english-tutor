// @vitest-environment jsdom
/**
 * Puerta de entrada (V3.82): entrar con email + contraseña, pedir acceso o
 * recuperar la contraseña.
 *
 * Lo que se fija aquí no es «hay un campo de email», sino que la puerta **no
 * promete lo que no puede cumplir** y **no deja entrar sin demostrar nada**:
 *
 * - No hay lista de cuentas que elegir. Esto es lo que hacía posible nombrar a
 *   otra persona, y es la razón de que la puerta ya no sepa quién existe.
 * - Los desenlaces que trae `useChat` (credenciales malas, cuenta sin activar,
 *   freno) se pintan con textos distintos, porque mandan a hacer cosas distintas.
 * - El formulario de solicitud exige un email con forma: sin él no hay forma de
 *   mandar la invitación, así que dejarle enviar sería prometer un correo que no
 *   puede salir.
 *
 * Quién decide si la credencial vale es el servidor: estos tests reciben el
 * desenlace ya resuelto por props (que es como se lo pasa `useChat`), porque lo
 * que se prueba es el contrato de la vista.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { I18nProvider } from "../hooks/useI18n";
import type { ProfileRequest } from "../types/api";
import type { LoginOutcome } from "../hooks/useChat";
import { ProfileGate } from "./ProfileGate";

afterEach(cleanup);

/** La solicitud tal como la devuelve el backend, para el caso de éxito. */
const PEDIDA: ProfileRequest = {
  id: 1,
  kind: "create",
  display_name: "Ana",
  user_id: "",
  note: "",
  email: "ana@example.com",
  requested_at: "2026-09-21T22:00:00Z",
  status: "pending",
  decided_at: "",
  decided_note: "",
  resolved_user_id: "",
};

function renderGate(props: Partial<Parameters<typeof ProfileGate>[0]> = {}) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      <ProfileGate
        onLogin={async () => ({ ok: true, user: { id: "a", name: "Ana", created_at: "" } })}
        onRequest={async () => ({ ok: true, request: PEDIDA })}
        onForgot={async () => ({ sent: true })}
        {...props}
      />
    </I18nProvider>,
  );
}

const emailInput = () => screen.getByLabelText("Email") as HTMLInputElement;
const passwordInput = () =>
  screen.getByLabelText("Password") as HTMLInputElement;
const signIn = () => screen.getByRole("button", { name: "Sign in" });

async function fillLogin(email = "ana@example.com", password = "caballo-bateria") {
  fireEvent.change(emailInput(), { target: { value: email } });
  fireEvent.change(passwordInput(), { target: { value: password } });
}

describe("ProfileGate · entrar (V3.82)", () => {
  it("ya no hay lista de cuentas: la puerta no enumera a nadie", () => {
    // Es la decisión de fondo de V3.82. Un `GET /api/users` sin sesión convertía
    // la pantalla de entrada en un censo de quién tiene cuenta.
    renderGate();
    expect(screen.queryByRole("option")).toBeNull();
    expect(screen.queryByText("Beto")).toBeNull();
  });

  it("no deja enviar hasta tener email y contraseña", () => {
    renderGate();
    expect((signIn() as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(emailInput(), { target: { value: "ana@example.com" } });
    expect((signIn() as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(passwordInput(), { target: { value: "c" } });
    expect((signIn() as HTMLButtonElement).disabled).toBe(false);
  });

  it("manda lo tecleado al abrir la sesión", async () => {
    const onLogin = vi.fn().mockResolvedValue({
      ok: true,
      user: { id: "a", name: "Ana", created_at: "" },
    });
    renderGate({ onLogin });
    await fillLogin();
    fireEvent.click(signIn());
    expect(onLogin).toHaveBeenCalledWith("ana@example.com", "caballo-bateria");
  });

  it("unas credenciales que no cuadran no se quedan en silencio", async () => {
    renderGate({
      onLogin: async () => ({ ok: false, reason: "invalid-credentials" }),
    });
    await fillLogin();
    fireEvent.click(signIn());
    expect(
      await screen.findByText("That email or password is not right."),
    ).toBeTruthy();
    // Y la contraseña se vacía: dejarla puesta invita a reintentar lo mismo.
    expect(passwordInput().value).toBe("");
  });

  it("una cuenta sin activar manda al enlace del correo, no a «algo falló»", async () => {
    // El texto importa: es una instrucción que sí se puede seguir.
    renderGate({ onLogin: async () => ({ ok: false, reason: "not-activated" }) });
    await fillLogin();
    fireEvent.click(signIn());
    expect(await screen.findByText(/not activated yet/)).toBeTruthy();
  });

  it("«fuera de servicio» y «dada de baja» dicen cosas distintas", async () => {
    const { unmount } = renderGate({
      onLogin: async () => ({ ok: false, reason: "disabled" }),
    });
    await fillLogin();
    fireEvent.click(signIn());
    expect(await screen.findByText(/out of service/)).toBeTruthy();
    unmount();

    renderGate({ onLogin: async () => ({ ok: false, reason: "unenrolled" }) });
    await fillLogin();
    fireEvent.click(signIn());
    expect(await screen.findByText(/closed at your request/)).toBeTruthy();
  });

  it("el freno se explica con su propio mensaje", async () => {
    renderGate({
      onLogin: async () => ({ ok: false, reason: "throttled", retryAfterSeconds: 30 }),
    });
    await fillLogin();
    fireEvent.click(signIn());
    expect(await screen.findByText(/Too many attempts/)).toBeTruthy();
  });

  it("un backend caído se cuenta como avería, no como credencial mala", async () => {
    const onLogin = vi.fn(
      async (): Promise<LoginOutcome> => ({ ok: false, reason: "error" }),
    );
    renderGate({ onLogin });
    await fillLogin();
    fireEvent.click(signIn());
    // Se fija lo que **no** dice: acusar a la contraseña de una caída manda a
    // cambiarla, y eso es hacer perder el tiempo a quien no se ha equivocado.
    expect(await screen.findByText(/Is the server running\?/)).toBeTruthy();
    expect(screen.queryByText(/not right/)).toBeNull();
  });
});

describe("ProfileGate · solicitar acceso (V3.82)", () => {
  const openRequest = () =>
    fireEvent.click(screen.getByRole("button", { name: "Ask for access" }));
  const submitRequest = () =>
    screen.getByRole("button", { name: "Send request" });

  it("pide nombre, email y avatar: lo que la cuenta necesita para existir", () => {
    renderGate();
    openRequest();
    expect(screen.getByLabelText("Name or nickname")).toBeTruthy();
    expect(screen.getByLabelText("Email")).toBeTruthy();
    expect(screen.getByLabelText("Note (optional)")).toBeTruthy();
  });

  it("no manda una solicitud sin nombre", async () => {
    const onRequest = vi.fn();
    renderGate({ onRequest });
    openRequest();
    fireEvent.change(emailInput(), { target: { value: "ana@example.com" } });
    fireEvent.click(submitRequest());
    expect(onRequest).not.toHaveBeenCalled();
    expect(await screen.findByText("That name is not valid.")).toBeTruthy();
  });

  it("no manda una solicitud sin un email con forma", async () => {
    // Sin email no hay forma de mandar la invitación: enviarla sería prometer un
    // correo que no puede salir.
    const onRequest = vi.fn();
    renderGate({ onRequest });
    openRequest();
    fireEvent.change(screen.getByLabelText("Name or nickname"), {
      target: { value: "Ana" },
    });
    fireEvent.change(emailInput(), { target: { value: "ana" } });
    fireEvent.click(submitRequest());
    expect(onRequest).not.toHaveBeenCalled();
    expect(await screen.findByText(/does not look valid/)).toBeTruthy();
  });

  it("manda nombre, email y avatar y cuenta que está enviada", async () => {
    const onRequest = vi.fn().mockResolvedValue({ ok: true, request: PEDIDA });
    renderGate({ onRequest });
    openRequest();
    fireEvent.change(screen.getByLabelText("Name or nickname"), {
      target: { value: "  Ana  " },
    });
    fireEvent.change(emailInput(), { target: { value: "ana@example.com" } });
    fireEvent.click(submitRequest());

    // El nombre se manda tal cual se tecleó: **quien lo recorta es el cliente de
    // la API** (`requestProfile`), que es el único sitio donde el nombre se
    // normaliza. Recortarlo también aquí sería tener la regla dos veces.
    expect(onRequest).toHaveBeenCalledWith("  Ana  ", "ana@example.com", {}, "");
    expect(await screen.findByText(/Request sent/)).toBeTruthy();
  });

  it("un email que ya tiene cuenta se explica con la salida a mano", async () => {
    renderGate({
      onRequest: async () => ({ ok: false, reason: "email-taken" }),
    });
    openRequest();
    fireEvent.change(screen.getByLabelText("Name or nickname"), {
      target: { value: "Ana" },
    });
    fireEvent.change(emailInput(), { target: { value: "ana@example.com" } });
    fireEvent.click(submitRequest());
    expect(
      await screen.findByText(/already has an account/),
    ).toBeTruthy();
  });

  it("la cola llena y la caída del servidor dicen cosas distintas", async () => {
    const { unmount } = renderGate({
      onRequest: async () => ({ ok: false, reason: "full" }),
    });
    openRequest();
    fireEvent.change(screen.getByLabelText("Name or nickname"), {
      target: { value: "Ana" },
    });
    fireEvent.change(emailInput(), { target: { value: "ana@example.com" } });
    fireEvent.click(submitRequest());
    expect(await screen.findByText(/too many pending requests/i)).toBeTruthy();
    unmount();

    renderGate({ onRequest: async () => ({ ok: false, reason: "offline" }) });
    openRequest();
    fireEvent.change(screen.getByLabelText("Name or nickname"), {
      target: { value: "Ana" },
    });
    fireEvent.change(emailInput(), { target: { value: "ana@example.com" } });
    fireEvent.click(submitRequest());
    expect(await screen.findByText(/Could not send the request/)).toBeTruthy();
  });

  it("se puede volver a la entrada sin quedarse atrapado", () => {
    renderGate();
    openRequest();
    fireEvent.click(screen.getByRole("button", { name: "Back to sign in" }));
    expect(signIn()).toBeTruthy();
  });
});

describe("ProfileGate · recuperar la contraseña (V3.82)", () => {
  const openForgot = () =>
    fireEvent.click(screen.getByRole("button", { name: "I forgot my password" }));

  it("deja de ser informativo: ahora pide el email de verdad", () => {
    // Hasta V3.81 el botón solo **explicaba** que la restablecía el webmaster.
    renderGate();
    openForgot();
    expect(emailInput()).toBeTruthy();
    expect(screen.getByRole("button", { name: "Send link" })).toBeTruthy();
  });

  it("manda el email y no promete que exista la cuenta", async () => {
    const onForgot = vi.fn().mockResolvedValue({ sent: true });
    renderGate({ onForgot });
    openForgot();
    fireEvent.change(emailInput(), { target: { value: "ana@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send link" }));

    expect(onForgot).toHaveBeenCalledWith("ana@example.com");
    // «Si ese email tiene una cuenta…»: el backend responde igual siempre para no
    // revelar quién está registrado, y el texto no puede decir más que el backend.
    expect(await screen.findByText(/If that email has an account/)).toBeTruthy();
  });

  it("sin SMTP dice que no se ha enviado nada en vez de fingirlo", async () => {
    renderGate({ onForgot: async () => ({ sent: false }) });
    openForgot();
    fireEvent.change(emailInput(), { target: { value: "ana@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send link" }));
    expect(await screen.findByText(/Nothing was sent/)).toBeTruthy();
  });
});

describe("ProfileGate · la sesión que no se pudo comprobar (V3.80.2)", () => {
  it("no confunde «no hay sesión» con «no se pudo comprobar»", () => {
    renderGate({ loadFailed: true });
    expect(screen.getByRole("alert")).toBeTruthy();
    // La mentira que dejaba al alumno sin salida era ofrecer entrar cuando lo que
    // había era un fallo de lectura.
    expect(screen.queryByLabelText("Email")).toBeNull();
  });

  it("ofrece reintentar en el sitio y avisa al hacerlo", () => {
    const onRetry = vi.fn();
    renderGate({ loadFailed: true, onRetry });
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("con la sesión comprobada bien, el aviso no aparece", () => {
    renderGate();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(emailInput()).toBeTruthy();
  });
});


