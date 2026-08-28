import * as React from "react";
import { cn } from "@/lib/utils";

interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactNode;
  side?: "top" | "bottom";
  className?: string;
  contentClassName?: string;
}

/**
 * Tooltip ligero y accesible (sin dependencias extra). Se abre con hover (desktop)
 * y con foco/tap (móvil/teclado); el contenido solo se monta cuando está abierto.
 * El trigger debe ser un elemento enfocable (p. ej. un `<button>`).
 */
export function Tooltip({
  content,
  children,
  side = "top",
  className,
  contentClassName,
}: TooltipProps) {
  const [open, setOpen] = React.useState(false);
  return (
    <span
      className={cn("relative inline-flex", className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocusCapture={() => setOpen(true)}
      onBlurCapture={() => setOpen(false)}
    >
      {children}
      {open && (
        <span
          role="tooltip"
          className={cn(
            "absolute left-1/2 z-50 w-max max-w-[16rem] -translate-x-1/2 rounded-lg border border-border bg-popover px-3 py-2 text-xs font-normal leading-snug text-popover-foreground shadow-md",
            side === "top" ? "bottom-full mb-2" : "top-full mt-2",
            contentClassName,
          )}
        >
          {content}
        </span>
      )}
    </span>
  );
}
