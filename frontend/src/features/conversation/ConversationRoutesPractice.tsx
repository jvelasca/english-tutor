/**
 * APRENDER → Conversation por rutas (V3.10), migrada al marco compartido de
 * quiz (V3.13 P2.1, wave 2).
 *
 * La página única con scroll (estadísticas, máquina de sesión, mapa A1–C2,
 * panel del nivel y acceso al Speaking Assessment) vive en
 * `features/routes/QuizRoutePage.tsx`. Este archivo aporta la configuración
 * (namespace i18n, API, panel), la **escena personalizada del mini-diálogo
 * guiado** (chat del tutor vía SSE y evaluación del transcripto) y la tarjeta
 * de acceso a la conversación libre en /chat.
 */
import { useRef, useState } from "react";
import { Loader2, MessageSquareText } from "lucide-react";
import type { LearnActivity } from "../../router/learnHub";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { ActivityResult } from "../../components/ActivityResult";
import { SkillBar } from "../../components/SkillBar";
import { useI18n } from "../../hooks/useI18n";
import { criterionLabel } from "../../utils/speaking";
import { navigateTo } from "../../router/hash";
import { CHAT_PATH } from "../../router/paths";
import {
  getConversationQuestion,
  getConversationStats,
  submitConversationAttempt,
} from "../../api/conversationRoutes";
import { getSpeakingLevel } from "../../api/academy";
import type {
  ConversationAttempt,
  ConversationDialogue,
  NextBestActivity,
} from "../../types/api";
import type { Section } from "../../utils/sections";
import {
  QuizRoutePage,
  type LearnSceneProps,
  type RouteQuizConfig,
} from "../routes/QuizRoutePage";
import { ConversationLevelPanel } from "./ConversationLevelPanel";
import { ConversationGuidedChat } from "./ConversationGuidedChat";

/* ------------------------------------------------------------------ */
/* Config de la destreza                                                */
/* ------------------------------------------------------------------ */

const CONVERSATION_ROUTE_CONFIG: RouteQuizConfig = {
  ns: "convRoutes",
  skillTitleKey: "skill.conversation",
  subtitleKey: "learn.conversationSubtitle",
  ariaLevelItemsId: "conversation-level-items",
  assessment: "speaking",
  requireUser: true,
  loadAssessed: (userId) =>
    getSpeakingLevel(userId).then((r) => r.level ?? null),
  LevelPanel: ConversationLevelPanel,
  scene: ConversationScene,
  trailing: FreeChatCard,
  api: {
    getStats: (userId) => getConversationStats(userId),
    getQuestion: (userId, level, mode) =>
      getConversationQuestion(userId, level, mode),
    submitAttempt: () =>
      Promise.reject(
        new Error(
          "conversación guiada no usa /attempt directo: la escena evalúa el transcripto por su API.",
        ),
      ),
  },
};

interface ConversationRoutesPracticeProps {
  userId: string | null;
  /** Actividad activa (Conversation) para el atajo de la franja superior. */
  active: LearnActivity;
  /** Navega de vuelta al hub de APRENDER (`#/aprender`). */
  onBack: () => void;
  /** La práctica registra un intento puntuado: el padre refresca métricas. */
  onAttempt: () => void;
  /** Recomendación de "siguiente mejor actividad" al terminar el examen. */
  onNext: (section: Section | null, step: NextBestActivity) => void;
}

export function ConversationRoutesPractice(
  props: ConversationRoutesPracticeProps,
) {
  return (
    <QuizRoutePage
      userId={props.userId}
      active={props.active}
      onBack={props.onBack}
      onAttempt={props.onAttempt}
      onNext={props.onNext}
      config={CONVERSATION_ROUTE_CONFIG}
    />
  );
}

/* ------------------------------------------------------------------ */
/* Escena de mini-diálogo guiado (vive en la página compartida)         */
/* ------------------------------------------------------------------ */

/**
 * Escena superior de conversation: mini-diálogo guiado multi-turno con el
 * tutor. La conversación, su evaluación (LLM local + señal objetiva) y el
 * resultado son estado local; la página avanza la sesión cuando el alumno
 * pulsa Continuar.
 */
