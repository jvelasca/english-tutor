"""Credenciales de la cuenta (V3.81) — sustituyen al PIN de V3.76.

Lo que se fija aquí es lo que **no** puede fallar en silencio: que el KDF
distinga la contraseña buena de la mala, que dos cuentas con la misma contraseña
no compartan hash, que un valor corrupto no autentique, que el freno cuente por
cuenta, y que la política rechace las contraseñas que encabezan cualquier
diccionario. El resto (la API) vive en `test_accounts_v381.py`.
"""
from __future__ import annotations

import pytest

from services import credentials

_BUENA = "caballo-bateria-grapa"


@pytest.fixture(autouse=True)
def _estado_limpio():
    credentials.reset_state()
    yield
    credentials.reset_state()


# --- KDF ----------------------------------------------------------------------


def test_la_contrasena_correcta_verifica_y_la_incorrecta_no():
    stored = credentials.hash_password(_BUENA)
    assert credentials.verify_password(stored, _BUENA) is True
    assert credentials.verify_password(stored, _BUENA + "x") is False
    # Ni siquiera con el prefijo correcto: no hay comparación parcial que valga.
    assert credentials.verify_password(stored, "caballo") is False


def test_dos_cuentas_con_la_misma_contrasena_no_comparten_hash():
    """La sal es por llamada: romper una cuenta no rompe la vecina."""
    uno = credentials.hash_password(_BUENA)
    otro = credentials.hash_password(_BUENA)
    assert uno != otro
    assert credentials.verify_password(uno, _BUENA) is True
    assert credentials.verify_password(otro, _BUENA) is True


def test_el_valor_guardado_declara_algoritmo_e_iteraciones():
    """Sin esto, subir el coste del KDF invalidaría todos los hashes guardados."""
    stored = credentials.hash_password(_BUENA)
    algoritmo, iteraciones, sal, digest = stored.split("$")
    assert algoritmo == "pbkdf2-sha256"
    assert int(iteraciones) == credentials.PBKDF2_ITERATIONS
    assert sal and digest


def test_el_hash_no_contiene_la_contrasena_en_claro():
    assert _BUENA not in credentials.hash_password(_BUENA)


@pytest.mark.parametrize(
    "basura",
    [
        "",
        "no-es-un-hash",
        "pbkdf2-sha256$0$c2FsdA==$aGFzaA==",  # cero iteraciones
        "pbkdf2-sha256$abc$c2FsdA==$aGFzaA==",  # iteraciones no numéricas
        "otro-algoritmo$1000$c2FsdA==$aGFzaA==",
        "pbkdf2-sha256$1000$$",  # salt y hash vacíos
        "pbkdf2-sha256$1000$c2FsdA==",  # partes de menos
        "pbkdf2-sha256$1000$no-base64!!$aGFzaA==",
    ],
)
def test_un_valor_corrupto_no_autentica(basura):
    """Fail-closed: ni una fila manipulada ni una escritura a medias abren puerta."""
    assert credentials.verify_password(basura, _BUENA) is False
    assert credentials.verify_password(basura, "") is False


def test_sin_credencial_no_se_verifica_nada():
    """`""` es «cuenta sin contraseña»: quien llama lo distingue **antes** de
    llegar aquí para poder dejar entrar (estado heredado), no para abrir con
    cualquier cosa."""
    assert credentials.verify_password("", _BUENA) is False
    assert credentials.verify_password("", "") is False


def test_una_contrasena_que_no_es_texto_no_revienta():
    assert credentials.verify_password(credentials.hash_password(_BUENA), None) is False  # type: ignore[arg-type]


# --- Política de contraseña ---------------------------------------------------


@pytest.mark.parametrize(
    "mala",
    [
        "",
        "corta",  # menos de 8
        "1234567",  # 7 dígitos
        "12345678",  # 8, pero de diccionario
        "password",
        "contrasena",
        "CONTRASENA",  # la lista se compara en minúsculas
        "aaaaaaaa",  # un solo carácter repetido no es una contraseña
        "11111111",
        " con espacios ",  # espacios en los extremos = pegote de copiar y pegar
        "caballo bateria"[:7],
    ],
)
def test_la_politica_rechaza_lo_previsible(mala):
    assert credentials.is_valid_password(mala) is False


@pytest.mark.parametrize(
    "buena",
    [
        "caballo-bateria-grapa",
        "8-caracteres",
        "aB3dEf7h",
        "ñandú-2026",
    ],
)
def test_la_politica_acepta_lo_razonable(buena):
    assert credentials.is_valid_password(buena) is True


