import { useEffect, useRef, useState } from "react";
import { verifyEmail } from "../../api/session";
import { useI18n } from "../../hooks/useI18n";
import { AccountNotice, AccountPage } from "./AccountPage";

interface AccountVerifyProps {
  /** Token del enlace de confirmación. */
  token: string;
  /** Volver a la app (o a la puerta de entrada). */
  onDone: () => void;
}

type VerifyState = "working" | "ok" | "invalid";

/**
 * Página de **verificación del email** (V3.82).
 *
 * Existía el enlace en el correo desde V3.81, pero la ruta `/#/cuenta/verificar`
 * no existía en el frontend: pulsarlo caía en Inicio y no confirmaba nada. Esta
 * es esa mitad que faltaba.
 *
 * No pide sesión —el enlace puede abrirse en otro navegador— y **no** es
 * idempotente por accidente: si el token ya se canjeó, la API responde error y la
 * página lo dice en vez de fingir un «confirmado» que no ocurrió.
 */
export function AccountVerify({ token, onDone }: AccountVerifyProps) {
  const { t } = useI18n();
  const [state, setState] = useState<VerifyState>(token ? "working" : "invalid");
  // Guarda contra el doble montaje de desarrollo (StrictMode): sin ella, el
  // primer intento gastaría el token y el segundo lo daría por inválido, que es
  // el peor error posible aquí. Se guarda **qué token** se canjeó, no un simple
  // «ya empecé», para que cambiar de enlace siga canjeando el nuevo.
  const startedRef = useRef<string | null>(null);

  useEffect(() => {
    if (!token || startedRef.current === token) return;
    startedRef.current = token;
    // El resultado se aplica **sin** bandera de «sigo vivo», y es deliberado: en
    // el doble montaje de desarrollo el primer efecto se limpia y el segundo no
    // vuelve a preguntar —el token es de un solo uso—, así que descartar la
    // respuesta dejaría la página diciendo «Confirmando…» para siempre. Esa
    // bandera, que parece prudente, es justo lo que rompía el caso real, y solo
    // se vio al abrir la página en un navegador de verdad.
    void verifyEmail(token)
      .then(() => setState("ok"))
      .catch(() => setState("invalid"));
  }, [token]);

  return (
    <AccountPage title={t("verify.title")}>
      {state === "working" && <AccountNotice>{t("verify.working")}</AccountNotice>}
      {state === "ok" && <AccountNotice>{t("verify.ok")}</AccountNotice>}
      {state === "invalid" && (
        <AccountNotice tone="error">
          {token ? t("verify.invalid") : t("verify.missing")}
        </AccountNotice>
      )}
      {state !== "working" && (
        <button type="button" className="dialog-primary" onClick={onDone}>
          {t("verify.goHome")}
        </button>
      )}
    </AccountPage>
  );
}
