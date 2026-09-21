// @vitest-environment jsdom
/**
 * Puerta de perfil con PIN (V3.76, Fase 3 del P0 de identidad).
 *
 * Lo que se fija aquí no es «hay un campo de PIN», sino que la puerta **no
 * promete lo que no puede cumplir**: no deja enviar un PIN con mala forma (el
 * backend lo rechazaría con 400), no se queda muda cuando el PIN no cuadra, y
 * ofrece volver en vez de atrapar al alumno en la pantalla.
 *
 * Quién decide que hace falta PIN es el servidor: estos tests reciben el estado
 * ya resuelto por props (que es como se lo pasa `useChat`), porque lo que se
 * prueba es el contrato de la vista.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { I18nProvider } from "../hooks/useI18n";
import type { ProfileRequest, User } from "../types/api";
import { ProfileGate } from "./ProfileGate";

function user(id: string, name: string, hasPin = false): User {
  return {
    id,
    name,
    avatar_color: "",
    avatar_emoji: "",
    avatar_image: "",
    has_pin: hasPin,
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

describe("ProfileGate · lista de perfiles", () => {
  it("elegir un perfil avisa con su id", () => {
    const onSelect = vi.fn();
    renderGate({ onSelect });
    fireEvent.click(screen.getByRole("option", { name: /Beto/ }));
    expect(onSelect).toHaveBeenCalledWith("b");
  });

  it("sin paso de PIN no aparece el campo", () => {
    renderGate();
    expect(screen.queryByLabelText("PIN")).toBeNull();
  });
});

describe("ProfileGate · paso de PIN (V3.76)", () => {
  const pinInput = () => screen.getByLabelText("PIN") as HTMLInputElement;
  const submit = () => screen.getByRole("button", { name: "Continue" });

  it("pide el PIN del perfil que lo tiene", () => {
    renderGate({ pinUser: ANA });
    expect(screen.getByText("Ana")).toBeTruthy();
    expect(pinInput().type).toBe("password");
    // El formulario de «crear perfil» no se ofrece mientras se teclea el PIN:
    // no son dos cosas que se puedan hacer a la vez.
    expect(screen.queryByLabelText("Name")).toBeNull();
  });

  it("no deja enviar hasta que el PIN tiene 4 dígitos", () => {
    renderGate({ pinUser: ANA, onSubmitPin: async () => false });
    expect((submit() as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(pinInput(), { target: { value: "123" } });
    expect((submit() as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(pinInput(), { target: { value: "1234" } });
    expect((submit() as HTMLButtonElement).disabled).toBe(false);
  });

  it("solo acepta dígitos y como mucho 6", () => {
    renderGate({ pinUser: ANA });
    fireEvent.change(pinInput(), { target: { value: "12a34b5678" } });
    expect(pinInput().value).toBe("123456");
  });

  it("envía el PIN del perfil correcto", async () => {
    const onSubmitPin = vi.fn().mockResolvedValue(true);
    renderGate({ pinUser: ANA, onSubmitPin });
    fireEvent.change(pinInput(), { target: { value: "4821" } });
    fireEvent.click(submit());
    expect(onSubmitPin).toHaveBeenCalledWith("a", "4821");
  });

  it("un PIN incorrecto no se queda en silencio", () => {
    renderGate({ pinUser: ANA, pinFeedback: "pin-invalid" });
    expect(screen.getByText("That PIN is not right.")).toBeTruthy();
  });

  it("el freno se explica con su propio mensaje", () => {
    renderGate({ pinUser: ANA, pinFeedback: "pin-throttled" });
    expect(
      screen.getByText("Too many attempts. Wait a moment and try again."),
    ).toBeTruthy();
  });

  it("se puede volver sin quedarse atrapado en el paso de PIN", () => {
    const onCancelPin = vi.fn();
    renderGate({ pinUser: ANA, onCancelPin });
    fireEvent.click(screen.getByRole("button", { name: "Back to profiles" }));
    expect(onCancelPin).toHaveBeenCalled();
  });
});

describe("ProfileGate · pedir un perfil (V3.77)", () => {
  const nameInput = () => screen.getByLabelText("Name") as HTMLInputElement;
  const submit = () => screen.getByRole("button", { name: "Ask for a profile" });

  it("no ofrece «crear»: la app pide, no crea", () => {
    // La ruta que creaba perfiles desde el navegador ya no es la del alumno
    // (el backend la cierra fuera del equipo), así que la puerta no la promete.
    renderGate();
    expect(screen.queryByRole("button", { name: "Create profile" })).toBeNull();
    expect(submit()).toBeTruthy();
  });

  it("manda el nombre recortado y cuenta que la solicitud está enviada", async () => {
    const onRequest = vi.fn().mockResolvedValue({ ok: true, request: PEDIDA });
    renderGate({ onRequest });

    fireEvent.change(nameInput(), { target: { value: "  Ana  " } });
    fireEvent.click(submit());

    expect(onRequest).toHaveBeenCalledWith("Ana");
    expect(await screen.findByText(/Request sent/)).toBeTruthy();
    // Y no desaparece: no hay perfil al que entrar todavía, así que la puerta se
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
    expect(
      await screen.findByText(/too many pending requests/i),
    ).toBeTruthy();
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
