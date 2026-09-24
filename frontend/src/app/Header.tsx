import { useI18n } from "../hooks/useI18n";
import type { HandsFreeStatus } from "../hooks/useHandsFree";
import type { MicUnavailableReason } from "../utils/browserCapabilities";
import type { User } from "../types/api";
import type { UserPatch } from "../api/users";
import type { ProfileRequestOutcome } from "../api/profileRequests";
import type { Route } from "./routes";
import { Navigation } from "./Navigation";
import { ConnectionIndicator } from "../components/ConnectionIndicator";
import { HandsFreeToggle } from "../components/HandsFreeToggle";
import { UserMenu } from "../components/UserMenu";
import { GearIcon, HelpIcon, TrendIcon } from "../components/Icons";

interface HeaderProps {
  route: Route;
  onNavigate: (route: Route) => void;
  /**
   * V3.82: la cuenta de la sesión, o `null` mientras no hay ninguna. Ya no es
   * una lista: el menú dejó de ser un selector de usuarios.
   */
  user: User | null;
  onEditUser: (id: string, patch: UserPatch) => Promise<User | null>;
  /** V3.77: la cuenta de la sesión pide su baja (la resuelve el webmaster). */
  onRequestDeleteUser?: (note: string) => Promise<ProfileRequestOutcome>;
  /** V3.81: abre el diálogo de cuenta (contraseña, email, verificación, baja, Salir). */
  onOpenAccount?: () => void;
  handsFreeEnabled: boolean;
  handsFreeStatus: HandsFreeStatus;
  handsFreeMicError: MicUnavailableReason | null;
  onToggleHandsFree: () => void;
  onOpenSettings: () => void;
  /**
   * V3.75.3: abre el análisis de evolución (`/analisis`). Es una ruta auxiliar,
   * no un destino de navegación: por eso vive aquí, junto al usuario, y no como
   * píldora.
   */
  onOpenAnalysis: () => void;
}

export function Header({
  route,
  onNavigate,
  user,
  onEditUser,
  onRequestDeleteUser,
  onOpenAccount,
  handsFreeEnabled,
  handsFreeStatus,
  handsFreeMicError,
  onToggleHandsFree,
  onOpenSettings,
  onOpenAnalysis,
}: HeaderProps) {
  const { t } = useI18n();
  return (
    <header className="sticky top-0 z-40 flex items-center gap-4 border-b border-border bg-background/80 px-4 py-2.5 backdrop-blur-xl">
      <div className="flex min-w-0 items-center gap-2.5">
        <button
          type="button"
          onClick={() => onNavigate("home")}
          aria-label={t("header.goHome")}
          className="group flex items-center gap-3 text-left"
        >
          <span className="grid size-10 place-items-center rounded-xl bg-gradient-to-br from-primary to-[var(--color-accent-2)] text-sm font-bold text-primary-foreground shadow-sm transition-transform group-hover:scale-[1.04]">
            EN
          </span>
          <span className="hidden min-w-0 flex-col sm:flex">
            <span className="text-lg leading-tight font-bold tracking-tight text-foreground transition-colors group-hover:text-primary">
              English Tutor
            </span>
            <span className="text-xs text-muted-foreground">{t("brand.subtitle")}</span>
          </span>
        </button>
        {/* V3.38.1: estado de conexión integrado en la cabecera (sustituye a la
            barra inferior); visible también en móvil, fuera del bloque sm:flex. */}
        <ConnectionIndicator />
      </div>

      {/* V3.38.1: con el 4.º destino (diccionario) las píldoras no caben (ni en
          español) sin invadir los botones de acción por debajo de 1280px. Se
          muestran desde `xl` y hasta entonces manda la bottom-nav (táctil);
          `overflow-x-auto` queda como red de seguridad (el centrado con
          `mx-auto` mantiene el inicio accesible si hubiera scroll). */}
      <div className="hidden min-w-0 flex-1 xl:flex xl:overflow-x-auto">
        <Navigation route={route} onNavigate={onNavigate} layoutId="nav-pill" className="mx-auto" />
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-2">
        <HandsFreeToggle
          enabled={handsFreeEnabled}
          status={handsFreeStatus}
          micError={handsFreeMicError}
          onToggle={onToggleHandsFree}
        />
        {/* V3.75.3: análisis de evolución junto al usuario. Antes vivía en un
            botón flotante dentro de la práctica (panel «Analysis»), donde no se
            encontraba fuera del ejercicio. */}
        <button
          type="button"
          className="icon-button"
          onClick={onOpenAnalysis}
          title={t("analysis.open")}
          aria-label={t("analysis.open")}
        >
          <TrendIcon size={18} />
        </button>
        <button
          type="button"
          className="icon-button"
          onClick={() => onNavigate("help")}
          title={t("help.title")}
          aria-label={t("help.title")}
        >
          <HelpIcon size={18} />
        </button>
        <button
          type="button"
          className="icon-button"
          onClick={onOpenSettings}
          title={t("settings.title")}
          aria-label={t("header.openSettings")}
          aria-haspopup="dialog"
        >
          <GearIcon size={18} />
        </button>
        <UserMenu
          user={user}
          onEdit={onEditUser}
          {...(onRequestDeleteUser ? { onRequestDelete: onRequestDeleteUser } : {})}
          {...(onOpenAccount ? { onOpenAccount } : {})}
        />
      </div>
    </header>
  );
}
