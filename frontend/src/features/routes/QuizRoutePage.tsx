/**
 * Página única compartida de las rutas de quiz (V3.13, P2.1 — wave 1).
 *
 * APRENDER → Grammar / Vocabulary por rutas: ambas son páginas únicas con
 * scroll, mismo escenario de práctica arriba (check del currículo: MC o
 * producción controlada escrita con corrección determinista), mismo mapa de
 * rutas A1–C2 con anillos y el mismo bloque «Demostrar el nivel» (examen /
 * escalera de evaluaciones del curso).
 *
 * Esta página parametriza esa estructura con un `RouteQuizConfig` por destreza
 * (namespace i18n, API y panel de nivel), de modo que las páginas de cada
 * destreza quedan como un wrapper fino (~60 líneas) en vez de duplicar
 * ~1000 líneas. La ruta es un hito de práctica con techo `functional`;
 * demostrar el nivel exige examen + evidencia formal, nunca la ruta.
 */
import { useEffect, useState } from "react";
import type { ComponentType, ReactNode } from "react";
import {
  ArrowLeft,
  Award,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  GraduationCap,
  Info,
  Loader2,
  X,
} from "lucide-react";
import { useI18n } from "../../hooks/useI18n";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { ActivityResult } from "../../components/ActivityResult";
import { LearnActivitySwitcher } from "../../components/LearnActivitySwitcher";
import { ProgressRing } from "../../components/ProgressRing";
import type { LearnActivity } from "../../router/learnHub";
import type { NextBestActivity } from "../../types/api";
import type { Section } from "../../utils/sections";
import { cn } from "../../lib/utils";
import { AssessmentLadder } from "../assessment/AssessmentLadder";
import { SpeakingAssessment } from "../speaking/SpeakingAssessment";
import {
  drillAnswered,
  isSessionFinished,
  sessionDone,
  type RouteSession,
} from "./routeSession";
import type {
  RouteAttempt,
  RouteQuestion,
  RouteQuestionMode,
  RouteStats,
} from "./quizRouteTypes";

/* ------------------------------------------------------------------ */
/* Tipos de la página compartida                                        */
/* ------------------------------------------------------------------ */

export interface RouteLevelPanelProps {
  userId: string | null;
  level: string;
  /** Sesión de práctica activa: no se pueden iniciar más sesiones. */
  disabled?: boolean;
  /** Contador que fuerza a recargar el panel (tras un intento). */
  refreshNonce?: number;
  /** Estado de la ruta del nivel (paneles de destrezas orales). */
  routeState?: "not_started" | "developing" | "functional";
  /** Nivel oral demostrado con el Speaking Assessment (destrezas orales). */
  assessedLevel?: string | null;
  onPracticeLevel: (level: string, total: number) => void;
  onDrillFailed: (level: string, failedIds: string[]) => void;
  /** Repasar lo aprendido: rotación solo por los checks ya acertados. */
  onReviewLearned: (level: string, total: number) => void;
  /** Abre el instrumento formal ("demostrar el nivel" con examen/escalera). */
  onDemonstrate: (level: string) => void;
}

export interface RouteDictionaryConfig {
  /** Clave del botón del diccionario p. ej. `vocRoutes.dictionaryCta`. */
  ctaKey: string;
  /** Clave del hint del diccionario, p. ej. `vocRoutes.dictionaryHint`. */
  hintKey: string;
  View: ComponentType<{ userId: string | null }>;
}

/**
 * Modo de superficie de una práctica unificada (DISENO-SPEAKING-UNICO F1):
 * la página Speaking agrupa los modos orales micro-conversación / acento /
 * diálogo guiado bajo una misma URL. Cada pestaña remonta la página con la
 * configuración de su modo (`QuizRoutePage key={modo}`).
 */
export interface RouteModeTab {
  /** Identificador estable del modo (p. ej. "micro" | "accent" | "dialogue"). */
  id: string;
  /** Clave i18n de la etiqueta de la pestaña. */
  labelKey: string;
}

/**
 * Contexto que recibe la escena de práctica de una destreza (V3.13 P2.1).
 *
 * La página compartida posee el marco: cabecera, estadísticas y anillos, la
 * máquina de sesión (level/drill/mastered), el panel del nivel y las vistas
 * formales. La escena (tarjeta del ejercicio: MC, producción controlada,
 * read-aloud, chat guiado…) vive en la página de la destreza, se remonta por
 * cada ítem (`key` del padre) y reporta a la página solo lo esencial.
 */
export interface LearnSceneProps {
  userId: string | null;
  ns: string;
  t: TranslateFn;
  /** Ítem activo del escenario (pregunta / frase / diálogo), opaco aquí. */
  item: unknown;
  itemLoading: boolean;
  itemError: boolean;
  /** La sesión ha terminado (banner de cierre sustituye a la escena). */
  finished: boolean;
  sessionActive: boolean;
  /** Ha habido un intento puntuado: refresca anillos y avisa al padre. */
  onReport: () => void;
  /** Avanza tras un resultado (o acaba la sesión) con el id del ítem. */
  onAnswered: (itemId: string, passed: boolean) => void;
  /** Salta al siguiente ítem del mismo bucket (práctica libre). */
  onSkip: () => void;
}

