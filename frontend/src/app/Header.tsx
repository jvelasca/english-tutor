import { useI18n } from "../hooks/useI18n";
import type { HandsFreeStatus } from "../hooks/useHandsFree";
import type { MicUnavailableReason } from "../utils/browserCapabilities";
import type { User } from "../types/api";
import type { UserPatch } from "../api/users";
import type { Route } from "./routes";
import { Navigation } from "./Navigation";
import { HandsFreeToggle } from "../components/HandsFreeToggle";
import { UserMenu } from "../components/UserMenu";
import { GearIcon } from "../components/Icons";

interface HeaderProps {
  route: Route;
  onNavigate: (route: Route) => void;
  users: User[];
  currentUserId: string | null;
  onSelectUser: (id: string) => void;
  onAddUser: (name: string) => void;
  onEditUser: (id: string, patch: UserPatch) => Promise<User | null>;
  handsFreeEnabled: boolean;
  handsFreeStatus: HandsFreeStatus;
  handsFreeMicError: MicUnavailableReason | null;
  onToggleHandsFree: () => void;
  onOpenSettings: () => void;
}

export function Header({
  route,
  onNavigate,
  users,
  currentUserId,
  onSelectUser,
  onAddUser,
  onEditUser,
  handsFreeEnabled,
  handsFreeStatus,
  handsFreeMicError,
  onToggleHandsFree,
  onOpenSettings,
}: HeaderProps) {
  const { t } = useI18n();
  return (
    <header className="sticky top-0 z-40 flex items-center gap-4 border-b border-border bg-background/80 px-4 py-2.5 backdrop-blur-xl">
      <div className="flex min-w-0 items-center">
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
      </div>

      <div className="hidden min-w-0 flex-1 justify-center md:flex">
        <Navigation route={route} onNavigate={onNavigate} layoutId="nav-pill" />
      </div>

      <div className="flex items-center gap-2">
        <HandsFreeToggle
          enabled={handsFreeEnabled}
          status={handsFreeStatus}
          micError={handsFreeMicError}
          onToggle={onToggleHandsFree}
        />
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
          users={users}
          currentUserId={currentUserId}
          onSelect={onSelectUser}
          onAdd={onAddUser}
          onEdit={onEditUser}
        />
      </div>
    </header>
  );
}
