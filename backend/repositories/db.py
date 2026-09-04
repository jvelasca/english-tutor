"""Infraestructura de datos: conexión, esquema y migraciones (SQLite, 100% local)."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone

from config import DATA_DIR

DB_PATH = DATA_DIR / "tutor.db"

DEFAULT_USER_NAME = "Usuario"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn(foreign_keys: bool = True) -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if foreign_keys:
        conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Crea la carpeta y las tablas si no existen. Idempotente y no destructiva."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with closing(_conn()) as conn, conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id)
                    REFERENCES conversations(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pronunciation_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                expected TEXT NOT NULL,
                heard TEXT NOT NULL,
                score INTEGER NOT NULL,
                level TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS learning_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                type TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vocabulary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                word TEXT NOT NULL,
                appearances INTEGER NOT NULL DEFAULT 1,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                UNIQUE (user_id, word),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS grammar_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                rule TEXT NOT NULL,
                message TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 1,
                last_example TEXT NOT NULL DEFAULT '',
                last_seen TEXT NOT NULL,
                first_seen TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 1.0,
                source TEXT NOT NULL DEFAULT 'heuristic',
                confirmed INTEGER NOT NULL DEFAULT 1,
                correct_after INTEGER NOT NULL DEFAULT 0,
                streak INTEGER NOT NULL DEFAULT 0,
                mastered INTEGER NOT NULL DEFAULT 0,
                UNIQUE (user_id, rule),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listening_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                answer_index INTEGER NOT NULL,
                correct INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS learning_profile (
                user_id TEXT PRIMARY KEY,
                cefr_level TEXT NOT NULL DEFAULT 'A1',
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                user_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, key),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS learning_goal (
                user_id TEXT PRIMARY KEY,
                goal_type TEXT NOT NULL DEFAULT 'general',
                minutes_per_day INTEGER NOT NULL DEFAULT 15,
                days_per_week INTEGER NOT NULL DEFAULT 5,
                target_level TEXT NOT NULL DEFAULT 'B1',
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS session_completions (
                user_id TEXT NOT NULL,
                step_key TEXT NOT NULL,
                completed_on TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                PRIMARY KEY (user_id, step_key),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS academy_enrollments (
                user_id TEXT NOT NULL,
                level_id TEXT NOT NULL,
                level TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                enrolled_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, level_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS academy_skill_mastery (
                user_id TEXT NOT NULL,
                level_id TEXT NOT NULL,
                skill TEXT NOT NULL,
                score REAL NOT NULL DEFAULT 0.0,
                recent_score REAL NOT NULL DEFAULT 0.0,
                confidence REAL NOT NULL DEFAULT 0.0,
                streak INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_seen_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, level_id, skill),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS academy_objective_mastery (
                user_id TEXT NOT NULL,
                level_id TEXT NOT NULL,
                objective_id TEXT NOT NULL,
                skill TEXT NOT NULL,
                score REAL NOT NULL DEFAULT 0.0,
                recent_score REAL NOT NULL DEFAULT 0.0,
                confidence REAL NOT NULL DEFAULT 0.0,
                streak INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_seen_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, level_id, objective_id, skill),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS academy_assessment_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                assessment_id TEXT NOT NULL,
                level_id TEXT NOT NULL DEFAULT '',
                results_json TEXT NOT NULL,
                passed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS academy_level_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                level_id TEXT NOT NULL,
                level TEXT NOT NULL,
                overall REAL NOT NULL,
                awarded_at TEXT NOT NULL,
                UNIQUE (user_id, level_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS academy_activity_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                level_id TEXT NOT NULL,
                objective_id TEXT NOT NULL,
                skill TEXT NOT NULL,
                result TEXT NOT NULL,
                event_type TEXT NOT NULL DEFAULT 'attempt',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS academy_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                level_id TEXT NOT NULL,
                objective_id TEXT NOT NULL DEFAULT '',
                skill TEXT NOT NULL,
                item_id TEXT NOT NULL DEFAULT '',
                item_type TEXT NOT NULL DEFAULT 'mcq',
                difficulty INTEGER NOT NULL DEFAULT 1,
                source TEXT NOT NULL DEFAULT 'objective_assessment',
                result REAL NOT NULL DEFAULT 0.0,
                curriculum_version TEXT NOT NULL DEFAULT '',
                assessment_version TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        # Migración idempotente: dimensión `evidence_kind` de la evidencia
        # (familiar/transfer/novel). Toda la evidencia previa queda 'familiar'.
        evidence_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(academy_evidence)")
        }
        if "evidence_kind" not in evidence_cols:
            conn.execute(
                "ALTER TABLE academy_evidence ADD COLUMN evidence_kind TEXT "
                "NOT NULL DEFAULT 'familiar'"
            )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cefr_assessment_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                level TEXT NOT NULL,
                numeric REAL NOT NULL,
                confidence REAL NOT NULL,
                instrument_version TEXT NOT NULL,
                curriculum_version TEXT NOT NULL,
                skills_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS placement_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                placement_version TEXT NOT NULL DEFAULT '',
                items_json TEXT NOT NULL DEFAULT '[]',
                answers_json TEXT NOT NULL DEFAULT '{}',
                theta_trace_json TEXT NOT NULL DEFAULT '[]',
                final_result_json TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        # Sesión trazable de Speaking Assessment 1.0 (análoga a placement_sessions):
        # reconstruye qué se evaluó (parts_json), con qué dificultad (cada parte
        # lleva su `difficulty_vector`/`difficulty`), qué evidencia se produjo
        # (evidence_json, una fila por criterio + overall por parte) y el resultado
        # final agregado (final_result_json).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS speaking_assessment_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'in_progress',
                assessment_version TEXT NOT NULL DEFAULT '',
                next_part_index INTEGER NOT NULL DEFAULT 0,
                parts_json TEXT NOT NULL DEFAULT '[]',
                evidence_json TEXT NOT NULL DEFAULT '[]',
                final_result_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        # Speaking Mission Performance (V2.9): sesión trazable del loop
        # Mission → Attempt → Evaluation → Drill → Retry → Improvement.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS speaking_mission_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'mission',
                scenario_id TEXT NOT NULL DEFAULT '',
                mission_json TEXT NOT NULL DEFAULT '{}',
                attempt_json TEXT,
                evaluation_json TEXT,
                drill_json TEXT NOT NULL DEFAULT '[]',
                retry_json TEXT,
                improvement_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        # Assessment 2.0 (V2.10): escalera formative/unit/progress/level/retention.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS assessment_v2_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                kind TEXT NOT NULL,
                level_id TEXT NOT NULL DEFAULT '',
                unit_id TEXT NOT NULL DEFAULT '',
                objective_id TEXT NOT NULL DEFAULT '',
                assessment_version TEXT NOT NULL DEFAULT '',
                instrument_json TEXT NOT NULL DEFAULT '{}',
                answers_json TEXT,
                result_json TEXT,
                retention_json TEXT,
                source_session_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        # FSRS-lite (V2.11): estado de scheduling por target (skill/lexicon/objective).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fsrs_cards (
                user_id TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                state TEXT NOT NULL DEFAULT 'new',
                difficulty REAL NOT NULL DEFAULT 5.0,
                stability REAL NOT NULL DEFAULT 0.1,
                reps INTEGER NOT NULL DEFAULT 0,
                lapses INTEGER NOT NULL DEFAULT 0,
                due_at TEXT NOT NULL DEFAULT '',
                last_review_at TEXT NOT NULL DEFAULT '',
                last_evidence_at TEXT NOT NULL DEFAULT '',
                last_grade INTEGER,
                why TEXT NOT NULL DEFAULT '',
                fsrs_version TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, target_type, target_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        # Calibración observacional de ítems de placement (V1.7): contadores
        # poblacionales por ítem (no por usuario). Las columnas de estimación
        # (estimated_difficulty/standard_error/discrimination) las rellena un
        # proceso de calibración posterior; aquí solo se persisten las
        # respuestas observadas y su tasa de acierto.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS placement_item_calibration (
                item_id TEXT PRIMARY KEY,
                responses INTEGER NOT NULL DEFAULT 0,
                correct INTEGER NOT NULL DEFAULT 0,
                correct_rate REAL,
                sample_size INTEGER,
                estimated_difficulty REAL,
                standard_error REAL,
                discrimination REAL
            )
            """
        )

        # Migración idempotente: SQLite no soporta ADD COLUMN IF NOT EXISTS.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(conversations)")}
        if "user_id" not in columns:
            conn.execute("ALTER TABLE conversations ADD COLUMN user_id TEXT")

        msg_columns = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
        if "mode" not in msg_columns:
            conn.execute("ALTER TABLE messages ADD COLUMN mode TEXT")

        if "message_id" not in msg_columns:
            conn.execute("ALTER TABLE messages ADD COLUMN message_id TEXT")

        # Migración idempotente: telemetría de turno (InteractionEvidence 2.0).
        # `duration_ms` = duración del turno; `latency_ms` = tiempo hasta empezar a
        # responder. Nullables: solo se rellenan cuando el turno tiene telemetría.
        if "duration_ms" not in msg_columns:
            conn.execute("ALTER TABLE messages ADD COLUMN duration_ms INTEGER")
        if "latency_ms" not in msg_columns:
            conn.execute("ALTER TABLE messages ADD COLUMN latency_ms INTEGER")

        # Migración idempotente: personalización visual del perfil (avatar).
        user_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "avatar_color" not in user_cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN avatar_color TEXT NOT NULL DEFAULT ''"
            )
        if "avatar_emoji" not in user_cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN avatar_emoji TEXT NOT NULL DEFAULT ''"
            )
        if "avatar_image" not in user_cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN avatar_image TEXT NOT NULL DEFAULT ''"
            )

        # Migración idempotente: `occurrences` → `appearances` (nº de mensajes en
        # los que apareció la palabra, no frecuencia real de uso).
        vocab_cols = {row[1] for row in conn.execute("PRAGMA table_info(vocabulary)")}
        if "occurrences" in vocab_cols and "appearances" not in vocab_cols:
            conn.execute(
                "ALTER TABLE vocabulary RENAME COLUMN occurrences TO appearances"
            )

        # Migración idempotente (P3): separa exposición / producción / dominio.
        # `exposures` cuenta los mensajes del tutor en los que apareció la palabra
        # (input que el alumno lee); `last_exposed_at` su última exposición; y
        # `production_days` los días distintos con producción del alumno (espaciado).
        if "exposures" not in vocab_cols:
            conn.execute(
                "ALTER TABLE vocabulary ADD COLUMN exposures INTEGER NOT NULL DEFAULT 0"
            )
        if "last_exposed_at" not in vocab_cols:
            conn.execute(
                "ALTER TABLE vocabulary ADD COLUMN last_exposed_at TEXT "
                "NOT NULL DEFAULT ''"
            )
        if "production_days" not in vocab_cols:
            conn.execute(
                "ALTER TABLE vocabulary ADD COLUMN production_days INTEGER "
                "NOT NULL DEFAULT 0"
            )
            conn.execute(
                "UPDATE vocabulary SET production_days = 1 "
                "WHERE appearances > 0 AND production_days = 0"
            )

        # Migración idempotente (V2.3): contexto curricular del ítem léxico.
        # Convierte la palabra en un ítem de primer nivel sembrado desde el
        # currículo (`objective.vocabulary` + `objective.concepts`). Estas
        # columnas solo añaden contexto; no afectan a las métricas de
        # producción/input (`appearances`/`exposures`).
        if "cefr" not in vocab_cols:
            conn.execute(
                "ALTER TABLE vocabulary ADD COLUMN cefr TEXT NOT NULL DEFAULT ''"
            )
        if "level_id" not in vocab_cols:
            conn.execute(
                "ALTER TABLE vocabulary ADD COLUMN level_id TEXT NOT NULL DEFAULT ''"
            )
        if "objective_id" not in vocab_cols:
            conn.execute(
                "ALTER TABLE vocabulary ADD COLUMN objective_id TEXT "
                "NOT NULL DEFAULT ''"
            )
        if "source" not in vocab_cols:
            conn.execute(
                "ALTER TABLE vocabulary ADD COLUMN source TEXT NOT NULL DEFAULT 'user'"
            )
        if "lemma" not in vocab_cols:
            conn.execute(
                "ALTER TABLE vocabulary ADD COLUMN lemma TEXT NOT NULL DEFAULT ''"
            )
        if "kind" not in vocab_cols:
            conn.execute(
                "ALTER TABLE vocabulary ADD COLUMN kind TEXT NOT NULL DEFAULT 'word'"
            )

        # Migración idempotente: confianza y estado de confirmación en errores
        # gramaticales (candidato vs confirmado), para verificación futura por LLM.
        grammar_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(grammar_errors)")
        }
        if "confidence" not in grammar_cols:
            conn.execute(
                "ALTER TABLE grammar_errors ADD COLUMN confidence REAL "
                "NOT NULL DEFAULT 1.0"
            )
        if "source" not in grammar_cols:
            conn.execute(
                "ALTER TABLE grammar_errors ADD COLUMN source TEXT "
                "NOT NULL DEFAULT 'heuristic'"
            )
        if "confirmed" not in grammar_cols:
            conn.execute(
                "ALTER TABLE grammar_errors ADD COLUMN confirmed INTEGER "
                "NOT NULL DEFAULT 1"
            )
        if "first_seen" not in grammar_cols:
            conn.execute(
                "ALTER TABLE grammar_errors ADD COLUMN first_seen TEXT "
                "NOT NULL DEFAULT ''"
            )
            conn.execute(
                "UPDATE grammar_errors SET first_seen = last_seen WHERE first_seen = ''"
            )
        if "correct_after" not in grammar_cols:
            conn.execute(
                "ALTER TABLE grammar_errors ADD COLUMN correct_after INTEGER "
                "NOT NULL DEFAULT 0"
            )
        if "streak" not in grammar_cols:
            conn.execute(
                "ALTER TABLE grammar_errors ADD COLUMN streak INTEGER "
                "NOT NULL DEFAULT 0"
            )
        if "mastered" not in grammar_cols:
            conn.execute(
                "ALTER TABLE grammar_errors ADD COLUMN mastered INTEGER "
                "NOT NULL DEFAULT 0"
            )

        # Migración idempotente: modelo de mastery determinista (recencia EMA,
        # confianza, racha, nº de evidencias y última vista). Sustituye a
        # `score = MAX(score, new)` para poder detectar deterioro del dominio.
        mastery_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(academy_skill_mastery)")
        }
        if "recent_score" not in mastery_cols:
            conn.execute(
                "ALTER TABLE academy_skill_mastery ADD COLUMN recent_score REAL "
                "NOT NULL DEFAULT 0.0"
            )
        if "confidence" not in mastery_cols:
            conn.execute(
                "ALTER TABLE academy_skill_mastery ADD COLUMN confidence REAL "
                "NOT NULL DEFAULT 0.0"
            )
        if "streak" not in mastery_cols:
            conn.execute(
                "ALTER TABLE academy_skill_mastery ADD COLUMN streak INTEGER "
                "NOT NULL DEFAULT 0"
            )
        if "attempts" not in mastery_cols:
            conn.execute(
                "ALTER TABLE academy_skill_mastery ADD COLUMN attempts INTEGER "
                "NOT NULL DEFAULT 0"
            )
        if "last_seen_at" not in mastery_cols:
            conn.execute(
                "ALTER TABLE academy_skill_mastery ADD COLUMN last_seen_at TEXT "
                "NOT NULL DEFAULT ''"
            )

        # Migración idempotente: tipificar eventos de actividad ('attempt' para
        # intentos binarios; 'lesson_completed' para finalizar una lección sin
        # declarar acierto).
        attempt_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(academy_activity_attempts)")
        }
        if "event_type" not in attempt_cols:
            conn.execute(
                "ALTER TABLE academy_activity_attempts ADD COLUMN event_type TEXT "
                "NOT NULL DEFAULT 'attempt'"
            )

        # Migración idempotente: sub-destreza, dificultad y métricas del intento
        # de listening (diagnóstico adaptativo de comprensión auditiva).
        listening_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(listening_attempts)")
        }
        if "skill" not in listening_cols:
            conn.execute(
                "ALTER TABLE listening_attempts ADD COLUMN skill TEXT "
                "NOT NULL DEFAULT ''"
            )
        if "difficulty" not in listening_cols:
            conn.execute(
                "ALTER TABLE listening_attempts ADD COLUMN difficulty INTEGER "
                "NOT NULL DEFAULT 1"
            )
        if "response_time_ms" not in listening_cols:
            conn.execute(
                "ALTER TABLE listening_attempts ADD COLUMN response_time_ms INTEGER"
            )
        if "replay_count" not in listening_cols:
            conn.execute(
                "ALTER TABLE listening_attempts ADD COLUMN replay_count INTEGER "
                "NOT NULL DEFAULT 0"
            )
        if "topic" not in listening_cols:
            conn.execute(
                "ALTER TABLE listening_attempts ADD COLUMN topic TEXT "
                "NOT NULL DEFAULT ''"
            )
        if "realized_difficulty" not in listening_cols:
            conn.execute(
                "ALTER TABLE listening_attempts ADD COLUMN realized_difficulty "
                "INTEGER NOT NULL DEFAULT 0"
            )
        # Migración idempotente: tareas de producción (dictado/shadowing). `task_type`
        # distingue MCQ de producción; `score` (0..1, nullable) es la evidencia
        # continua del intento de producción (solo para dictado/shadowing).
        if "task_type" not in listening_cols:
            conn.execute(
                "ALTER TABLE listening_attempts ADD COLUMN task_type TEXT "
                "NOT NULL DEFAULT 'mcq'"
            )
        if "score" not in listening_cols:
            conn.execute(
                "ALTER TABLE listening_attempts ADD COLUMN score REAL"
            )

        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_conversation_message_id "
            "ON messages(conversation_id, message_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_user_id "
            "ON conversations(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pronunciation_user_id "
            "ON pronunciation_attempts(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_learning_events_user_id "
            "ON learning_events(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_vocabulary_user_id ON vocabulary(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_grammar_errors_user_id "
            "ON grammar_errors(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_listening_attempts_user_id "
            "ON listening_attempts(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_academy_evidence_user_id "
            "ON academy_evidence(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cefr_snapshots_user_id "
            "ON cefr_assessment_snapshots(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_placement_sessions_user_id "
            "ON placement_sessions(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_speaking_assessment_sessions_user_id "
            "ON speaking_assessment_sessions(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_speaking_mission_sessions_user_id "
            "ON speaking_mission_sessions(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_assessment_v2_sessions_user_id "
            "ON assessment_v2_sessions(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fsrs_cards_user_due "
            "ON fsrs_cards(user_id, due_at)"
        )

        # Listening extra generado (V3.6): catálogo global de ítems de práctica
        # generados con IA local (LLM + Piper). Es contenido complementario de una
        # ruta: nunca forma parte del banco curado oficial ni de la puerta de ruta.
        # `payload_json` guarda el dict completo del ítem (mismas claves que el
        # banco: script, question, options, answer_index, skill, topic,
        # difficulty_vector…). `generator_version` versiona el prompt/validador.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listening_generated (
                id TEXT PRIMARY KEY,
                level TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                generator_version TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE (level, payload_json)
            )
            """
        )

        # Activación por usuario de los ítems extra en una ruta (V3.6): un ítem
        # generado entra en la ruta de un alumno solo cuando este lo activa, y la
        # activación se puede revertir (el contenido generado queda en el catálogo
        # global para otros perfiles o para reactivarlo después).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listening_route_extras (
                user_id TEXT NOT NULL,
                level TEXT NOT NULL,
                question_id TEXT NOT NULL,
                added_at TEXT NOT NULL,
                PRIMARY KEY (user_id, level, question_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (question_id) REFERENCES listening_generated(id)
            )
            """
        )

        # Trabajos de generación en segundo plano (V3.6). Generar 10-50 ítems con
        # el modelo local tarda minutos; el POST de extras crea un trabajo y el
        # frontend hace polling hasta `done`. `added_ids_json` lista los ids
        # activados en la ruta al terminar.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listening_generation_jobs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                level TEXT NOT NULL,
                requested INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                added_ids_json TEXT NOT NULL DEFAULT '[]',
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        # Usuario por defecto para no perder conversaciones previas (huérfanas).
        default = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        if default is None:
            uid = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO users (id, name, created_at) VALUES (?, ?, ?)",
                (uid, DEFAULT_USER_NAME, _now()),
            )
            conn.execute(
                "UPDATE conversations SET user_id = ? WHERE user_id IS NULL", (uid,)
            )

    # Fase 2: FKs reales (reconstrucción idempotente con foreign_keys OFF).
    with closing(_conn(foreign_keys=False)) as conn, conn:
        _migrate_conversations_fk(conn)
        _migrate_pronunciation_fk(conn)
        _migrate_certificates_table(conn)


