import { Fragment } from "react";
import { BookOpen, GraduationCap, House, Languages, Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { useI18n } from "../hooks/useI18n";
import { ROUTES, type Route, type RouteOption } from "./routes";
import { cn } from "@/lib/utils";

/** Icono lucide de cada destino raíz (3 mundos + diccionario y traductor). */
const ROUTE_ICONS: Partial<Record<Route, LucideIcon>> = {
  home: House,
  course: GraduationCap,
  learn: Sparkles,
  dictionary: BookOpen,
  // V3.39 (Fase 2): utilidad de traducción bidireccional ES↔EN.
  translator: Languages,
};

/**
 * V3.38.1: el diccionario es un destino AUXILIAR, no un mundo del core. Se
 * marca visualmente con un separador (barra vertical en las píldoras de
 * escritorio, divisor real en la bottom-nav móvil) para que no compita con
 * Inicio / Formación / Aprender. V3.39 añade el Traductor al MISMO bloque
 * auxiliar (tras el separador, junto al diccionario).
 *
 * V3.73.1 (GUI-03): se mantienen los cinco destinos —el diccionario debe seguir
 * a un toque en móvil—, pero la jerarquía se refuerza en la bottom-nav con un
 * divisor vertical de verdad y un peso visual algo menor en las dos utilidades
 * (icono y etiqueta un punto más pequeños). El color NO se degrada: bajar el
 * contraste de un destino táctil sería un retroceso de accesibilidad.
 */
const DIVIDER_BEFORE: Route = "dictionary";

const DIVIDER_INDEX = ROUTES.findIndex((r) => r.id === DIVIDER_BEFORE);
/** Los 3 mundos del núcleo: Inicio · Formación · Aprender. */
const CORE_ROUTES: RouteOption[] = ROUTES.slice(0, DIVIDER_INDEX);
/** Las utilidades de apoyo: Diccionario · Traductor. */
const AUXILIARY_ROUTES: RouteOption[] = ROUTES.slice(DIVIDER_INDEX);

/**
 * Destino de la bottom-nav. `auxiliary` reduce un punto el icono y la etiqueta
 * (nunca el tamaño del botón: sigue siendo el destino completo, ≥56px de alto y
 * ≥44px de ancho).
 */
function BottomDestination({
  option,
  active,
  auxiliary = false,
  layoutId,
  onNavigate,
}: {
  option: RouteOption;
  active: boolean;
  auxiliary?: boolean;
  layoutId: string;
  onNavigate: (route: Route) => void;
}) {
  const { t } = useI18n();
  const Icon = ROUTE_ICONS[option.id];
  return (
    <button
      type="button"
      onClick={() => onNavigate(option.id)}
      aria-current={active ? "page" : undefined}
      className={cn(
        "relative flex min-h-14 min-w-0 flex-1 flex-col items-center justify-center gap-1 px-1 transition-colors",
        active ? "text-primary" : "text-muted-foreground hover:text-foreground",
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
        <Icon
          aria-hidden="true"
          className={cn("shrink-0", auxiliary ? "size-5" : "size-[22px]")}
          strokeWidth={2}
        />
      )}
      <span
        className={cn(
          "max-w-full truncate leading-none font-semibold",
          auxiliary ? "text-[10px]" : "text-[11px]",
        )}
      >
        {t(option.i18nKey)}
      </span>
    </button>
  );
}

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
        className={cn("flex w-full items-stretch", className)}
        aria-label={t("nav.aria")}
      >
        {CORE_ROUTES.map((option) => (
          <BottomDestination
            key={option.id}
            option={option}
            active={route === option.id}
            layoutId={layoutId}
            onNavigate={onNavigate}
          />
        ))}
        {/* Divisor real (mismo lenguaje que las píldoras de escritorio): separa
            los 3 mundos de las 2 utilidades de apoyo sin robarles el toque. */}
        <span
          aria-hidden="true"
          data-testid="nav-divider"
          className="bg-border my-2.5 w-px shrink-0"
        />
        {AUXILIARY_ROUTES.map((option) => (
          <BottomDestination
            key={option.id}
            option={option}
            active={route === option.id}
            auxiliary
            layoutId={layoutId}
            onNavigate={onNavigate}
          />
        ))}
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
