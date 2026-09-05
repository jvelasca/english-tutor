/**
 * Sesiones de práctica de Conversation por rutas (V3.10).
 *
 * V3.13 P2.1: la máquina de sesión (level/drill/mastered) es compartida por las
 * seis rutas; este módulo re-exporta la implementación única para no romper los
 * imports y tests existentes.
 */
import {
  drillAnswered,
  drillDone,
  isSessionFinished,
  sessionDone,
  type RouteSession,
} from "../routes/routeSession";

export type ConversationSession = RouteSession;

export { drillAnswered, drillDone, isSessionFinished, sessionDone };