def _has_user_fk(conn: sqlite3.Connection, table: str) -> bool:
    return any(
        row[3] == "user_id" for row in conn.execute(f"PRAGMA foreign_key_list({table})")
    )


def _migrate_conversations_fk(conn: sqlite3.Connection) -> None:
    """Añade FK user_id → users(id) reconstruyendo la tabla (idempotente)."""
    if _has_user_fk(conn, "conversations"):
        return
    conn.execute(
        """
        CREATE TABLE conversations_new (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            user_id TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        "INSERT INTO conversations_new (id, title, created_at, updated_at, user_id) "
        "SELECT id, title, created_at, updated_at, user_id FROM conversations"
    )
    conn.execute("DROP TABLE conversations")
    conn.execute("ALTER TABLE conversations_new RENAME TO conversations")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)"
    )


def _migrate_pronunciation_fk(conn: sqlite3.Connection) -> None:
    """Añade FK user_id → users(id) reconstruyendo la tabla (idempotente)."""
    if _has_user_fk(conn, "pronunciation_attempts"):
        return
    conn.execute(
        """
        CREATE TABLE pronunciation_attempts_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            expected TEXT NOT NULL,
            heard TEXT NOT NULL,
            score INTEGER NOT NULL,
            level TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        "INSERT INTO pronunciation_attempts_new "
        "(id, user_id, expected, heard, score, level, created_at) "
        "SELECT id, user_id, expected, heard, score, level, created_at "
        "FROM pronunciation_attempts"
    )
    conn.execute("DROP TABLE pronunciation_attempts")
    conn.execute(
        "ALTER TABLE pronunciation_attempts_new RENAME TO pronunciation_attempts"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pronunciation_user_id "
        "ON pronunciation_attempts(user_id)"
    )


def _migrate_certificates_table(conn: sqlite3.Connection) -> None:
    """Renombra academy_certificates → academy_level_completions (idempotente).

    Copia las filas existentes y suelta la tabla vieja. No hace nada si la tabla
    antigua ya no existe (instalación nueva o migración ya aplicada)."""
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if "academy_certificates" not in tables:
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS academy_level_completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            level_id TEXT NOT NULL,
            level TEXT NOT NULL,
            overall REAL NOT NULL,
            awarded_at TEXT NOT NULL,
            UNIQUE (user_id, level_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO academy_level_completions "
        "(id, user_id, level_id, level, overall, awarded_at) "
        "SELECT id, user_id, level_id, level, overall, awarded_at "
        "FROM academy_certificates"
    )
    conn.execute("DROP TABLE academy_certificates")


def ping() -> bool:
    """Comprueba que SQLite responde (SELECT 1)."""
    try:
        with closing(_conn()) as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except Exception:  # noqa: BLE001
        return False
