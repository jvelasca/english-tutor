import { Fragment } from "react";
import { BookOpen, GraduationCap, House, Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { useI18n } from "../hooks/useI18n";
import { ROUTES, type Route } from "./routes";
import { cn } from "@/lib/utils";

/** Icono lucide de cada destino raíz (los 3 mundos + el diccionario auxiliar). */
const ROUTE_ICONS: Partial<Record<Route, LucideIcon>> = {
  home: House,
  course: GraduationCap,
  learn: Sparkles,
  dictionary: BookOpen,
};

/**
 * V3.38.1: el diccionario es un destino AUXILIAR, no un mundo del core. Se
 * marca visualmente con un separador (barra vertical en las píldoras de
 * escritorio, borde divisorio en la bottom-nav móvil) para que no compita con
 * Inicio / Formación / Aprender.
 */
const DIVIDER_BEFORE: Route = "dictionary";

export function Navigation({
  route,
  onNavigate,
  variant = "pills",
  layoutId = "nav-pill",
  className,
}: {
  route: Route;
  onNavigate: (route: Route) => void;
  /**
   * V3.38.1: "pills" se monta en la cabecera solo desde `xl` (>=1280px) —por
   * debajo, con el 4.º destino, no cabe sin invadir las acciones— y "bottom"
   * cubre el resto hasta `xl` (antes el corte estaba en `md`).
   */
  variant?: "pills" | "bottom";
  layoutId?: string;
  className?: string;
}) {
  const { t } = useI18n();

  if (variant === "bottom") {
    return (
      <nav
        className={cn("grid w-full grid-cols-4", className)}
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
                r.id === DIVIDER_BEFORE && "border-border/60 border-l",
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
          <Fragment key={r.id}>
            {r.id === DIVIDER_BEFORE && (
              <span
                aria-hidden="true"
                data-testid="nav-divider"
                className="bg-border mx-1 h-5 w-px shrink-0"
              />
            )}
            <button
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
          </Fragment>
        );
      })}
    </nav>
  );
}
