import { GraduationCap, House, Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { useI18n } from "../hooks/useI18n";
import { ROUTES, type Route } from "./routes";
import { cn } from "@/lib/utils";

/** Icono lucide de cada destino raíz. Solo los 3 mundos de V3.1 llegan aquí. */
const ROUTE_ICONS: Partial<Record<Route, LucideIcon>> = {
  home: House,
  course: GraduationCap,
  learn: Sparkles,
};

export function Navigation({
  route,
  onNavigate,
  variant = "pills",
  layoutId = "nav-pill",
  className,
}: {
  route: Route;
  onNavigate: (route: Route) => void;
  /** "pills" para la cabecera (>=768px), "bottom" para la bottom-nav móvil. */
  variant?: "pills" | "bottom";
  layoutId?: string;
  className?: string;
}) {
  const { t } = useI18n();

  if (variant === "bottom") {
    return (
      <nav
        className={cn("grid w-full grid-cols-3", className)}
        aria-label={t("nav.aria")}
      >
        {ROUTES.map((r) => {
          const active = route === r.id;
          const Icon = ROUTE_ICONS[r.id];
          return (
            <button
              key={r.id}
              type="button"
              onClick={() => onNavigate(r.id)}
              aria-current={active ? "page" : undefined}
              className={cn(
                "relative flex min-h-14 flex-col items-center justify-center gap-1 px-2 transition-colors",
                active
                  ? "text-primary"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {active && (
                <motion.span
                  layoutId={layoutId}
                  className="bg-primary absolute top-0 h-0.5 w-8 rounded-full"
                  transition={{ type: "spring", stiffness: 400, damping: 32 }}
                />
              )}
              {Icon && (
                <Icon aria-hidden="true" className="size-[22px] shrink-0" strokeWidth={2} />
              )}
              <span className="max-w-full truncate text-[11px] leading-none font-semibold">
                {t(r.i18nKey)}
              </span>
            </button>
          );
        })}
      </nav>
    );
  }

  return (
    <nav className={cn("flex items-center gap-1", className)} aria-label={t("nav.aria")}>
      {ROUTES.map((r) => {
        const active = route === r.id;
        return (
          <button
            key={r.id}
            type="button"
            onClick={() => onNavigate(r.id)}
            aria-current={active ? "page" : undefined}
            className={cn(
              "relative shrink-0 rounded-full px-4 py-2 text-sm font-semibold whitespace-nowrap transition-colors",
              active
                ? "text-primary-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {active && (
              <motion.span
                layoutId={layoutId}
                className="bg-primary absolute inset-0 rounded-full"
                transition={{ type: "spring", stiffness: 400, damping: 32 }}
              />
            )}
            <span className="relative z-10">{t(r.i18nKey)}</span>
          </button>
        );
      })}
    </nav>
  );
}
