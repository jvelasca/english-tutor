"""Borrado de perfiles de prueba («virtual testers») de la base de datos local.

Durante el desarrollo se crearon varios perfiles de prueba (`Visual Tester n`
en la BD; «virtual testers» coloquialmente) para probar la app. Ya no son
necesarios: este script los elimina de `tutor.db` junto con toda su evidencia
(los ~40 tablas con `user_id` no tienen `ON DELETE CASCADE`, así que el borrado
debe ser explícito y transaccional).

Seguridad:

- **Dry-run por defecto**: sin `--apply` solo muestra qué perfiles coinciden y
  cuántas filas se borrarían; no modifica nada.
- **Copia de seguridad**: antes de aplicar, hace checkpoint del WAL y guarda
  `tutor.db.bak-<timestamp>` junto a la base de datos.
- **Transacción única**: todos los `DELETE` van en una transacción; si algo
  falla, no se borra nada.
- **No toca a los demás usuarios**: solo actúa sobre los ids que coinciden con
  el patrón (por defecto `%tester%`, sin distinguir mayúsculas).

Uso:

    python scripts/purge_virtual_testers.py                 # dry-run
    python scripts/purge_virtual_testers.py --apply         # borra de verdad
    python scripts/purge_virtual_testers.py --db ruta.db    # otra base de datos

Requiere cerrar la app/launcher antes de `--apply` (si no, el WAL puede estar
activo y el fichero bloqueado en Windows).
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# El script vive en <repo>/scripts/, así que la raíz es el padre de `scripts`.
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "backend" / "data" / "tutor.db"
# Perfiles de prueba creados durante el desarrollo (el usuario los llama
# «virtual testers»; el nombre real en la BD es «Visual Tester n»).
DEFAULT_PATTERN = "%tester%"
# Tablas con `user_id` que NO se borran por la vía genérica: se tratan aparte
# porque `messages` no tiene `user_id` (cuelga de `conversations`).
SPECIAL_TABLES = {"conversations"}


def quote(identifier: str) -> str:
    """Escapa un identificador SQLite (nombre de tabla)."""
    return '"' + identifier.replace('"', '""') + '"'


def tables_with_user_id(conn: sqlite3.Connection) -> list[str]:
    """Enumera dinámicamente las tablas que tienen columna `user_id`."""
    names = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    result: list[str] = []
    for name in names:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({quote(name)})")}
        if "user_id" in columns:
            result.append(name)
    return result


def placeholders(count: int) -> str:
    return ", ".join("?" for _ in range(count))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Elimina los perfiles de prueba «VIRTUAL TESTER» de tutor.db.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica el borrado (por defecto solo simula, dry-run).",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"Ruta de la base de datos (por defecto: {DEFAULT_DB}).",
    )
    parser.add_argument(
        "--pattern",
        default=DEFAULT_PATTERN,
        help=f"Patrón LIKE del nombre de usuario (por defecto: {DEFAULT_PATTERN!r}).",
    )
    args = parser.parse_args(argv)

    db_path: Path = args.db
    if not db_path.exists():
        print(f"ERROR: no existe la base de datos {db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(db_path)
    try:
        targets = conn.execute(
            "SELECT id, name, created_at FROM users "
            "WHERE name LIKE ? COLLATE NOCASE ORDER BY name",
            (args.pattern,),
        ).fetchall()
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

        print(f"Base de datos: {db_path}")
        print(f"Patrón:        {args.pattern!r}")
        print(f"Usuarios totales: {total_users}")
        print(f"Coincidencias:    {len(targets)}")
        for user_id, name, created_at in targets:
            print(f"  - {name}  (id={user_id}, alta={created_at})")

        if not targets:
            print("\nNada que borrar.")
            return 0

        ids = [row[0] for row in targets]
        marks = placeholders(len(ids))

        tables = tables_with_user_id(conn)
        conversation_ids = [
            row[0]
            for row in conn.execute(
                f"SELECT id FROM conversations WHERE user_id IN ({marks})", ids
            )
        ]
        messages = 0
        if conversation_ids:
            msg_marks = placeholders(len(conversation_ids))
            messages = conn.execute(
                f"SELECT COUNT(*) FROM messages "
                f"WHERE conversation_id IN ({msg_marks})",
                conversation_ids,
            ).fetchone()[0]

        counts: list[tuple[str, int]] = []
        for table in tables:
            if table in SPECIAL_TABLES:
                continue
            count = conn.execute(
                f"SELECT COUNT(*) FROM {quote(table)} WHERE user_id IN ({marks})",
                ids,
            ).fetchone()[0]
            if count:
                counts.append((table, count))
        counts.append(("conversations", len(conversation_ids)))
        counts.append(("messages", messages))
        counts.append(("users", len(ids)))

        print("\nFilas a borrar por tabla:")
        for table, count in counts:
            print(f"  - {table}: {count}")

        if not args.apply:
            print("\nDRY-RUN: no se ha modificado nada. Usa --apply para borrar.")
            return 0

        # Checkpoint del WAL para que la copia incluya todo lo confirmado.
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = db_path.with_name(f"{db_path.name}.bak-{timestamp}")
        shutil.copy2(db_path, backup_path)
        print(f"\nCopia de seguridad: {backup_path}")

        # FK OFF: el borrado recorre padre→hijo por `user_id`; las tablas sin
        # `user_id` no cuelgan de estos usuarios.
        conn.execute("PRAGMA foreign_keys = OFF")
        with conn:  # transacción única
            if conversation_ids:
                msg_marks = placeholders(len(conversation_ids))
                conn.execute(
                    f"DELETE FROM messages WHERE conversation_id IN ({msg_marks})",
                    conversation_ids,
                )
            conn.execute(
                f"DELETE FROM conversations WHERE user_id IN ({marks})", ids
            )
            for table in tables:
                if table in SPECIAL_TABLES:
                    continue
                conn.execute(
                    f"DELETE FROM {quote(table)} WHERE user_id IN ({marks})", ids
                )
            conn.execute(f"DELETE FROM users WHERE id IN ({marks})", ids)
        conn.execute("PRAGMA foreign_keys = ON")

        remaining = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        print(
            f"Borrados {len(ids)} perfiles de prueba. "
            f"Usuarios restantes: {remaining}."
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