export interface RouteQuizApi {
  getStats: (userId: string) => Promise<RouteStats>;
  getQuestion: (
    userId: string,
    level: string,
    mode: RouteQuestionMode,
  ) => Promise<unknown>;
  submitAttempt: (
    userId: string,
    checkId: string,
    selectedIndex: number,
    typedAnswer?: string,
  ) => Promise<RouteAttempt>;
}

export interface RouteQuizConfig {
  /** Namespace i18n de la destreza (p. ej. "gramRoutes", "vocRoutes"). */
  ns: string;
  /** Clave del título de la página (p. ej. "skill.grammar"; en superficies
      con modos, "speaking.surfaceTitleAccent"). */
  skillTitleKey: string;
  /** Clave del subtítulo bajo el título (p. ej. "learn.grammarSubtitle"). */
  subtitleKey: string;
  /** Id estable de la lista de ítems (aria-controls de los anillos). */
  ariaLevelItemsId: string;
  LevelPanel: ComponentType<RouteLevelPanelProps>;
  api: RouteQuizApi;
  /** Vista extra (diccionario personal en Vocabulary). */
  dictionary?: RouteDictionaryConfig;
  /** Escena de práctica personalizada (read-aloud, chat guiado…). Sin ella, la
      página usa la escena de quiz MC / producción controlada. */
  scene?: ComponentType<LearnSceneProps>;
  /** Carga el nivel oral demostrado (`/api/academy/speaking/level`) para
      mostrarlo en el mapa y en los paneles (destrezas orales). */
  loadAssessed?: (userId: string) => Promise<string | null>;
  /** Instrumento formal para "demostrar el nivel": `ladder` (AssessmentLadder,
      por defecto) o `speaking` (Speaking Assessment completo). */
  assessment?: "ladder" | "speaking";
  /** Tarjeta extra tras el mapa de rutas (p. ej. conversación libre). */
  trailing?: ComponentType<{ userId: string | null }>;
  /** Sin perfil activo: solo spinner (p. ej. conversation). */
  requireUser?: boolean;
  /** V3.21 (V20-03/04): clave i18n de la competencia REAL que miden las stats
      del mapa (Producción oral / Pronunciación / Conversación). Si se omite,
      el bloque de stats no muestra etiqueta de competencia adicional. */
  statsCompetenceKey?: string;
}

interface QuizRoutePageProps {
  userId: string | null;
  active: LearnActivity;
  onBack: () => void;
  onAttempt: () => void;
  onNext: (section: Section | null, step: NextBestActivity) => void;
  config: RouteQuizConfig;
  /** Pestañas de modo de superficie (p. ej. los modos orales de Speaking). */
  modeTabs?: readonly RouteModeTab[];
  /** Modo de superficie activo (debe ser un id de `modeTabs`). */
  modeTab?: string;
  /** Cambia el modo de superficie: el padre remonta la página con otra config. */
  onModeChange?: (mode: string) => void;
}

type RouteView =
  | { kind: "routes" }
  | { kind: "assessment"; level: string }
  | { kind: "dictionary" };

function routeMode(session: RouteSession | null): RouteQuestionMode {
  if (!session) return "all";
  return session.mode === "drill"
    ? "failed"
    : session.mode === "mastered"
      ? "mastered"
      : "all";
}

export type TranslateFn = (k: string) => string;

/* ------------------------------------------------------------------ */
/* Página compartida                                                    */
/* ------------------------------------------------------------------ */

