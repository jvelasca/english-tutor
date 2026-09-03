import { useEffect, useState } from "react";
import { AnimatePresence, motion, type Variants } from "motion/react";
import {
  BarChart3,
  GraduationCap,
  LayoutDashboard,
  Layers,
  Route,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { getStudentModel } from "../../api/academy";
import type { StudentModel } from "../../types/api";
import { useI18n } from "../../hooks/useI18n";
import { EstimatedLevelBadge } from "../../components/LevelBadge";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { cn } from "../../lib/utils";
import { ResumenTab } from "./ResumenTab";
import { CursoTab } from "./CursoTab";
import { HabilidadesTab } from "./HabilidadesTab";
import { TrayectoriaTab } from "./TrayectoriaTab";
import { RecorridosTab } from "./RecorridosTab";

/** Pestañas de MI PROGRESO (UI_V3.1 §4.4). */
export type ProgressTab =
  | "overview"
  | "course"
  | "skills"
  | "journey"
  | "tracks";

interface TabDef {
  id: ProgressTab;
  labelKey: string;
  Icon: LucideIcon;
}

const TABS: TabDef[] = [
  { id: "overview", labelKey: "progress.overviewTab", Icon: LayoutDashboard },
  { id: "course", labelKey: "progress.courseTab", Icon: GraduationCap },
  { id: "skills", labelKey: "progress.skillsTab", Icon: BarChart3 },
  { id: "journey", labelKey: "progress.journeyTab", Icon: Route },
  { id: "tracks", labelKey: "progress.tracksTab", Icon: Layers },
];

function isProgressTab(value: string | undefined): value is ProgressTab {
  return TABS.some((tab) => tab.id === value);
}

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};

const item: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
  },
};

interface ProgressScreenProps {
  userId: string | null;
  refreshKey?: number;
  /** Pestaña inicial. Workspace la fija a "journey" en la sub-ruta legada #/progreso/trayectoria. */
  initialTab?: ProgressTab;
}

/**
 * MI PROGRESO (V3.1): pantalla de 5 pestañas accesibles que consolida
 * ProgressScreen, la escalera de JourneyScreen y los paneles de perfil que
 * vivían ocultos en el panel Analysis (UI_V3.1 §4.4 y §4.5).
 *
 * Cada pestaña es autónoma (fetches propios); la pantalla solo consulta el
 * modelo del alumno para la cabecera (nivel estimado + banda de readiness).
 */
export function ProgressScreen({
  userId,
  refreshKey = 0,
  initialTab,
}: ProgressScreenProps) {
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState<ProgressTab>(() =>
    isProgressTab(initialTab) ? initialTab : "overview",
  );
  const [model, setModel] = useState<StudentModel | null>(null);

  // La sub-ruta legada #/progreso/trayectoria (route "journey") pide abrir la
  // pestaña Trayectoria; volver a #/progreso restaura Resumen.
  useEffect(() => {
    if (isProgressTab(initialTab)) setActiveTab(initialTab);
    else setActiveTab("overview");
  }, [initialTab]);

  // El modelo del alumno alimenta las insignias de la cabecera (nivel
  // estimado + readiness); cada pestaña hace sus propios fetches al activarse.
  useEffect(() => {
    if (!userId) {
      setModel(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const m = await getStudentModel(userId);
        if (!cancelled) setModel(m);
      } catch {
        if (!cancelled) setModel(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, refreshKey]);

  const band = model?.readiness.band ?? "developing";

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 lg:py-8">
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="flex flex-col gap-5"
      >
        <motion.header
          variants={item}
          className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3"
        >
          <div>
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
              {t("progress.title")}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {t("progress.subtitle")}
            </p>
          </div>
          {model && (
            <div className="flex flex-wrap items-center gap-2">
              <EstimatedLevelBadge level={model.estimated_level} />
              <Badge variant="secondary">
                {model.target_level} · {t(`readiness.${band}`)}
              </Badge>
            </div>
          )}
        </motion.header>

        {!userId ? (
          <motion.div variants={item}>
            <Card className="p-6 text-center">
              <p className="text-sm text-muted-foreground">
                {t("empty.noProfile")}
              </p>
            </Card>
          </motion.div>
        ) : (
          <>
            <motion.nav variants={item} aria-label={t("progress.tabAria")}>
              <div
                role="tablist"
                aria-label={t("progress.tabAria")}
                className="flex gap-1 overflow-x-auto rounded-xl border border-border bg-card p-1 shadow-sm"
              >
                {TABS.map((tab) => {
                  const selected = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      role="tab"
                      id={`progress-tab-${tab.id}`}
                      aria-selected={selected}
                      aria-controls={`progress-panel-${tab.id}`}
                      tabIndex={selected ? 0 : -1}
                      onClick={() => setActiveTab(tab.id)}
                      className={cn(
                        "relative flex min-h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg px-3.5 py-2 text-sm font-medium transition-colors sm:px-4",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                        selected
                          ? "text-primary"
                          : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      {selected && (
                        <motion.span
                          layoutId="progress-tab-pill"
                          className="absolute inset-0 rounded-lg bg-accent"
                          transition={{
                            type: "spring",
                            stiffness: 500,
                            damping: 40,
                          }}
                        />
                      )}
                      <tab.Icon
                        className="relative z-10 size-4 shrink-0"
                        aria-hidden="true"
                      />
                      <span className="relative z-10">{t(tab.labelKey)}</span>
                    </button>
                  );
                })}
              </div>
            </motion.nav>

            <div
              role="tabpanel"
              id={`progress-panel-${activeTab}`}
              aria-labelledby={`progress-tab-${activeTab}`}
            >
              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key={activeTab}
                  initial={{ opacity: 0, x: 8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -8 }}
                  transition={{ duration: 0.15, ease: "easeOut" }}
                >
                  {activeTab === "overview" && (
                    <ResumenTab userId={userId} refreshKey={refreshKey} />
                  )}
                  {activeTab === "course" && (
                    <CursoTab userId={userId} refreshKey={refreshKey} />
                  )}
                  {activeTab === "skills" && (
                    <HabilidadesTab userId={userId} refreshKey={refreshKey} />
                  )}
                  {activeTab === "journey" && (
                    <TrayectoriaTab userId={userId} refreshKey={refreshKey} />
                  )}
                  {activeTab === "tracks" && (
                    <RecorridosTab userId={userId} refreshKey={refreshKey} />
                  )}
                </motion.div>
              </AnimatePresence>
            </div>
          </>
        )}
      </motion.div>
    </div>
  );
}
