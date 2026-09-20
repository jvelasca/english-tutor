import * as React from "react";
import { Info, MoreHorizontal } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Qué hay dentro del panel, y por tanto qué promete el disparador (V3.75.7):
 *
 * - `"info"`: **solo notas** (una explicación, un aviso de honestidad). El botón
 *   lleva una **(i)**: «aquí hay información», sin prometer nada accionable.
 * - `"options"`: notas **y opciones** (elegir voz, alcance de la repetición). El
 *   botón lleva **(...)**: «aquí se toca algo».
 *
 * La distinción no es cosmética. En esta app el «...» ya significa «abre para
 * **configurar**» (tarjeta de audio de listening), así que un «...» que solo
 * esconde un párrafo obliga al alumno a pulsar para descubrir que no había nada
 * que decidir; y una (i) que esconde controles los oculta bajo una promesa falsa.
 */
export type DisclosureContent = "info" | "options";

interface InfoDisclosureProps {
  /** Notas informativas (routeNote, gate, honestidad del progreso...). */
  children: React.ReactNode;
  /** Etiqueta accesible del disparador (ya traducida). */
  label: string;
  /**
   * `inline`: botón compacto en el flujo, con el panel a ancho completo.
   * `corner`: botón anclado a la esquina de una Card `relative`; el panel
   * ocupa el ancho disponible en el punto donde se monta.
   */
  variant?: "inline" | "corner";
  /** Alineación horizontal del botón en la variante `inline`. */
  align?: "start" | "end";
  /** id del panel (`aria-controls`); debe ser único en la página. */
  id?: string;
  /** Contenido del panel: decide el icono del disparador. `"info"` por defecto. */
  content?: DisclosureContent;
  className?: string;
}

/**
 * Divulgación progresiva de notas informativas (V3.48.1).
 *
 * Sigue la convención de la app (`button` + `aria-expanded`) para dejar limpias
 * las pantallas de práctica: el texto explicativo se monta solo cuando el alumno
 * lo pide. En `corner` el disparador se ancla arriba a la derecha de la Card
 * contenedora (que debe ser `relative`).
 *
 * **El texto nunca queda debajo del disparador (V3.75.7).** En `corner` el botón
 * flota sobre la esquina de la Card, así que el panel —que el llamador monta
 * donde le conviene, a menudo como primer hijo— podía empezar justo bajo él: la
 * primera línea salía tapada por el propio botón que acababa de abrirla. En vez
 * de reservar altura (que dejaría un hueco muerto cuando el panel se monta más
 * abajo), el panel reserva la **columna** del botón con `pr-12` (36px del botón
 * + 12px de separación): el texto se estrecha y nunca coincide con él, suba o no
 * el panel hasta el borde superior. El panel sigue ocupando lo mismo como caja,
 * así que el botón se apoya en su esquina sin tapar una sola letra.
 */
export function InfoDisclosure({
  children,
  label,
  variant = "inline",
  align = "start",
  id,
  content = "info",
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
        {content === "options" ? (
          <MoreHorizontal className="size-4" aria-hidden="true" />
        ) : (
          <Info className="size-4" aria-hidden="true" />
        )}
      </button>
      {open && (
        <div
          id={id}
          className={cn(
            "flex w-full flex-col gap-2 text-[11px] leading-relaxed text-muted-foreground",
            // `pr-12` en la esquina es la garantía de que el texto no pasa por
            // debajo del botón; se compone aparte de `px-3` para no depender del
            // orden en que Tailwind emita las dos utilidades de padding-right.
            corner ? "py-2 pl-3 pr-12" : "px-3 py-2",
            "rounded-lg border border-border bg-muted/30",
          )}
        >
          {children}
        </div>
      )}
    </div>
  );
}
