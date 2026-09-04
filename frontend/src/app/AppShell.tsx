import type { ReactNode } from "react";
import { StatusBar } from "../components/StatusBar";
import { Navigation } from "./Navigation";
import { useI18n } from "../hooks/useI18n";
import type { Route } from "./routes";

export function AppShell({
  header,
  route,
  onNavigate,
  children,
}: {
  header: ReactNode;
  route: Route;
  onNavigate: (route: Route) => void;
  children: ReactNode;
}) {
  const { t } = useI18n();
  return (
    <div className="relative flex h-full flex-col">
      <a
        href="#main-content"
        className="skip-link"
        onClick={(e) => {
          const el = document.getElementById("main-content");
          if (el) {
            e.preventDefault();
            el.focus();
            el.scrollIntoView();
          }
        }}
      >
        {t("common.skipToContent")}
      </a>
      {header}
      <main
        id="main-content"
        tabIndex={-1}
        className="flex min-h-0 flex-1 flex-col overflow-y-auto"
      >
        {children}
      </main>
      <StatusBar />
      <div className="border-t border-border bg-background/95 backdrop-blur md:hidden">
        <Navigation
          route={route}
          onNavigate={onNavigate}
          variant="bottom"
          layoutId="nav-pill-mobile"
        />
      </div>
    </div>
  );
}
