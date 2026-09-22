/**
 * Última red de la UI (V3.77.2).
 *
 * React NO atrapa los errores lanzados durante el render sin un `ErrorBoundary`:
 * desmonta el árbol entero y deja la app en blanco. Ese era el radio real de un
 * contrato HTTP incompleto (el fallo de V3.77.0 que solo se parcheó en
 * `AddVocabSection`): no moría «la tarjeta», moría la app.
 *
 * Aquí se declaran DOS radios, porque el coste de fallar no es el mismo:
 *
 * - `scope="app"`  (root, envuelve `<App />`): captura lo que ningún boundary
 *   interno pudo atrapar. No hay contexto de i18n por encima de `<App />`, así
 *   que las cadenas se leen con `translate()` a partir del idioma persistido,
 *   igual que hace el cliente de API.
 * - `scope="route"` (envuelve la pantalla activa): contiene el fallo en una
 *   pantalla y deja navegación, cabecera y perfil utilizables.
 *
 * El detalle técnico se muestra plegado (`<details>`): es información honesta
 * para un proyecto local, sin convertir el aviso en una traza ilegible.
 */
import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCw, RotateCcw } from "lucide-react";
import { translate, type Lang } from "../utils/i18n";
import { Button } from "./ui/button";
import { cn } from "@/lib/utils";

const LANG_STORAGE_KEY = "english-tutor.lang";

/** Idioma de la UI leído del almacenamiento: el boundary vive fuera del
 *  `I18nProvider`, así que no puede depender del contexto. */
function currentLang(): Lang {
  try {
    return window.localStorage.getItem(LANG_STORAGE_KEY) === "es" ? "es" : "en";
  } catch {
    return "en";
  }
}

export interface ErrorBoundaryProps {
  children: ReactNode;
  /**
   * Radio declarado del boundary:
   * - `"app"`: envuelve la aplicación entera (root).
   * - `"route"`: envuelve la pantalla activa.
   */
  scope?: "app" | "route";
  /** Se ejecuta al reintentar, ANTES de limpiar el error (p. ej. navegar). */
  onReset?: () => void;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // En un proyecto local el log de consola es el canal de diagnóstico; no se
    // envía a ningún sitio ni se oculta el error al alumno.
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  private retry = () => {
    this.props.onReset?.();
    this.setState({ error: null });
  };

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;

    const t = (key: string) => translate(currentLang(), key);
    const isRoute = this.props.scope === "route";

    return (
      <div
        role="alert"
        className={cn(
          "flex flex-col items-center justify-center gap-4 px-4 py-12 text-center",
          isRoute ? "min-h-[60vh]" : "h-full min-h-screen",
        )}
      >
        <span className="grid size-12 place-items-center rounded-2xl bg-destructive/10 text-destructive">
          <AlertTriangle className="size-6" aria-hidden="true" />
        </span>
        <div className="flex max-w-md flex-col gap-2">
          <h1 className="text-lg font-bold tracking-tight">
            {t("error.boundary.title")}
          </h1>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {t(
              isRoute
                ? "error.boundary.route.hint"
                : "error.boundary.app.hint",
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-2">
          <Button type="button" size="sm" onClick={this.retry}>
            <RotateCcw aria-hidden="true" />
            {t("common.retry")}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => window.location.reload()}
          >
            <RefreshCw aria-hidden="true" />
            {t("error.boundary.reload")}
          </Button>
        </div>
        {error.message ? (
          <details className="max-w-md text-left">
            <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
              {t("error.boundary.details")}
            </summary>
            <p className="mt-2 rounded-md bg-secondary/60 px-3 py-2 text-[11px] leading-relaxed break-words text-muted-foreground">
              {error.message}
            </p>
          </details>
        ) : null}
      </div>
    );
  }
}
