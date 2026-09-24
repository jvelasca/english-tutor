// @vitest-environment jsdom
/**
 * Páginas de cuenta que llegan por correo (V3.82): activar, restablecer y
 * verificar.
 *
 * Las tres comparten una regla que es fácil de romper: **no prometen lo que no
 * ha pasado**. Un «ya está» pintado por defecto convertiría un enlace caducado en
 * una confirmación falsa, y la persona se quedaría creyendo que su cuenta está
 * lista cuando no lo está. Por eso el caso que más se fija aquí es el fallo.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { StrictMode } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { I18nProvider } from "../../hooks/useI18n";
import { activateAccount, ActivationError, resetPassword, ResetError, verifyEmail } from "../../api/session";
import { AccountActivate } from "./AccountActivate";
import { AccountReset } from "./AccountReset";
import { AccountVerify } from "./AccountVerify";

vi.mock("../../api/session", async (importOriginal) => {
  // Se conserva el módulo real: `ActivationError`/`ResetError` tienen que ser la
  // misma clase que usan las páginas, o su `instanceof` no reconocería nada.
  const actual = await importOriginal<typeof import("../../api/session")>();
  return {
    ...actual,
    activateAccount: vi.fn(),
    resetPassword: vi.fn(),
    verifyEmail: vi.fn(),
  };
});

const activateMock = vi.mocked(activateAccount);
const resetMock = vi.mocked(resetPassword);
const verifyMock = vi.mocked(verifyEmail);

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

function renderPage(node: React.ReactElement) {
  return render(<I18nProvider lang="en" setLang={() => {}}>{node}</I18nProvider>);
}

/**
 * Monta con `StrictMode`, que es como corre la app de verdad en desarrollo
 * (`main.tsx`).
 *
 * Hace falta porque el doble montaje de React no es un detalle de laboratorio:
 * ya se llevó por delante la página de verificación —se quedaba en
 * «Confirming…» **para siempre**—, y el test sin `StrictMode` no lo vio porque
 * montaba una sola vez. Una suite que no reproduce cómo arranca la app no
 * vigila el bug que sí ocurre.
 */
function renderStrict(node: React.ReactElement) {
  return render(
    <StrictMode>
      <I18nProvider lang="en" setLang={() => {}}>{node}</I18nProvider>
    </StrictMode>,
  );
}

function fillPassword(password = "caballo-bateria") {
  fireEvent.change(screen.getByLabelText("New password"), {
    target: { value: password },
  });
  fireEvent.change(screen.getByLabelText("Repeat the password"), {
    target: { value: password },
  });
}

