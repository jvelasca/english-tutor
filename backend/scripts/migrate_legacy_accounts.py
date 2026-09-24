# -*- coding: utf-8 -*-
"""Migra las cuentas heredadas (sin contraseña) al alta profesional (V3.82).

**Qué problema resuelve.** Hasta V3.81 una cuenta podía existir **sin credencial**
y abrir sesión con solo nombrarse. V3.82 retira esa puerta: una cuenta sin
contraseña ya no entra (403 `ACCOUNT_NOT_ACTIVATED`), así que las que quedaran en
ese estado se quedarían fuera. Este guion las pasa al flujo nuevo sin pedirle la
contraseña a nadie:

1. Le asigna su **email** (el que va a identificar la cuenta).
2. Emite una **invitación de activación** (token de un solo uso, 7 días).
3. La deja «pendiente de activación» y **imprime el enlace** para entregarlo a
   mano cuando no haya SMTP (modo híbrido).

Nunca escribe una contraseña: eso lo hace la propia persona desde el enlace.

**Idempotente.** Una cuenta que ya tiene email y contraseña no se toca; una que ya
tiene invitación viva se salta salvo `--reissue`. Se puede correr las veces que
haga falta.

**Seguro por defecto.** Sin `--apply` es un **simulacro** (`--dry-run`): dice qué
haría y no escribe nada. Con `--apply` toma una **copia de seguridad** antes de
tocar la base de datos.

Uso (desde la raíz del repositorio, con el intérprete del backend):

    backend\\.venv\\Scripts\\python.exe backend\\scripts\\migrate_legacy_accounts.py

Añade `--apply` para escribir de verdad (si no, solo simula).

Opciones:

    --apply              escribe de verdad (sin esto, solo simula)
    --base-url URL       origen del frontend para los enlaces (por defecto
                         http://localhost:5173)
    --set NOMBRE=EMAIL   añade o pisa una correspondencia (repetible)
    --reissue            reemite la invitación aunque ya hubiera una viva
    --db RUTA            base de datos a migrar (por defecto la del proyecto)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

# Correspondencia por defecto: las cuentas que existen hoy en la instalación del
# autor. Cada nombre se resuelve sin distinguir mayúsculas ni espacios sobrantes,
# que es la misma regla con la que el producto compara nombres. Se puede ampliar
# con `--set`.
DEFAULT_EMAILS = {
    "j.a": "josealberto.vel+ja@gmail.com",
    "ja": "josealberto.vel+ja@gmail.com",
    "paz": "josealberto.vel+paz@gmail.com",
}


def _fold(name: str) -> str:
    return " ".join((name or "").split()).casefold()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="escribe los cambios")
    parser.add_argument("--reissue", action="store_true", help="reemite la invitación")
    parser.add_argument("--base-url", default="http://localhost:5173")
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="NOMBRE=EMAIL",
        help="correspondencia extra (repetible)",
    )
    parser.add_argument("--db", type=Path, default=None)
    return parser.parse_args(argv)


def build_map(extra: list[str]) -> dict[str, str]:
    """Correspondencia nombre→email, con los `--set` pisando los defectos."""
    mapping = dict(DEFAULT_EMAILS)
    for item in extra:
        if "=" not in item:
            raise SystemExit(f"--set espera NOMBRE=EMAIL, llegó {item!r}")
        name, email = item.split("=", 1)
        mapping[_fold(name)] = email.strip()
    return mapping


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    import config

    if args.db is not None:
        # Se fija la ruta **antes** de importar `repositories.db`, que captura
        # `DATA_DIR` al importarse.
        config.DATA_DIR = args.db.resolve().parent
        import repositories.db as db_module

        db_module.DB_PATH = args.db.resolve()

    from repositories import users as users_repo
    from repositories.db import init_db
    from services import backup, credentials, mailer

    init_db()
    mapping = build_map(args.set)

    users = users_repo.list_users(include_test=False, include_disabled=True)
    legacy = [u for u in users if not u.get("has_password")]

    print(f"# modo: {'APLICAR' if args.apply else 'SIMULACRO (usa --apply)'}")
    print(f"# cuentas totales: {len(users)} · sin contraseña: {len(legacy)}\n")

    if not legacy:
        print("No hay ninguna cuenta pendiente de activación. Nada que hacer.")
        return 0

    plan: list[dict] = []
    for user in legacy:
        name = str(user.get("name") or "")
        existing_email = str(user.get("email") or "")
        target = existing_email or mapping.get(_fold(name), "")
        if not target:
            plan.append(
                {"user": user, "email": "", "skip": "sin correspondencia (usa --set)"}
            )
            continue
        activation = users_repo.get_activation(user["id"]) or ("", "")
        if activation[0] and not args.reissue:
            plan.append({"user": user, "email": target, "skip": "ya tiene invitación"})
            continue
        plan.append({"user": user, "email": target, "skip": ""})

    for item in plan:
        user = item["user"]
        if item["skip"]:
            print(f"  · {user['name']}: se salta ({item['skip']})")
        else:
            print(f"  · {user['name']} → {item['email']}")

    actionable = [item for item in plan if not item["skip"]]
    if not args.apply:
        print(f"\n# {len(actionable)} cuenta(s) se migrarían. Nada escrito.")
        return 0
    if not actionable:
        print("\n# nada que aplicar.")
        return 0

    info = backup.create_backup()
    print(f"\n# copia de seguridad: {info.get('name', info)}")

    links: list[tuple[str, str, str]] = []
    for item in actionable:
        user = item["user"]
        uid = user["id"]
        email = item["email"]
        existing_email = str(user.get("email") or "")
        if email != existing_email:
            # No se usa `set_credentials` (eso pondría una contraseña y
            # `must_change`): aquí solo se fija el email. La contraseña la elige
            # la persona desde el enlace de activación.
            updated = users_repo.set_email(uid, email)
            if updated is None:
                print(f"  ! {user['name']}: no se pudo asignar el email")
                continue
        token = credentials.new_activation_token()
        if not users_repo.set_activation(uid, credentials.hash_token(token)):
            print(f"  ! {user['name']}: no se pudo emitir la invitación")
            continue
        # El hito se anota en el repositorio directamente: este guion es síncrono y
        # el envoltorio async del dominio solo existe para los routers.
        users_repo.record_event(
            subject_id=uid,
            subject_name=user["name"],
            action=users_repo.EVENT_INVITED,
            note="migración heredada",
        )
        link = mailer.activation_link(args.base_url, token)
        links.append((user["name"], email, link))
        print(f"  ✓ {user['name']}: invitación emitida")

    print("\n# enlaces de activación (entrégalos a mano si no hay SMTP):")
    for name, email, link in links:
        print(f"  {name} <{email}>\n    {link}")

    print(
        "\n# hecho. Recuerda: la cuenta queda «pendiente de activación» hasta que "
        "la persona abra su enlace."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