export function ConversationScene({
  userId,
  item,
  itemLoading,
  itemError,
  sessionActive,
  onReport,
  onAnswered,
  onSkip,
}: LearnSceneProps) {
  const dialogue = item as ConversationDialogue | null;
  const [chatStarted, setChatStarted] = useState(false);
  const [result, setResult] = useState<ConversationAttempt | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [evaluateError, setEvaluateError] = useState<string | null>(null);
  const lastConvIdRef = useRef<string | null>(null);

  async function submitEvaluation() {
    const convId = lastConvIdRef.current;
    if (!userId || !dialogue || !convId || evaluating) return;
    setEvaluating(true);
    setEvaluateError(null);
    try {
      const att = await submitConversationAttempt(userId, dialogue.id, convId);
      setResult(att);
      setChatStarted(false);
      onReport();
    } catch (e) {
      setEvaluateError((e as Error).message);
    } finally {
      setEvaluating(false);
    }
  }

  // La página no renderiza esta escena sin perfil activo (requireUser).
  if (!userId) return null;

  return (
    <ConversationPracticeCard
      userId={userId}
      dialogue={dialogue}
      cardLoading={itemLoading}
      cardError={itemError}
      chatStarted={chatStarted}
      onStarted={() => setChatStarted(true)}
      evaluating={evaluating}
      evaluateError={evaluateError}
      result={result}
      sessionActive={sessionActive}
      onFinished={(convId) => {
        lastConvIdRef.current = convId;
        void submitEvaluation();
      }}
      onRetryEvaluation={() => void submitEvaluation()}
      onContinue={() => {
        if (dialogue && result) onAnswered(dialogue.id, result.passed);
      }}
      onSkip={onSkip}
    />
  );
}

interface ConversationPracticeCardProps {
  userId: string;
  dialogue: ConversationDialogue | null;
  cardLoading: boolean;
  cardError: boolean;
  /** El alumno ya ha enviado al menos un turno: no se puede saltar. */
  chatStarted: boolean;
  onStarted: () => void;
  evaluating: boolean;
  evaluateError: string | null;
  result: ConversationAttempt | null;
  sessionActive: boolean;
  /** El mini-chat ha terminado y deja el `conversation_id` para evaluar. */
  onFinished: (conversationId: string) => void;
  onRetryEvaluation: () => void;
  /** Continuar tras un resultado (avanza la sesión) o saltar sin conversar. */
  onContinue: () => void;
  onSkip: () => void;
}

