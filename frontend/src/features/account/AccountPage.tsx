import type { ReactNode } from "react";
import { useI18n } from "../../hooks/useI18n";

interface AccountPageProps {
  title: string;
  /** Frase que explica para qué sirve la página. Opcional. */
  prompt?: string;
  children: ReactNode;
}

/**
 * Páginas de cuenta que llegan **por un enlace de correo** (V3.82): activar,
 * restablecer y confirmar el email.
 *
 * Las tres se pintan fuera del armazón de la app y por encima de la puerta de
 * entrada, porque quien las abre puede no tener sesión, estar en **otro**
 * navegador (el móvil) y no haber abierto nunca la aplicación en ese equipo. No
 * llevan cabecera ni navegación: son una parada, no un destino. Por eso el
 * armazón es uno solo y vive aquí: lo que comparten es el fondo, la tarjeta
 * centrada, el logotipo, el título y el pie; lo único distinto es el cuerpo.
 *
 * El pie (`account.localNote`) no es decoración: en este equipo puede **no haber
 * correo configurado**, y entonces el enlace no ha salido de aquí sino que se
 * entrega a mano. Decirlo es lo que evita que alguien espere un correo que nunca
 * va a llegar.
 */
export function AccountPage({ title, prompt, children }: AccountPageProps) {
  const { t } = useI18n();
  return (
    <div className="dialog-backdrop" role="presentation">
      <div
        className="dialog dialog--profile-gate"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="dialog-body">
          <div className="flex flex-col items-center gap-2 text-center">
            <span className="grid size-16 place-items-center rounded-2xl bg-gradient-to-br from-primary to-[var(--color-accent-2)] text-2xl font-bold text-primary-foreground shadow-sm">
              EN
            </span>
            <h2 className="mt-2 text-xl font-bold tracking-tight text-foreground">
              {title}
            </h2>
            {prompt && (
              <p className="text-sm leading-relaxed text-muted-foreground">
                {prompt}
              </p>
            )}
          </div>
          {children}
          <p className="text-xs leading-relaxed text-muted-foreground">
            {t("account.localNote")}
          </p>
        </div>
      </div>
    </div>
  );
}

interface AccountNoticeProps {
  /**
   * `error` = algo no salió (rol `alert`); sin tono = información neutra (rol
   * `status`). El rol no es decorativo: un error tiene que **interrumpir** al
   * lector de pantalla y un «confirmando…» no.
   */
  tone?: "error" | "info";
  children: ReactNode;
}

/**
 * Aviso dentro de una página de cuenta.
 *
 * Existe para que el tono y el rol se decidan en un sitio. La regla que protege
 * es la del fichero de tests: estas páginas **no prometen lo que no ha pasado**,
 * así que un fallo nunca debe pintarse con el mismo aspecto (ni el mismo rol)
 * que un éxito.
 */
export function AccountNotice({ tone = "info", children }: AccountNoticeProps) {
  const error = tone === "error";
  return (
    <p
      className={
        error
          ? "dialog-error"
          : "rounded-md border border-border bg-muted px-3 py-2 text-sm leading-relaxed text-muted-foreground"
      }
      role={error ? "alert" : "status"}
    >
      {children}
    </p>
  );
}
