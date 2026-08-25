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
            "CREATE INDEX IF NOT EXISTS idx_placement_sessions_user_id "
            "ON placement_sessions(user_id)"
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