describe("AccountActivate", () => {
  it("sin token en el enlace lo dice en vez de pedir una contraseña para nada", () => {
    renderPage(<AccountActivate token="" onDone={() => {}} />);
    expect(screen.getByRole("alert").textContent).toMatch(/no invitation/);
    expect(screen.queryByLabelText("New password")).toBeNull();
  });

  it("no manda nada con dos contraseñas distintas", () => {
    renderPage(<AccountActivate token="t" onDone={() => {}} />);
    fireEvent.change(screen.getByLabelText("New password"), {
      target: { value: "caballo-bateria" },
    });
    fireEvent.change(screen.getByLabelText("Repeat the password"), {
      target: { value: "caballo-bateriaX" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Activate my account" }));
    expect(activateMock).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toMatch(/do not match/);
  });

  it("con la contraseña elegida activa la cuenta y entra sola", async () => {
    // La sesión ya viene abierta del servidor: pedirla otra vez en la puerta
    // sería castigar a quien acaba de elegirla.
    activateMock.mockResolvedValue({ id: "a", name: "Ana", created_at: "" });
    const onDone = vi.fn();
    renderPage(<AccountActivate token="invitacion" onDone={onDone} />);

    fillPassword();
    fireEvent.click(screen.getByRole("button", { name: "Activate my account" }));

    await waitFor(() => expect(activateMock).toHaveBeenCalledWith("invitacion", "caballo-bateria"));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
  });

  it("una invitación caducada manda pedir otra, no acusa a la contraseña", async () => {
    activateMock.mockRejectedValue(new ActivationError("expired"));
    renderPage(<AccountActivate token="t" onDone={() => {}} />);

    fillPassword();
    fireEvent.click(screen.getByRole("button", { name: "Activate my account" }));

    expect(await screen.findByText(/has expired/)).toBeTruthy();
  });

  it("una invitación ya usada se distingue de una caducada", async () => {
    activateMock.mockRejectedValue(new ActivationError("invalid"));
    renderPage(<AccountActivate token="t" onDone={() => {}} />);

    fillPassword();
    fireEvent.click(screen.getByRole("button", { name: "Activate my account" }));

    expect(await screen.findByText(/not valid/)).toBeTruthy();
  });
});

describe("AccountReset", () => {
  it("sin token en el enlace lo dice en vez de pedir una contraseña para nada", () => {
    renderPage(<AccountReset token="" onDone={() => {}} />);
    expect(screen.getByRole("alert").textContent).toMatch(/no reset/);
  });

  it("con la contraseña nueva restablece y entra", async () => {
    resetMock.mockResolvedValue({ id: "a", name: "Ana", created_at: "" });
    const onDone = vi.fn();
    renderPage(<AccountReset token="del-correo" onDone={onDone} />);

    fillPassword("otra-clave-larga");
    fireEvent.click(screen.getByRole("button", { name: "Save password" }));

    await waitFor(() =>
      expect(resetMock).toHaveBeenCalledWith("del-correo", "otra-clave-larga"),
    );
    await waitFor(() => expect(onDone).toHaveBeenCalled());
  });

  it("un enlace gastado manda pedir otro", async () => {
    resetMock.mockRejectedValue(new ResetError("expired"));
    renderPage(<AccountReset token="t" onDone={() => {}} />);

    fillPassword();
    fireEvent.click(screen.getByRole("button", { name: "Save password" }));

    expect(await screen.findByText(/has expired/)).toBeTruthy();
  });
});

describe("AccountVerify", () => {
  it("canjea el token una sola vez aunque el componente se monte dos veces", async () => {
    // Con el doble montaje de React en desarrollo, sin la guarda el primer intento
    // gastaría el token y el segundo lo daría por inválido: el peor error posible
    // aquí es decir «no vale» de un enlace que sí valía.
    verifyMock.mockResolvedValue({ id: "a", name: "Ana", created_at: "" });
    renderPage(<AccountVerify token="abc" onDone={() => {}} />);

    await waitFor(() => expect(verifyMock).toHaveBeenCalledTimes(1));
    expect(verifyMock).toHaveBeenCalledWith("abc");
    expect(await screen.findByText(/is confirmed/)).toBeTruthy();
  });

  it("en modo estricto no se queda en «Confirming…» para siempre", async () => {
    // El bug real: la guarda del doble montaje dejaba pasar el segundo efecto
    // —el token ya estaba marcado como canjeado— y la bandera de «sigo vivo» del
    // primero descartaba la única respuesta que iba a llegar. Resultado: la
    // página de verificación se quedaba cargando eternamente en desarrollo, que
    // es exactamente donde se prueba a mano.
    verifyMock.mockResolvedValue({ id: "a", name: "Ana", created_at: "" });
    renderStrict(<AccountVerify token="abc" onDone={() => {}} />);

    expect(await screen.findByText(/is confirmed/)).toBeTruthy();
    expect(screen.queryByText(/Confirming/)).toBeNull();
    expect(verifyMock).toHaveBeenCalledTimes(1);
  });

  it("sin token no llama a la API y lo dice", async () => {
    renderPage(<AccountVerify token="" onDone={() => {}} />);
    expect(await screen.findByText(/no confirmation/)).toBeTruthy();
    expect(verifyMock).not.toHaveBeenCalled();
  });

  it("un token que no vale se cuenta como fallo, no como «confirmado»", async () => {
    verifyMock.mockRejectedValue(new Error("RESET"));
    renderPage(<AccountVerify token="viejo" onDone={() => {}} />);

    expect(await screen.findByText(/not valid or has expired/)).toBeTruthy();
    expect(screen.queryByText(/is confirmed/)).toBeNull();
  });

  it("deja volver a la app cuando ha terminado", async () => {
    verifyMock.mockResolvedValue({ id: "a", name: "Ana", created_at: "" });
    const onDone = vi.fn();
    renderPage(<AccountVerify token="abc" onDone={onDone} />);

    const goHome = await screen.findByRole("button", { name: "Go to the app" });
    fireEvent.click(goHome);
    expect(onDone).toHaveBeenCalled();
  });
});