def test_la_politica_tiene_tope_por_arriba():
    """Un cuerpo de megabytes convertiría el KDF en una vía de agotamiento de CPU."""
    justa = "ab" * (credentials.PASSWORD_MAX_CHARS // 2)
    assert len(justa) == credentials.PASSWORD_MAX_CHARS
    assert credentials.is_valid_password(justa) is True
    assert credentials.is_valid_password(justa + "c") is False


def test_una_contrasena_que_no_es_texto_no_es_valida():
    assert credentials.is_valid_password(None) is False
    assert credentials.is_valid_password(12345678) is False


# --- Freno de intentos --------------------------------------------------------


def test_los_primeros_fallos_no_frenan():
    """Dedos torpes no son un ataque: la holgura es deliberada."""
    esperas = [
        credentials.note_failure("u") for _ in range(credentials._FREE_ATTEMPTS)
    ]

    assert esperas == [0.0] * credentials._FREE_ATTEMPTS
    assert credentials.seconds_to_wait("u") == 0.0


def test_el_freno_crece_al_fallar():
    for _ in range(credentials._FREE_ATTEMPTS):
        credentials.note_failure("u")
    primero = credentials.note_failure("u")
    segundo = credentials.note_failure("u")
    assert primero == 1.0
    assert segundo == 2.0
    assert credentials.seconds_to_wait("u") > 0


def test_acertar_limpia_el_freno():
    for _ in range(credentials._FREE_ATTEMPTS + 4):
        credentials.note_failure("u")
    credentials.note_success("u")
    assert credentials.seconds_to_wait("u") == 0.0
    # Y el contador vuelve a estar en la holgura, no a un fallo del bloqueo.
    assert [
        credentials.note_failure("u") for _ in range(credentials._FREE_ATTEMPTS)
    ] == [0.0] * credentials._FREE_ATTEMPTS


def test_el_freno_es_por_cuenta():
    """Si fuera global, un atacante podría dejar fuera a todo el equipo."""
    for _ in range(credentials._FREE_ATTEMPTS + 3):
        credentials.note_failure("ana")
    assert credentials.seconds_to_wait("ana") > 0
    assert credentials.seconds_to_wait("beto") == 0.0


def test_el_freno_tiene_techo():
    """Sin techo, un contador manipulado bloquearía la cuenta para siempre."""
    for _ in range(credentials._FREE_ATTEMPTS + 50):
        credentials.note_failure("u")
    assert credentials.seconds_to_wait("u") <= credentials._MAX_DELAY_SECONDS


def test_una_cuenta_sin_fallos_no_espera():
    assert credentials.seconds_to_wait("nunca-ha-fallado") == 0.0


# --- Contraseña temporal y email ----------------------------------------------


def test_la_contrasena_temporal_es_legible_y_valida():
    """Se dicta en voz alta: sin caracteres que se confunden al copiarlos."""
    for _ in range(20):
        temporal = credentials.new_temporary_password()
        assert credentials.is_valid_password(temporal) is True
        assert not (set(temporal) & set("0O1lI"))


def test_dos_temporales_no_se_repiten():
    assert len({credentials.new_temporary_password() for _ in range(50)}) == 50


def test_el_token_de_email_se_guarda_hasheado_y_es_de_un_solo_uso():
    token = credentials.new_email_token()
    assert token != credentials.hash_email_token(token)
    # El hash es estable (se puede buscar por él) y distinto por token.
    assert credentials.hash_email_token(token) == credentials.hash_email_token(token)
    assert credentials.hash_email_token(token) != credentials.hash_email_token(
        credentials.new_email_token()
    )


@pytest.mark.parametrize(
    "bueno",
    ["ana@example.com", "a.b+etiqueta@sub.dominio.es", "JOSE@EXAMPLE.ORG"],
)
def test_emails_que_sirven(bueno):
    assert credentials.is_valid_email(bueno) is True
    assert credentials.normalize_email(bueno) != ""


@pytest.mark.parametrize(
    "malo",
    [
        "",
        "sin-arroba",
        "dos@@arrobas.com",
        "sin-dominio@x",
        "@example.com",
        "ana@",
        "ana arroba@example.com",
    ],
)
def test_emails_que_no_sirven(malo):
    assert credentials.is_valid_email(malo) is False
    assert credentials.normalize_email(malo) == ""


def test_el_email_se_normaliza_limpiando_los_extremos():
    """Pegar el correo con un espacio detrás no puede ser un error de alta.

    `is_valid_email` es estricto (no perdona el espacio), pero `normalize_email`
    es el que se usa al guardar y **sí** lo limpia: es la diferencia entre
    rechazar un dedazo y no dejar entrar a alguien por cómo copió y pegó.
    """
    assert credentials.is_valid_email(" ana@example.com ") is False
    assert credentials.normalize_email(" ana@example.com ") == "ana@example.com"


def test_el_email_se_normaliza_en_minusculas():
    """Dos filas que el índice único considera iguales no pueden verse distintas."""
    assert credentials.normalize_email("  Ana@Example.COM ") == "ana@example.com"
