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
      {header}
      {children}
      <div className="border-t border-border bg-background/95 px-2 py-1 backdrop-blur md:hidden">
        <Navigation
          route={route}
          onNavigate={onNavigate}
          layoutId="nav-pill-mobile"
          className="w-full"
        />
      </div>
      <StatusBar />
    </div>
  );
}
