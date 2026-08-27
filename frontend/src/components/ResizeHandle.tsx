import { useRef } from "react";
import type {
  KeyboardEvent as ReactKeyboardEvent,
  PointerEvent as ReactPointerEvent,
} from "react";

interface ResizeHandleProps {
  onDrag: (dx: number) => void;
  label: string;
  /** Ancho actual (para `aria-valuenow`). */
  value?: number;
  min?: number;
  max?: number;
}

/**
 * Asa de redimensionado vertical entre paneles. Se muestra solo en desktop
 * (`hidden lg:flex`); en móvil/tablet los paneles son drawers y no se redimensionan.
 */
export function ResizeHandle({ onDrag, label, value, min, max }: ResizeHandleProps) {
  const startX = useRef(0);

  function onPointerDown(e: ReactPointerEvent<HTMLDivElement>) {
    e.preventDefault();
    startX.current = e.clientX;
    document.body.classList.add("is-resizing");

    const onMove = (ev: PointerEvent) => onDrag(ev.clientX - startX.current);
    const onUp = () => {
      document.body.classList.remove("is-resizing");
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  }

  function onKeyDown(e: ReactKeyboardEvent<HTMLDivElement>) {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    onDrag(e.key === "ArrowLeft" ? -24 : 24);
  }

  return (
    <div
      className="group relative hidden w-2 shrink-0 cursor-col-resize touch-none items-center justify-center lg:flex"
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={value}
      tabIndex={0}
      onPointerDown={onPointerDown}
      onKeyDown={onKeyDown}
    >
      <span
        aria-hidden="true"
        className="h-full w-0.5 rounded-full bg-border transition-colors duration-150 group-hover:bg-primary group-focus-visible:bg-primary"
      />
    </div>
  );
}