export function QuizRoutePage({
  userId,
  active,
  onBack,
  onAttempt,
  onNext,
  config,
  modeTabs,
  modeTab,
  onModeChange,
}: QuizRoutePageProps) {
  const { t } = useI18n();
  const ns = config.ns;
  const nk = (key: string) => `${ns}.${key}`;

  const [view, setView] = useState<RouteView>({ kind: "routes" });
  const [stats, setStats] = useState<RouteStats | null>(null);
  // Nivel oral demostrado (Speaking Assessment) en destrezas orales.
  const [assessedLevel, setAssessedLevel] = useState<string | null>(null);
  const [expandedLevel, setExpandedLevel] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [refreshNonce, setRefreshNonce] = useState(0);
  // Sesión focalizada activa (drill / repaso / vuelta del nivel). Sin sesión, el
  // escenario practica la ruta recomendada (stats.level) en modo libre.
  const [session, setSession] = useState<RouteSession | null>(null);
  // Ítem activo del escenario superior (pregunta / frase / diálogo): opaco para
  // la página, la escena de la destreza lo interpreta.
  const [question, setQuestion] = useState<unknown>(null);
  const [cardLoading, setCardLoading] = useState(false);
  const [cardError, setCardError] = useState(false);
  const [result, setResult] = useState<RouteAttempt | null>(null);
  const [busy, setBusy] = useState(false);
  const [attemptError, setAttemptError] = useState<string | null>(null);
  // Seq de "siguiente pregunta": avanzar tras responder o saltar.
  const [seq, setSeq] = useState(0);
  // El texto «Cómo funcionan las rutas» va plegado por defecto tras un botón (i).
  const [routesInfoOpen, setRoutesInfoOpen] = useState(false);

  // --- Carga inicial de estadísticas y nivel oral demostrado ------------------
  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    setLoadError(false);
    const uid = userId;
    void (async () => {
      try {
        const [s, lvl] = await Promise.all([
          config.api.getStats(uid),
          config.loadAssessed
            ? config.loadAssessed(uid)
            : Promise.resolve(null),
        ]);
        if (cancelled) return;
        setStats(s);
        if (lvl !== null) setAssessedLevel(lvl);
        // Despliega por defecto el nivel en el que está el alumno.
        setExpandedLevel((cur) => cur ?? s.level ?? null);
      } catch {
        if (!cancelled) setLoadError(true);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, refreshNonce]);

  // --- Pregunta activa del escenario ------------------------------------------
  const finished = session !== null && isSessionFinished(session);
  const stageLevel = session?.level ?? stats?.level ?? null;
  const stageMode = routeMode(session);

  useEffect(() => {
    if (!userId || finished || !stageLevel) return;
    let cancelled = false;
    setCardLoading(true);
    setCardError(false);
    setQuestion(null);
    setResult(null);
    setAttemptError(null);
    const uid = userId;
    void (async () => {
      try {
        const q = await config.api.getQuestion(uid, stageLevel, stageMode);
        if (!cancelled) {
          setQuestion(q);
          setCardLoading(false);
        }
      } catch {
        if (!cancelled) {
          setCardLoading(false);
          setCardError(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, stageLevel, stageMode, seq, finished]);

  /** Recarga estadísticas (anillos) y fuerza el refresco de los paneles. */
  function refreshAfterAttempt() {
    if (!userId) return;
    setRefreshNonce((n) => n + 1);
  }

  /** Pide la siguiente pregunta del mismo bucket (avanzar / saltar). */
  function nextCard() {
    setResult(null);
    setAttemptError(null);
    setSeq((s) => s + 1);
  }

  // --- Acciones de sesión (panel de nivel) -----------------------------------

  function startSession(next: RouteSession) {
    setResult(null);
    setAttemptError(null);
    setSeq((s) => s + 1);
    setSession(next);
  }

  function exitSession() {
    setSession(null);
    setResult(null);
    setAttemptError(null);
    setRefreshNonce((n) => n + 1);
    setSeq((s) => s + 1);
  }

  /** Avanza tras ver el resultado de una pregunta (o acaba la sesión). */
  function advance(passed: boolean, answeredItemId?: string) {
    if (!session) {
      // Práctica libre (sin sesión): simplemente siguiente pregunta.
      onAttempt();
      nextCard();
      return;
    }
    let next: RouteSession;
    if (session.mode === "drill") {
      next = {
        ...session,
        remaining: drillAnswered(
          session.remaining,
          answeredItemId ??
            (question as RouteQuestion | null)?.check_id ??
            "",
          passed,
        ),
      };
    } else {
      next = { ...session, done: session.done + 1 };
    }
    onAttempt();
    refreshAfterAttempt();
    if (isSessionFinished(next)) {
      setSession(next);
      setResult(null);
      return;
    }
    setSession(next);
    nextCard();
  }

  /** Envía la respuesta (MC o producción controlada) y muestra el feedback. */
  async function submit(answer: { optionIndex: number; typed?: string }) {
    if (!userId || !question || busy) return;
    const q = question as RouteQuestion | null;
    if (!q) return;
    if (q.type === "controlled_production" && !answer.typed?.trim()) return;
    setBusy(true);
    setAttemptError(null);
    try {
      const attempt = await config.api.submitAttempt(
        userId,
        q.check_id,
        answer.optionIndex,
        answer.typed?.trim() ?? "",
      );
      setResult(attempt);
      refreshAfterAttempt();
      onAttempt();
    } catch (e) {
      setAttemptError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function pick(optionIndex: number) {
    void submit({ optionIndex });
  }

  function pickTyped(typed: string) {
    void submit({ optionIndex: -1, typed });
  }

  // --- Vistas alternas (assessment / dictionary) ------------------------------
  if (loadError) {
    return (
      <section className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center gap-3 px-4 py-16 text-center">
        <p className="text-sm text-destructive">{t(nk("loadError"))}</p>
        <Button
          type="button"
          variant="outline"
          onClick={() => setRefreshNonce((n) => n + 1)}
        >
          {t(nk("retry"))}
        </Button>
      </section>
    );
  }

  if (config.requireUser && !userId) {
    return (
      <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        {t(nk("loading"))}
      </div>
    );
  }

  if (view.kind === "dictionary" && config.dictionary) {
    const DictView = config.dictionary.View;
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex shrink-0 items-center gap-2 border-b border-border bg-background/90 px-2 py-1.5 backdrop-blur">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="min-h-9 shrink-0 gap-1 px-2 text-sm font-medium"
            onClick={() => setView({ kind: "routes" })}
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            {t(nk("backRoutes"))}
          </Button>
          <span className="text-xs text-muted-foreground">
            {t(config.dictionary.hintKey)}
          </span>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <DictView userId={userId} />
        </div>
      </div>
    );
  }

  if (view.kind === "assessment" && config.assessment === "speaking") {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex shrink-0 items-center gap-2 border-b border-border bg-background/90 px-2 py-1.5 backdrop-blur">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="min-h-9 shrink-0 gap-1 px-2 text-sm font-medium"
            onClick={() => setView({ kind: "routes" })}
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            {t(nk("backRoutes"))}
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <SpeakingAssessment
            userId={userId}
            onAttempt={onAttempt}
            onNext={onNext}
          />
        </div>
      </div>
    );
  }

  if (view.kind === "assessment") {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex shrink-0 items-center gap-2 border-b border-border bg-background/90 px-2 py-1.5 backdrop-blur">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="min-h-9 shrink-0 gap-1 px-2 text-sm font-medium"
            onClick={() => setView({ kind: "routes" })}
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            {t(nk("backRoutes"))}
          </Button>
          <span className="text-xs text-muted-foreground">
            {t(nk("formalTitle")).replace("{level}", view.level)}
          </span>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
            <div className="mb-4 flex flex-col gap-1.5">
              <h1 className="text-lg font-bold tracking-tight">
                {t(nk("formalTitle")).replace("{level}", view.level)}
              </h1>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {t(nk("formalNote"))}
              </p>
            </div>
            <AssessmentLadder
              userId={userId}
              levelId={view.level.toLowerCase()}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center gap-2 border-b border-border bg-background/90 px-2 py-1.5 backdrop-blur">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="min-h-9 shrink-0 gap-1 px-2 text-sm font-medium"
          onClick={onBack}
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          {t("learn.back")}
        </Button>
        <LearnActivitySwitcher active={active} />
        {config.dictionary && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="ml-auto min-h-9 shrink-0 gap-1 px-2 text-sm font-medium"
            onClick={() => setView({ kind: "dictionary" })}
          >
            <BookOpen className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">{t(config.dictionary.ctaKey)}</span>
          </Button>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
          <header className="mb-6">
            {modeTabs && modeTabs.length > 0 && (
              <div
                role="group"
                aria-label={t("learn.pickMode")}
                className="mb-4 flex flex-wrap items-center gap-1.5"
              >
                {modeTabs.map((tab) => {
                  const isActive = tab.id === modeTab;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => onModeChange?.(tab.id)}
                      aria-pressed={isActive}
                      className={cn(
                        "inline-flex min-h-9 items-center rounded-full border px-3.5 text-xs font-semibold whitespace-nowrap transition-colors",
                        isActive
                          ? "cursor-default border-primary/60 bg-primary/10 text-primary"
                          : "border-border text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                      )}
                    >
                      {t(tab.labelKey)}
                    </button>
                  );
                })}
              </div>
            )}
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
              {t(config.skillTitleKey)}
            </h1>
            <p className="mt-1.5 text-muted-foreground">{t(config.subtitleKey)}</p>
            <div className="mt-2">
              <button
                type="button"
                onClick={() => setRoutesInfoOpen((open) => !open)}
                aria-expanded={routesInfoOpen}
                aria-controls="routes-info-copy"
                className="inline-flex min-h-8 items-center gap-1.5 rounded-full border border-border bg-muted/30 px-2.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
              >
                <Info className="size-3.5 shrink-0" aria-hidden="true" />
                {t("learn.routesInfoToggle")}
                <ChevronDown
                  className={cn(
                    "size-3.5 shrink-0 transition-transform",
                    routesInfoOpen && "rotate-180",
                  )}
                  aria-hidden="true"
                />
              </button>
              {routesInfoOpen && (
                <p
                  id="routes-info-copy"
                  className="mt-2 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs leading-relaxed text-muted-foreground"
                >
                  {t(nk("routesSubtitle"))}
                </p>
              )}
            </div>
          </header>

          {!stats ? (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              {t(nk("loading"))}
            </div>
          ) : (
            <div className="flex flex-col gap-5">
              {/* ---- Escenario de práctica superior (página única) ---- */}
              {finished && session ? (
                <ActivityResult outcome="ok" title={t(nk("sessionEnded"))}>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {session.mode === "drill"
                      ? t(nk("doneDrillLine"))
                          .replace("{total}", String(session.total))
                          .replace("{level}", session.level)
                      : session.mode === "mastered"
                        ? t(nk("doneReviewLine"))
                            .replace("{total}", String(session.total))
                            .replace("{level}", session.level)
                        : t(nk("doneLevelLine"))
                            .replace("{total}", String(session.total))
                            .replace("{level}", session.level)}
                  </p>
                  <div className="pt-1">
                    <Button type="button" onClick={exitSession}>
                      {t(nk("backRoutes"))}
                    </Button>
                  </div>
                </ActivityResult>
              ) : (
                <>
                  {session && (
                    <Card className="flex flex-row flex-wrap items-center justify-between gap-3 p-3">
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <Badge variant="secondary">
                          {session.mode === "drill"
                            ? t(nk("modeDrill"))
                            : session.mode === "mastered"
                              ? t(nk("modeReview")).replace(
                                  "{level}",
                                  session.level,
                                )
                              : t(nk("modeLevel")).replace(
                                  "{level}",
                                  session.level,
                                )}
                        </Badge>
                        <Badge variant="outline" className="tabular-nums">
                          {sessionDone(session)} / {session.total}
                        </Badge>
                        <span className="text-muted-foreground">
                          {session.mode === "drill"
                            ? t(nk("drillHint"))
                            : t(nk("sessionHint"))}
                        </span>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={exitSession}
                      >
                        {t(nk("exitSession"))}
                      </Button>
                    </Card>
                  )}

                  {config.scene ? (
                    (() => {
                      const LearnScene = config.scene;
                      return (
                        <LearnScene
                          key={`scene-${seq}`}
                          userId={userId}
                          ns={ns}
                          t={t}
                          item={question}
                          itemLoading={cardLoading}
                          itemError={cardError}
                          finished={finished}
                          sessionActive={session !== null}
                          onReport={() => {
                            refreshAfterAttempt();
                            onAttempt();
                          }}
                          onAnswered={(itemId, passed) =>
                            advance(passed, itemId)
                          }
                          onSkip={nextCard}
                        />
                      );
                    })()
                  ) : (
                    <PracticeCard
                      key={(question as RouteQuestion | null)?.check_id ?? "none"}
                      ns={ns}
                      question={question as RouteQuestion | null}
                      cardLoading={cardLoading}
                      cardError={cardError}
                      result={result}
                      busy={busy}
                      attemptError={attemptError}
                      onPick={pick}
                      onSubmitTyped={pickTyped}
                      onAdvance={() => {
                        if (!session && !result) {
                          nextCard();
                          return;
                        }
                        if (result) advance(result.passed);
                      }}
                      onSkip={nextCard}
                      sessionActive={session !== null}
                      t={t}
                    />
                  )}
                </>
              )}

              {/* ---- Rutas A1–C2 (mapa de práctica, espejo de las demás) ---- */}
              <QuizRoutesSection
                ns={ns}
                ariaLevelItemsId={config.ariaLevelItemsId}
                LevelPanel={config.LevelPanel}
                userId={userId}
                stats={stats}
                statsCompetenceKey={config.statsCompetenceKey}
                showAssessed={config.loadAssessed !== undefined}
                assessedLevel={assessedLevel}
                expandedLevel={expandedLevel}
                setExpandedLevel={setExpandedLevel}
                disabled={session !== null}
                refreshNonce={refreshNonce}
                onStartSession={startSession}
                onDemonstrate={(level) =>
                  setView({ kind: "assessment", level })
                }
              />

              {config.trailing && <config.trailing userId={userId} />}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Mapa de rutas compartido                                             */
/* ------------------------------------------------------------------ */

interface QuizRoutesSectionProps {
  ns: string;
  ariaLevelItemsId: string;
  LevelPanel: ComponentType<RouteLevelPanelProps>;
  userId: string | null;
  stats: RouteStats;
  /** V3.21 (V20-03/04): competencia real del modo para etiquetar las stats. */
  statsCompetenceKey?: string;
  /** Muestra el nivel oral demostrado (destrezas orales). */
  showAssessed: boolean;
  assessedLevel: string | null;
  expandedLevel: string | null;
  setExpandedLevel: (level: string | null) => void;
  disabled: boolean;
  refreshNonce: number;
  onStartSession: (session: RouteSession) => void;
  onDemonstrate: (level: string) => void;
}

/** Mapa de rutas: resumen + tira de anillos + panel del nivel. */
function QuizRoutesSection({
  ns,
  ariaLevelItemsId,
  LevelPanel,
  userId,
  stats,
  statsCompetenceKey,
  showAssessed,
  assessedLevel,
  expandedLevel,
  setExpandedLevel,
  disabled,
  refreshNonce,
  onStartSession,
  onDemonstrate,
}: QuizRoutesSectionProps) {
  const { t } = useI18n();
  const nk = (key: string) => `${ns}.${key}`;

  return (
    <Card className="gap-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-0.5 text-xs">
          <span className="font-semibold uppercase tracking-wide text-muted-foreground">
            {t(nk("routesMapTitle"))}
          </span>
          <span className="text-muted-foreground">
            {t(nk("routesMapHint"))}
          </span>
          {statsCompetenceKey && (
            <span className="mt-1 w-fit rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-primary">
              {t(statsCompetenceKey)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <ProgressRing
            value={stats.accuracy ?? 0}
            size={58}
            strokeWidth={6}
            ariaLabel={`${t(nk("accuracy"))}: ${
              stats.accuracy !== null ? `${stats.accuracy}%` : "—"
            }`}
          >
            <span className="text-xs font-bold tabular-nums text-foreground">
              {stats.accuracy !== null ? `${Math.round(stats.accuracy)}%` : "—"}
            </span>
          </ProgressRing>
          <div className="flex flex-col gap-0.5 text-xs">
            <span className="font-semibold text-foreground">
              {t(nk("accuracy"))}
            </span>
            <span className="tabular-nums text-muted-foreground">
              {stats.passed} {t("assessment.of")} {stats.attempts}
            </span>
            {showAssessed &&
              (assessedLevel ? (
                <Badge variant="outline" className="mt-1 w-fit gap-1">
                  <Award className="size-3.5" aria-hidden="true" />
                  {t(nk("assessedLevel")).replace(
                    "{level}",
                    assessedLevel,
                  )}
                </Badge>
              ) : (
                <span className="mt-0.5 text-muted-foreground">
                  {t(nk("assessedLevelNone"))}
                </span>
              ))}
          </div>
        </div>
      </div>

      <p className="border-t border-border pt-3 text-xs leading-relaxed text-muted-foreground">
        {t(nk("routeNote")).replace("{level}", stats.level)}
      </p>
      <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
        {t(nk("routeCertNote"))}
      </p>

      <div className="flex flex-col border-t border-border pt-4">
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {t(nk("routeRingHelp"))}
        </p>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
          {stats.levels.map((lv) => {
            const expanded = expandedLevel === lv.level;
            const pct = lv.completed
              ? 100
              : lv.total > 0
                ? (lv.mastered / lv.total) * 100
                : 0;
            return (
              <button
                key={lv.level}
                type="button"
                onClick={() => setExpandedLevel(expanded ? null : lv.level)}
                aria-expanded={expanded}
                aria-controls={ariaLevelItemsId}
                aria-label={t(nk("levelHistoryTitle")).replace(
                  "{level}",
                  lv.level,
                )}
                disabled={disabled}
                className={cn(
                  "flex flex-col items-center gap-1.5 rounded-lg p-1.5 transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                  expanded && "bg-accent",
                  disabled && "cursor-not-allowed opacity-60",
                )}
              >
                <ProgressRing
                  value={pct}
                  size={46}
                  strokeWidth={5}
                  className={
                    lv.completed
                      ? "text-success"
                      : lv.mastered > 0
                        ? "text-primary"
                        : "text-muted-foreground"
                  }
                  ariaLabel={t(nk("masteredOfTotal"))
                    .replace("{mastered}", String(lv.mastered))
                    .replace("{total}", String(lv.total))}
                >
                  {lv.completed ? (
                    <Check className="size-4" aria-hidden="true" />
                  ) : (
                    <span className="text-[11px] font-semibold tabular-nums text-foreground">
                      {lv.level}
                    </span>
                  )}
                </ProgressRing>
                <span className="text-[10px] font-medium text-muted-foreground">
                  {lv.completed ? lv.level : ""}
                </span>
                <span className="text-[10px] font-semibold tabular-nums text-foreground">
                  {t(nk("masteredOfTotal"))
                    .replace("{mastered}", String(lv.mastered))
                    .replace("{total}", String(lv.total))}
                </span>
                {lv.total > 0 && lv.mastered > 0 && !lv.completed && (
                  <span className="text-[10px] tabular-nums text-muted-foreground">
                    {t(nk("coveragePct")).replace(
                      "{pct}",
                      String(Math.round((lv.mastered / lv.total) * 100)),
                    )}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {expandedLevel !== null && !disabled && (
          <div
            id={ariaLevelItemsId}
            className="mt-4 border-t border-border pt-4"
          >
            <LevelPanel
              userId={userId}
              level={expandedLevel}
              routeState={
                (
                  stats.levels.find((lv) => lv.level === expandedLevel) as
                    | { state?: "not_started" | "developing" | "functional" }
                    | undefined
                )?.state
              }
              assessedLevel={showAssessed ? assessedLevel : null}
              disabled={disabled}
              refreshNonce={refreshNonce}
              onPracticeLevel={(level, total) =>
                onStartSession({ mode: "level", level, total, done: 0 })
              }
              onDrillFailed={(level, failedIds) =>
                onStartSession({
                  mode: "drill",
                  level,
                  total: failedIds.length,
                  remaining: failedIds,
                })
              }
              onReviewLearned={(level, total) =>
                onStartSession({ mode: "mastered", level, total, done: 0 })
              }
              onDemonstrate={onDemonstrate}
            />
          </div>
        )}
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Tarjeta del escenario (MC + producción controlada)                   */
/* ------------------------------------------------------------------ */

interface PracticeCardProps {
  ns: string;
  question: RouteQuestion | null;
  cardLoading: boolean;
  cardError: boolean;
  result: RouteAttempt | null;
  busy: boolean;
  attemptError: string | null;
  onPick: (optionIndex: number) => void;
  /** Envía una respuesta escrita (producción controlada, V3.13 P1). */
  onSubmitTyped: (answer: string) => void;
  /** Continuar tras un resultado (avanza la sesión) o saltar sin responder. */
  onAdvance: () => void;
  onSkip: () => void;
  sessionActive: boolean;
  t: TranslateFn;
}

/** Tarjeta del escenario (arriba, siempre visible): MC o producción controlada. */
function PracticeCard({
  ns,
  question,
  cardLoading,
  cardError,
  result,
  busy,
  attemptError,
  onPick,
  onSubmitTyped,
  onAdvance,
  onSkip,
  sessionActive,
  t,
}: PracticeCardProps) {
  const [typedValue, setTypedValue] = useState("");
  const isTyped = question?.type === "controlled_production";
  const nk = (key: string) => `${ns}.${key}`;

  if (cardLoading || !question) {
    return (
      <Card className="p-8">
        <p className="flex items-center justify-center gap-2 text-center text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          {t(nk("loading"))}
        </p>
      </Card>
    );
  }

  if (cardError) {
    return (
      <Card className="flex flex-col items-center gap-3 p-6 text-center">
        <p className="text-sm text-destructive">{t(nk("loadError"))}</p>
        <Button type="button" variant="outline" onClick={onAdvance}>
          {t(nk("retry"))}
        </Button>
      </Card>
    );
  }

  if (result) {
    if (result.type === "controlled_production") {
      const ok = result.passed;
      const expected = result.expected_answers ?? [];
      return (
        <Card className="gap-4 p-5 sm:p-6">
          <ActivityResult
            outcome={ok ? "ok" : "ko"}
            title={`${ok ? t(nk("resultPassed")) : t(nk("resultNotPassed"))}`}
            footer={
              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" onClick={onAdvance}>
                  {t(nk("continue"))}
                </Button>
              </div>
            }
          >
            <header className="flex flex-wrap items-center gap-2">
              <Badge variant={ok ? "default" : "destructive"}>
                {ok ? t(nk("resultPassed")) : t(nk("resultNotPassed"))}
              </Badge>
              <Badge variant="outline" className="text-[10px] normal-case">
                {t(nk("typeIn"))}
              </Badge>
              <span className="text-sm text-muted-foreground">
                {t(nk("resultScore")).replace(
                  "{score}",
                  String(Math.round(result.score)),
                )}
              </span>
            </header>

            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t(nk("questionLabel"))}
              </span>
              <p
                className="rounded-lg border border-border bg-secondary/20 px-3 py-2 text-sm font-medium leading-relaxed text-foreground"
                lang="en"
              >
                {result.prompt}
              </p>
            </div>

            <div className="flex flex-col gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t(nk("typedYourAnswer"))}
              </span>
              <p
                className={cn(
                  "rounded-lg border px-3 py-2 text-sm leading-relaxed",
                  ok
                    ? "border-success/40 bg-success/10 text-success"
                    : "border-destructive/40 bg-destructive/10 text-destructive",
                )}
                lang="en"
              >
                {result.typed_answer?.trim() || "—"}
              </p>
            </div>

            {expected.length > 0 && (
              <div className="flex flex-col gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {t(nk("typedExpected"))}
                </span>
                <ul
                  className="flex flex-col gap-1.5"
                  aria-label={t(nk("typedExpected"))}
                >
                  {expected.map((answer) => (
                    <li
                      key={answer}
                      className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm text-foreground"
                    >
                      <Check
                        className="size-3.5 shrink-0 text-success"
                        aria-hidden="true"
                      />
                      <span lang="en">{answer}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <p className="text-[11px] leading-relaxed text-muted-foreground">
              {t(nk("resultHonestNote"))}
            </p>
          </ActivityResult>
        </Card>
      );
    }

    const reveal = (index: number): { tone: string; mark: ReactNode } => {
      if (index === result.correct_index) {
        return {
          tone: "border-success/40 bg-success/10 text-success",
          mark: <Check className="size-3.5 shrink-0" aria-hidden="true" />,
        };
      }
      if (index === result.selected_index) {
        return {
          tone: "border-destructive/40 bg-destructive/10 text-destructive",
          mark: <X className="size-3.5 shrink-0" aria-hidden="true" />,
        };
      }
      return { tone: "border-border", mark: null };
    };

    return (
      <Card className="gap-4 p-5 sm:p-6">
        <ActivityResult
          outcome={result.passed ? "ok" : "ko"}
          title={`${result.passed ? t(nk("resultPassed")) : t(nk("resultNotPassed"))}`}
          footer={
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" onClick={onAdvance}>
                {t(nk("continue"))}
              </Button>
            </div>
          }
        >
          <header className="flex flex-wrap items-center gap-2">
            <Badge variant={result.passed ? "default" : "destructive"}>
              {result.passed
                ? t(nk("resultPassed"))
                : t(nk("resultNotPassed"))}
            </Badge>
            <span className="text-sm text-muted-foreground">
              {t(nk("resultScore")).replace(
                "{score}",
                String(Math.round(result.score)),
              )}
            </span>
          </header>

          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {t(nk("questionLabel"))}
            </span>
            <p
              className="rounded-lg border border-border bg-secondary/20 px-3 py-2 text-sm font-medium leading-relaxed text-foreground"
              lang="en"
            >
              {result.prompt}
            </p>
          </div>

          <ul
            className="flex flex-col gap-1.5"
            aria-label={t(nk("answerLabel"))}
          >
            {result.options.map((option, idx) => {
              const revealState = reveal(idx);
              return (
                <li
                  key={`${result.check_id}-${idx}`}
                  className={cn(
                    "flex items-center gap-2 rounded-lg border px-3 py-2 text-sm",
                    revealState.tone,
                  )}
                >
                  <span
                    className={cn(
                      "flex size-5 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold",
                      idx === result.correct_index
                        ? "border-success/50 text-success"
                        : idx === result.selected_index
                          ? "border-destructive/50 text-destructive"
                          : "border-border text-muted-foreground",
                    )}
                  >
                    {String.fromCharCode(65 + idx)}
                  </span>
                  <span className="flex-1 text-foreground" lang="en">
                    {option}
                  </span>
                  {revealState.mark}
                </li>
              );
            })}
          </ul>

          <p className="text-[11px] leading-relaxed text-muted-foreground">
            {t(nk("resultHonestNote"))}
          </p>
        </ActivityResult>
      </Card>
    );
  }

  return (
    <Card className="gap-4 p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[10px] normal-case">
            {question.topic.replace(/_/g, " ")}
          </Badge>
          <Badge variant="secondary">{question.level}</Badge>
          {isTyped && (
            <Badge
              variant="outline"
              className="text-[10px] normal-case text-primary"
            >
              {t(nk("typeIn"))}
            </Badge>
          )}
        </div>
        <span className="text-[11px] text-muted-foreground">
          {isTyped ? t(nk("typedHint")) : t(nk("pickHint"))}
        </span>
      </div>

      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {t(nk("questionLabel"))}
        </span>
        <p
          className="rounded-xl border border-border bg-secondary/30 px-4 py-3.5 text-base font-medium leading-relaxed text-foreground sm:text-lg"
          lang="en"
        >
          {question.prompt}
        </p>
      </div>

      {attemptError && (
        <div
          role="alert"
          className="flex flex-col items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-center text-xs text-destructive"
        >
          <p className="break-words">{attemptError}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => undefined}
          >
            {t(nk("retry"))}
          </Button>
        </div>
      )}

      {isTyped ? (
        <div className="flex flex-col gap-2">
          <label
            htmlFor={`${ns}-typed-answer`}
            className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
          >
            {t(nk("typedAnswerLabel"))}
          </label>
          <input
            id={`${ns}-typed-answer`}
            type="text"
            lang="en"
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck={false}
            value={typedValue}
            disabled={busy}
            onChange={(e) => setTypedValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && typedValue.trim() && !busy) {
                onSubmitTyped(typedValue);
              }
            }}
            placeholder={t(nk("typedPlaceholder"))}
            className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-base text-foreground transition-colors placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-wait disabled:opacity-60"
          />
          <div className="flex justify-end">
            <Button
              type="button"
              onClick={() => onSubmitTyped(typedValue)}
              disabled={busy || !typedValue.trim()}
            >
              {t(nk("typedSubmit"))}
            </Button>
          </div>
        </div>
      ) : (
        <ul
          className="flex flex-col gap-1.5"
          aria-label={t(nk("answerLabel"))}
        >
          {question.options.map((option, idx) => (
            <li key={`${question.check_id}-${idx}`}>
              <button
                type="button"
                disabled={busy}
                onClick={() => onPick(idx)}
                className="group flex w-full items-center gap-2.5 rounded-lg border border-border px-3 py-2.5 text-left text-sm text-foreground transition-colors hover:border-primary/50 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-wait disabled:opacity-60"
              >
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-border text-[11px] font-semibold text-muted-foreground transition-colors group-hover:border-primary/50 group-hover:text-primary">
                  {String.fromCharCode(65 + idx)}
                </span>
                <span className="flex-1" lang="en">
                  {option}
                </span>
                <ChevronRight
                  className="size-4 shrink-0 text-muted-foreground/60 transition-transform group-hover:translate-x-0.5"
                  aria-hidden="true"
                />
              </button>
            </li>
          ))}
        </ul>
      )}

      {busy && (
        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          {t(nk("evaluating"))}
        </p>
      )}

      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-[11px] leading-relaxed text-muted-foreground">
          <GraduationCap className="size-3.5 shrink-0" aria-hidden="true" />
          {t(nk("pickNote"))}
        </p>
        {!sessionActive && !busy && (
          <Button type="button" variant="ghost" size="sm" onClick={onSkip}>
            {t(nk("skip"))}
          </Button>
        )}
      </div>
    </Card>
  );
}
