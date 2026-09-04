import { BookOpen, MessageSquareText } from "lucide-react";
import type { ComponentType, SVGProps } from "react";
import {
  GrammarIcon,
  ListeningIcon,
  PronunciationIcon,
  SpeakingIcon,
} from "./Icons";
import { useI18n } from "../hooks/useI18n";
import { navigateTo } from "../router/hash";
import { learnActivityPath } from "../router/paths";
import {
  CONVERSATION_ACTIVITY,
  GRAMMAR_ACTIVITY,
  LISTENING_ACTIVITY,
  PRONUNCIATION_ACTIVITY,
  SPEAKING_ACTIVITY,
  VOCABULARY_ACTIVITY,
  type LearnActivity,
} from "../router/learnHub";
import { cn } from "../lib/utils";

type IconType = ComponentType<
  { size?: number; className?: string } & SVGProps<SVGSVGElement>
>;

interface ActivityEntry {
  id: LearnActivity;
  titleKey: string;
  Icon: IconType;
}

/**
 * Las 6 actividades del hub de APRENDER, en el mismo orden que las tarjetas de
 * LearnHub: atajo directo entre prácticas desde la franja superior.
 */
const ACTIVITIES: ActivityEntry[] = [
  { id: LISTENING_ACTIVITY, titleKey: "skill.listening", Icon: ListeningIcon },
  { id: SPEAKING_ACTIVITY, titleKey: "skill.speaking", Icon: SpeakingIcon },
  {
    id: PRONUNCIATION_ACTIVITY,
    titleKey: "skill.pronunciation",
    Icon: PronunciationIcon,
  },
  {
    id: CONVERSATION_ACTIVITY,
    titleKey: "learn.conversation",
    Icon: MessageSquareText,
  },
  { id: VOCABULARY_ACTIVITY, titleKey: "skill.vocabulary", Icon: BookOpen },
  { id: GRAMMAR_ACTIVITY, titleKey: "skill.grammar", Icon: GrammarIcon },
];

interface LearnActivitySwitcherProps {
  /** Actividad actualmente en práctica (null = ninguna / hub). */
  active: LearnActivity | null;
}

/**
 * Atajo entre actividades de APRENDER (V3.6.1): píldoras icono + nombre que
 * navegan por hash a `#/aprender/<actividad>`; la activa queda resaltada y
 * deshabilitada. Navegar ya alinea sección/modo en `App.tsx`
 * (`ACTIVITY_SECTION`/`ACTIVITY_MODE`). En pantallas estrechas se muestran
 * solo los iconos (con `title`/aria) y las etiquetas aparecen desde `md`.
 */
export function LearnActivitySwitcher({
  active,
}: LearnActivitySwitcherProps) {
  const { t } = useI18n();
  return (
    <div
      role="group"
      aria-label={t("learn.switchActivity")}
      className="-my-1 flex min-w-0 flex-1 items-center gap-0.5 overflow-x-auto py-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
      {ACTIVITIES.map(({ id, titleKey, Icon }) => {
        const label = t(titleKey);
        const isActive = active === id;
        return (
          <button
            key={id}
            type="button"
            onClick={() => navigateTo(learnActivityPath(id))}
            disabled={isActive}
            aria-current={isActive ? "page" : undefined}
            aria-label={label}
            title={label}
            className={cn(
              "inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-full border px-2.5 text-xs font-semibold whitespace-nowrap transition-colors",
              isActive
                ? "cursor-default border-primary/60 bg-primary/10 text-primary"
                : "border-transparent text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
            )}
          >
            <Icon size={15} className="shrink-0" />
            <span className="hidden md:inline">{label}</span>
          </button>
        );
      })}
    </div>
  );
}
