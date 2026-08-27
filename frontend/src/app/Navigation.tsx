import { motion } from "motion/react";
import { useI18n } from "../hooks/useI18n";
import { ROUTES, type Route } from "./routes";
import { cn } from "@/lib/utils";

export function Navigation({
  route,
  onNavigate,
  layoutId = "nav-pill",
  className,
}: {
  route: Route;
  onNavigate: (route: Route) => void;
  layoutId?: string;
  className?: string;
}) {
  const { t } = useI18n();
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
              "relative flex-1 rounded-full px-4 py-2 text-sm font-semibold whitespace-nowrap transition-colors md:flex-none",
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
