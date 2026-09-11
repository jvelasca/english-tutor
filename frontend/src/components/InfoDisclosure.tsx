import * as React from "react";
import { MoreHorizontal } from "lucide-react";
import { cn } from "@/lib/utils";

interface InfoDisclosureProps {
  /** Notas informativas (routeNote, gate, honestidad del progreso...). */
  children: React.ReactNode;
  /** Etiqueta accesible del disparador (ya traducida). */
  label: string;
  /**
   * `inline`: botón compacto en el flujo, con el panel a ancho completo.
   * `corner`: botón «...» anclado a la esquina de una Card `relative`; el panel
   * ocupa el ancho disponible en el punto donde se monta.
   */
  variant?: "inline" | "corner";
  /** Alineación horizontal del botón en la variante `inline`. */
  align?: "start" | "end";
  /** id del panel (`aria-controls`); debe ser único en la página. */
  id?: string;
  className?: string;
}

/**
 * Divulgación progresiva de notas informativas (V3.48.1).
 *
 * Sigue la convención de la app (`button` + `aria-expanded` + `MoreHorizontal`)
 * para dejar limpias las pantallas de práctica: el texto explicativo se monta
 * solo cuando el alumno lo pide. En `corner` el disparador se ancla arriba a la
 * derecha de la Card contenedora (que debe ser `relative`).
 */
export function InfoDisclosure({
  children,
  label,
  variant = "inline",
  align = "start",
  id,
  className,
}: InfoDisclosureProps) {
  const [open, setOpen] = React.useState(false);
  const corner = variant === "corner";

  return (
    <div
      className={cn(
        corner ? "contents" : "flex w-full flex-col gap-2",
        className,
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls={id}
        aria-label={label}
        title={label}
        className={cn(
          "grid shrink-0 place-items-center rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
          corner ? "absolute top-3 right-3 z-10 size-9" : "size-8",
          !corner && (align === "end" ? "self-end" : "self-start"),
          open
            ? "border-transparent bg-primary text-primary-foreground"
            : "border-border bg-secondary text-secondary-foreground hover:border-primary/50 hover:text-foreground",
        )}
      >
        <MoreHorizontal className="size-4" aria-hidden="true" />
      </button>
      {open && (
        <div
          id={id}
          className="flex w-full flex-col gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2 text-[11px] leading-relaxed text-muted-foreground"
        >
          {children}
        </div>
      )}
    </div>
  );
}