/** Tarjeta del escenario de conversación guiada (arriba, siempre visible). */
function ConversationPracticeCard({
  userId,
  dialogue,
  cardLoading,
  cardError,
  chatStarted,
  onStarted,
  evaluating,
  evaluateError,
  result,
  sessionActive,
  onFinished,
  onRetryEvaluation,
  onContinue,
  onSkip,
}: ConversationPracticeCardProps) {
  const { t } = useI18n();

  if (cardLoading || !dialogue) {
    return (
      <Card className="p-8">
        <p className="flex items-center justify-center gap-2 text-center text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          {t("convRoutes.loading")}
        </p>
      </Card>
    );
  }

  if (cardError) {
    return (
      <Card className="flex flex-col items-center gap-3 p-6 text-center">
        <p className="text-sm text-destructive">{t("convRoutes.loadError")}</p>
        <Button type="button" variant="outline" onClick={onSkip}>
          {t("convRoutes.retry")}
        </Button>
      </Card>
    );
  }

  // Evaluación en curso (el transcripto completo se puntúa con el LLM local).
  if (evaluating) {
    return (
      <Card className="flex flex-col items-center gap-3 p-8 text-center">
        <Loader2 className="size-6 animate-spin text-primary" aria-hidden="true" />
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <MessageSquareText className="size-4" aria-hidden="true" />
          {t("convRoutes.evaluating")}
        </p>
      </Card>
    );
  }

  // Resultado de la conversación terminada.
  if (result) {
    const criteria = Object.entries(result.criteria).filter(
      (entry): entry is [string, number] =>
        entry[1] !== null && entry[1] !== undefined,
    );
    return (
      <Card className="gap-4 p-5 sm:p-6">
        <ActivityResult
          outcome={result.passed ? "ok" : "ko"}
          title={`${t("convRoutes.resultTitle")} · ${Math.round(
            result.overall * 100,
          )}/100`}
          footer={
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" onClick={onContinue}>
                {t("convRoutes.continue")}
              </Button>
            </div>
          }
        >
          <header className="flex flex-wrap items-center gap-2">
            <Badge variant={result.passed ? "default" : "destructive"}>
              {result.passed
                ? t("convRoutes.resultPassed")
                : t("convRoutes.resultNotPassed")}
            </Badge>
            <Badge variant="outline">{result.level}</Badge>
            <span className="text-xs text-muted-foreground">
              {result.topic.replace(/_/g, " ")}
            </span>
          </header>

          {result.heard && (
            <div className="flex flex-col gap-1 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs">
              <span className="font-semibold text-muted-foreground">
                {t("convRoutes.transcriptLabel")}
              </span>
              <span className="leading-relaxed text-foreground" lang="en">
                {result.heard}
              </span>
            </div>
          )}

          {result.communicative_goals.length > 0 && (
            <div className="flex flex-col gap-1 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs">
              <span className="font-semibold text-muted-foreground">
                {t("convRoutes.goalsLabel")}
              </span>
              <ul className="flex flex-col gap-1 text-foreground">
                {result.communicative_goals.map((goal) => (
                  <li key={`${result.dialogue_id}-${goal}`}>• {goal}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-col gap-2.5">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {t("convRoutes.criteriaTitle")}
            </p>
            {criteria.map(([name, value]) => (
              <SkillBar
                key={name}
                label={criterionLabel(name)}
                value={value}
                hint={`${Math.round(value * 100)}%`}
              />
            ))}
          </div>

          <p className="text-[11px] leading-relaxed text-muted-foreground">
            {t("convRoutes.resultHonestNote")}
          </p>
        </ActivityResult>
      </Card>
    );
  }

  return (
    <Card className="gap-4 p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{dialogue.level}</Badge>
          <span className="text-muted-foreground">
            {t("convRoutes.practiceHint")}
          </span>
        </div>
        {!chatStarted && !sessionActive && (
          <Button type="button" variant="ghost" size="sm" onClick={onSkip}>
            {t("convRoutes.skip")}
          </Button>
        )}
      </div>

      <ConversationGuidedChat
        key={dialogue.id}
        userId={userId}
        dialogue={dialogue}
        onFirstMessage={onStarted}
        onFinish={(_heard, _durationSeconds, conversationId) =>
          onFinished(conversationId)
        }
      />

      {evaluateError && (
        <div
          role="alert"
          className="flex flex-col items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-center text-xs text-destructive"
        >
          <p className="break-words">{evaluateError}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onRetryEvaluation}
          >
            {t("convRoutes.retry")}
          </Button>
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Tarjeta de conversación libre (tras el mapa de rutas)                */
/* ------------------------------------------------------------------ */

/** Acceso a la conversación libre con el tutor (ruta /chat). */
function FreeChatCard() {
  const { t } = useI18n();
  return (
    <Card className="flex flex-col gap-2 border-dashed p-4">
      <p className="flex items-center gap-2 text-xs font-semibold text-foreground">
        <MessageSquareText className="size-4" aria-hidden="true" />
        {t("convRoutes.freeChatTitle")}
      </p>
      <p className="text-[11px] leading-relaxed text-muted-foreground">
        {t("convRoutes.freeChatNote")}
      </p>
      <div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="min-h-8 gap-1.5"
          onClick={() => navigateTo(CHAT_PATH)}
        >
          <MessageSquareText className="size-3.5" aria-hidden="true" />
          {t("convRoutes.freeChatCta")}
        </Button>
      </div>
    </Card>
  );
}
