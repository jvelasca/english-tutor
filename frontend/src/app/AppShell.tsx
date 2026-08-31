import type { ReactNode } from "react";
import { StatusBar } from "../components/StatusBar";
import { Navigation } from "./Navigation";
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
        Skip to content
      </a>
      {header}
      <main
        id="main-content"
        tabIndex={-1}
        className="flex min-h-0 flex-1 flex-col overflow-y-auto"
      >
        {children}
      </main>
      <div className="border-t border-border bg-background/95 px-2 py-1 backdrop-blur md:hidden">
        <Navigation
          route={route}
          onNavigate={onNavigate}
          layoutId="nav-pill-mobile"
          className="w-full"
        />
      </div>
      <StatusBar onOpenHelp={() => onNavigate("help")} />
    </div>
  );
}
