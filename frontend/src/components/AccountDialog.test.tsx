// @vitest-environment jsdom
/**
 * Diálogo de cuenta (V3.81): contraseña, email, baja y salir.
 *
 * Lo que se fija aquí son las **decisiones**, no los campos: que la baja sea en dos
 * pasos y exija la contraseña, que el diálogo diga la verdad que promete la app
 * (darse de baja **no** borra los datos), que no se mande a la API nada con mala
 * forma (el servidor lo rechazaría), que una cuenta heredada sin credencial pueda
 * ponerse la suya sin que se le pida una «actual» que no existe, y que en modo
 * forzado (contraseña temporal) no haya salida salvo cambiarla.
 *
 * La lógica de red vive en `useChat`, así que aquí los desenlaces llegan por props:
 * lo que se prueba es el contrato de la vista.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { I18nProvider } from "../hooks/useI18n";
import type { AccountActionOutcome } from "../hooks/useChat";
import type { User } from "../types/api";
import { AccountDialog } from "./AccountDialog";

function user(over: Partial<User> = {}): User {
  return {
    id: "a",
    name: "Ana",
    avatar_color: "",
    avatar_emoji: "",
    avatar_image: "",
    email: "ana@ejemplo.es",
    email_verified: false,
    has_password: true,
    created_at: "2026-01-01T00:00:00Z",
    ...over,
  };
}

const OK = async (): Promise<AccountActionOutcome> => ({ ok: true, user: user() });

afterEach(cleanup);

function renderDialog(props: Partial<Parameters<typeof AccountDialog>[0]> = {}) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      <AccountDialog
        user={user()}
        onClose={() => {}}
        onChangePassword={OK}
        onChangeEmail={OK}
        onResendVerification={async () => true}
        onUnenroll={OK}
        onSignOut={() => {}}
        {...props}
      />
    </I18nProvider>,
  );
}

/** La sección cuyo rótulo es `label` (el `.field`), para no confundir sus campos. */
function field(label: string): HTMLElement {
  const span = screen
    .getAllByText(label)
    .find((el) => el.classList.contains("field-label"));
  if (!span) throw new Error(`no hay sección «${label}» en el diálogo`);
  return span.closest(".field") as HTMLElement;
}

function type(el: HTMLElement, value: string) {
  fireEvent.change(el, { target: { value } });
}

describe("AccountDialog · montaje", () => {
  it("cuelga de document.body, no del árbol que lo abre", () => {
    renderDialog();
    expect(screen.getByRole("dialog").parentElement?.parentElement).toBe(
      document.body,
    );
  });

  it("declara lo que la baja no hace: no borra los datos", () => {
    renderDialog();
    expect(screen.getByText(/does not erase your data/)).toBeTruthy();
  });
});

