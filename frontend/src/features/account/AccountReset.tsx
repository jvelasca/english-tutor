import { resetPassword, ResetError } from "../../api/session";
import { useI18n } from "../../hooks/useI18n";
import { AccountNotice, AccountPage } from "./AccountPage";
import { NewPasswordForm } from "./NewPasswordForm";

interface AccountResetProps {
  /** Token del enlace de restablecimiento. */
  token: string;
  /** Se cambió bien: la sesión ya está abierta en el servidor. */
  onDone: () => void;
}

/**
 * Página de **restablecimiento** (V3.82): contraseña nueva desde el enlace del
 * correo.
 *
 * El token es de un solo uso y caduca en una hora. Al guardar, el backend sube la
 * época de autenticación, así que **las demás sesiones abiertas de esa cuenta
 * mueren**: si alguien había entrado con la contraseña vieja, se queda fuera. Es
 * justo lo que se quiere de un «me han cambiado la contraseña».
 */
export function AccountReset({ token, onDone }: AccountResetProps) {
  const { t } = useI18n();

  if (!token) {
    return (
      <AccountPage title={t("reset.title")}>
        <AccountNotice tone="error">{t("reset.missing")}</AccountNotice>
      </AccountPage>
    );
  }

  return (
    <AccountPage title={t("reset.title")} prompt={t("reset.prompt")}>
      <NewPasswordForm
        submitLabel={t("reset.submit")}
        onSubmit={async (password) => {
          try {
            await resetPassword(token, password);
          } catch (err) {
            return err instanceof ResetError ? resetErrorKey(err) : "account.error";
          }
          // La sesión ya está abierta con la contraseña nueva.
          onDone();
          return null;
        }}
      />
    </AccountPage>
  );
}

/** Qué decir ante cada desenlace fallido del restablecimiento. */
export function resetErrorKey(err: ResetError): string {
  switch (err.reason) {
    case "expired":
      return "reset.expired";
    case "invalid":
      return "reset.invalid";
    case "password-format":
      return "account.passwordFormat";
    default:
      return "account.error";
  }
}
