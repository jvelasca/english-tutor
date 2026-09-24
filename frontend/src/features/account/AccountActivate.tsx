import { activateAccount, ActivationError } from "../../api/session";
import { useI18n } from "../../hooks/useI18n";
import { AccountNotice, AccountPage } from "./AccountPage";
import { NewPasswordForm } from "./NewPasswordForm";

interface AccountActivateProps {
  /** Token de la invitación, leído del enlace del correo. */
  token: string;
  /** Se activó bien: la sesión ya está abierta en el servidor. */
  onDone: () => void;
}

/**
 * Página de **activación** (V3.82): donde el autorizado elige su contraseña.
 *
 * Es el paso que convierte una solicitud aprobada en una cuenta usable, y lo
 * hace la propia persona: el webmaster no inventa ni conoce ninguna contraseña.
 * Pulsar el enlace prueba que el correo es suyo, así que al terminar la cuenta
 * queda además con el email **verificado**.
 *
 * No pide sesión previa: el enlace puede abrirse en otro navegador, y lo que
 * autoriza no es una cookie sino un token de un solo uso con caducidad. Al
 * terminar, el servidor deja la sesión abierta y la app entra sola: quien acaba
 * de elegir su contraseña no tiene que volver a escribirla.
 */
export function AccountActivate({ token, onDone }: AccountActivateProps) {
  const { t } = useI18n();

  if (!token) {
    return (
      <AccountPage title={t("activate.title")}>
        <AccountNotice tone="error">{t("activate.missing")}</AccountNotice>
      </AccountPage>
    );
  }

  return (
    <AccountPage title={t("activate.title")} prompt={t("activate.prompt")}>
      <NewPasswordForm
        submitLabel={t("activate.submit")}
        onSubmit={async (password) => {
          try {
            await activateAccount(token, password);
          } catch (err) {
            return err instanceof ActivationError
              ? activationErrorKey(err)
              : "account.error";
          }
          // La sesión ya está abierta: se adopta y se entra en la app.
          onDone();
          return null;
        }}
      />
    </AccountPage>
  );
}

/** Qué decir ante cada desenlace fallido de la activación. */
export function activationErrorKey(err: ActivationError): string {
  switch (err.reason) {
    case "expired":
      return "activate.expired";
    case "invalid":
      return "activate.invalid";
    case "password-format":
      return "account.passwordFormat";
    default:
      return "account.error";
  }
}