describe("AccountDialog · cambio de contraseña", () => {
  it("no manda una contraseña sin forma", async () => {
    const onChangePassword = vi.fn(OK);
    renderDialog({ onChangePassword });
    const section = field("Change password");
    type(within(section).getByLabelText("Current password"), "vieja-larga");
    type(within(section).getByLabelText("New password"), "corta");
    fireEvent.click(within(section).getByRole("button", { name: "Change password" }));
    expect(
      await screen.findByText("The password needs at least 8 characters."),
    ).toBeTruthy();
    expect(onChangePassword).not.toHaveBeenCalled();
  });

  it("no manda si la repetición no cuadra", async () => {
    const onChangePassword = vi.fn(OK);
    renderDialog({ onChangePassword });
    const section = field("Change password");
    type(within(section).getByLabelText("Current password"), "vieja-larga");
    type(within(section).getByLabelText("New password"), "nueva-larga-clave");
    type(within(section).getByLabelText("Repeat the password"), "otra-cosa-larga");
    fireEvent.click(within(section).getByRole("button", { name: "Change password" }));
    expect(
      await screen.findByText("The two passwords do not match."),
    ).toBeTruthy();
    expect(onChangePassword).not.toHaveBeenCalled();
  });

  it("con la actual y la nueva, guarda y lo dice", async () => {
    const onChangePassword = vi.fn(OK);
    renderDialog({ onChangePassword });
    const section = field("Change password");
    type(within(section).getByLabelText("Current password"), "vieja-larga");
    type(within(section).getByLabelText("New password"), "nueva-larga-clave");
    type(
      within(section).getByLabelText("Repeat the password"),
      "nueva-larga-clave",
    );
    fireEvent.click(within(section).getByRole("button", { name: "Change password" }));
    expect(await screen.findByText("Saved.")).toBeTruthy();
    expect(onChangePassword).toHaveBeenCalledWith(
      "vieja-larga",
      "nueva-larga-clave",
    );
  });

  it("si la actual no cuadra, lo dice en vez de quedarse mudo", async () => {
    const onChangePassword = vi.fn(
      async (): Promise<AccountActionOutcome> => ({
        ok: false,
        reason: "password-invalid",
      }),
    );
    renderDialog({ onChangePassword });
    const section = field("Change password");
    type(within(section).getByLabelText("Current password"), "no-es-esta");
    type(within(section).getByLabelText("New password"), "nueva-larga-clave");
    type(
      within(section).getByLabelText("Repeat the password"),
      "nueva-larga-clave",
    );
    fireEvent.click(within(section).getByRole("button", { name: "Change password" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("That password is not right.");
  });

  it("una cuenta sin credencial la pone por primera vez, sin «actual»", async () => {
    const onChangePassword = vi.fn(OK);
    renderDialog({ user: user({ has_password: false }), onChangePassword });
    const section = field("Change password");
    expect(within(section).queryByLabelText("Current password")).toBeNull();
    type(within(section).getByLabelText("New password"), "nueva-larga-clave");
    type(
      within(section).getByLabelText("Repeat the password"),
      "nueva-larga-clave",
    );
    fireEvent.click(within(section).getByRole("button", { name: "Change password" }));
    await screen.findByText("Saved.");
    expect(onChangePassword).toHaveBeenCalledWith(null, "nueva-larga-clave");
  });
});

describe("AccountDialog · contraseña temporal (modo forzado)", () => {
  it("no se puede cerrar: ni aspa, ni Escape, ni las otras secciones", () => {
    const onClose = vi.fn();
    renderDialog({ forced: true, onClose });
    expect(screen.queryByLabelText("Close")).toBeNull();
    expect(screen.queryByRole("button", { name: "Close" })).toBeNull();
    expect(screen.queryByText("Change email")).toBeNull();
    expect(screen.queryByText("Delete my account")).toBeNull();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
  });

  it("exige la contraseña actual antes de aceptar la nueva", async () => {
    const onChangePassword = vi.fn(OK);
    renderDialog({ forced: true, onChangePassword });
    const section = field("Change your password");
    type(within(section).getByLabelText("New password"), "nueva-larga-clave");
    type(
      within(section).getByLabelText("Repeat the password"),
      "nueva-larga-clave",
    );
    fireEvent.click(within(section).getByRole("button", { name: "Change password" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Your password is required.");
    expect(onChangePassword).not.toHaveBeenCalled();
  });

  it("cambiarla es la salida: al guardar, cierra", async () => {
    const onClose = vi.fn();
    renderDialog({ forced: true, onClose });
    const section = field("Change your password");
    type(within(section).getByLabelText("Current password"), "temporal-12345");
    type(within(section).getByLabelText("New password"), "nueva-larga-clave");
    type(
      within(section).getByLabelText("Repeat the password"),
      "nueva-larga-clave",
    );
    fireEvent.click(within(section).getByRole("button", { name: "Change password" }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});

describe("AccountDialog · email", () => {
  it("no manda un email con mala forma", async () => {
    const onChangeEmail = vi.fn(OK);
    renderDialog({ onChangeEmail });
    const section = field("Change email");
    type(within(section).getByLabelText("Current password"), "vieja-larga");
    type(within(section).getByLabelText("New email"), "ana-arroba-ejemplo");
    fireEvent.click(within(section).getByRole("button", { name: "Save" }));
    expect(await screen.findByText("That email does not look valid.")).toBeTruthy();
    expect(onChangeEmail).not.toHaveBeenCalled();
  });

  it("cambiar el email exige la contraseña, y no la inventa", async () => {
    const onChangeEmail = vi.fn(OK);
    renderDialog({ onChangeEmail });
    const section = field("Change email");
    type(within(section).getByLabelText("New email"), "otra@ejemplo.es");
    fireEvent.click(within(section).getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Your password is required.")).toBeTruthy();
    expect(onChangeEmail).not.toHaveBeenCalled();
  });

  it("el reenvío dice lo que ha pasado de verdad: enviado o sin correo", async () => {
    const { unmount } = renderDialog({
      onResendVerification: async () => true,
    });
    const section = field("Change email");
    fireEvent.click(
      within(section).getByRole("button", { name: "Resend verification" }),
    );
    expect(
      await screen.findByText("Verification link sent to your email."),
    ).toBeTruthy();
    unmount();

    renderDialog({ onResendVerification: async () => false });
    fireEvent.click(
      within(field("Change email")).getByRole("button", {
        name: "Resend verification",
      }),
    );
    expect(await screen.findByText(/no mail configured/)).toBeTruthy();
  });

  it("con el email ya verificado no se ofrece reenviar nada", () => {
    renderDialog({ user: user({ email_verified: true }) });
    expect(
      within(field("Change email")).queryByRole("button", {
        name: "Resend verification",
      }),
    ).toBeNull();
    expect(screen.getByText("Verified")).toBeTruthy();
  });
});

describe("AccountDialog · baja", () => {
  it("la baja es en dos pasos: el primer clic no da de baja a nadie", async () => {
    const onUnenroll = vi.fn(OK);
    renderDialog({ onUnenroll });
    const section = field("Delete my account");
    fireEvent.click(within(section).getByRole("button", { name: "Delete my account" }));
    expect(onUnenroll).not.toHaveBeenCalled();
    // Se abrió la confirmación: ahora hay salida («Cancel») y pide la contraseña.
    expect(within(section).getByRole("button", { name: "Cancel" })).toBeTruthy();
    expect(within(section).getByLabelText("Current password")).toBeTruthy();
  });

  it("confirmar sin contraseña no da de baja", async () => {
    const onUnenroll = vi.fn(OK);
    renderDialog({ onUnenroll });
    const section = field("Delete my account");
    fireEvent.click(within(section).getByRole("button", { name: "Delete my account" }));
    fireEvent.click(within(section).getByRole("button", { name: "Delete my account" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain(
      "Your password is required.",
    );
    expect(onUnenroll).not.toHaveBeenCalled();
  });

  it("confirmada con la contraseña, da de baja una sola vez", async () => {
    const onUnenroll = vi.fn(OK);
    renderDialog({ onUnenroll });
    const section = field("Delete my account");
    fireEvent.click(within(section).getByRole("button", { name: "Delete my account" }));
    type(within(section).getByLabelText("Current password"), "vieja-larga");
    fireEvent.click(within(section).getByRole("button", { name: "Delete my account" }));
    await waitFor(() => expect(onUnenroll).toHaveBeenCalledTimes(1));
    expect(onUnenroll).toHaveBeenCalledWith("vieja-larga");
  });

  it("si el servidor dice que la contraseña no es, lo cuenta", async () => {
    const onUnenroll = vi.fn(
      async (): Promise<AccountActionOutcome> => ({
        ok: false,
        reason: "password-invalid",
      }),
    );
    renderDialog({ onUnenroll });
    const section = field("Delete my account");
    fireEvent.click(within(section).getByRole("button", { name: "Delete my account" }));
    type(within(section).getByLabelText("Current password"), "no-es-esta");
    fireEvent.click(within(section).getByRole("button", { name: "Delete my account" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("That password is not right.");
  });

  it("cancelar cierra la confirmación sin llamar a nadie", () => {
    const onUnenroll = vi.fn(OK);
    renderDialog({ onUnenroll });
    const section = field("Delete my account");
    fireEvent.click(within(section).getByRole("button", { name: "Delete my account" }));
    fireEvent.click(within(section).getByRole("button", { name: "Cancel" }));
    expect(within(section).queryByRole("button", { name: "Cancel" })).toBeNull();
    expect(onUnenroll).not.toHaveBeenCalled();
  });
});

describe("AccountDialog · salir", () => {
  it("«Salir» cierra la sesión (y existe de verdad)", () => {
    const onSignOut = vi.fn();
    renderDialog({ onSignOut });
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(onSignOut).toHaveBeenCalledTimes(1);
  });

  it("Esc cierra el diálogo normal, pero no la sesión", () => {
    const onClose = vi.fn();
    const onSignOut = vi.fn();
    renderDialog({ onClose, onSignOut });
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onSignOut).not.toHaveBeenCalled();
  });
});
