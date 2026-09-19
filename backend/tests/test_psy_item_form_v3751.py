"""Instrumento psicométrico del banco (V3.75.1 · pausa pedagógica pre-baseline).

Fija el **contrato del instrumento** (`item-form`, `distractor-signals` y la
extensión de `mc-bias`), **no las cifras del defecto**: la auditoría es de
medición y el plan declara que los candados que fijen un invariante de reparto se
diseñan **con** la corrección, no antes. Lo que se comprueba aquí es que el
instrumento:

1. mide el mismo conjunto de ítems por sus tres ejes (`mc_banks` como fuente
   única);
2. es internamente coherente (posiciones y `k` suman, las posiciones muertas lo
   son de verdad);
3. es determinista y de solo lectura;
4. no puede volver a etiquetar los exámenes como «level/placement»: el
   placement se mide aparte.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import audit_dossier

ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT / "docs" / "audit" / "generated"

BANCOS = ("checks_curriculum", "corpus_listening", "exams", "placement")
TAMANO_BANCOS = {
    "checks_curriculum": 368,
    "corpus_listening": 490,
    "exams": 22,
    "placement": 24,
}


def _snapshot(directory: Path) -> dict[str, float]:
    if not directory.is_dir():
        return {}
    return {
        str(path.relative_to(ROOT)).replace("\\", "/"): path.stat().st_mtime
        for path in directory.rglob("*")
        if path.is_file()
    }


# --- 1. Fuente única: los tres ejes miden el mismo conjunto -----------------


def test_mc_banks_son_los_cuatro_bancos_declarados():
    banks = audit_dossier.mc_banks()
    assert tuple(banks) == BANCOS
    assert {name: len(rows) for name, rows in banks.items()} == TAMANO_BANCOS


def test_cada_fila_de_banco_es_un_mc_completo():
    for name, rows in audit_dossier.mc_banks().items():
        for row in rows:
            assert set(row) == {
                "id",
                "level",
                "prompt",
                "options",
                "correct_index",
            }, name
            assert len(row["options"]) >= 2, (name, row["id"])


def test_el_placement_tiene_sus_24_items_y_no_esta_fundido_con_los_examenes():
    """Hasta V3.75.1, `mc-bias` llamaba «level/placement» a un grupo de 22 que
    solo contaba exámenes: el placement (24 ítems) no aparecía en la medición."""
    banks = audit_dossier.mc_banks()
    assert len(banks["placement"]) == 24
    assert len(banks["exams"]) == 22
    assert {row["level"] for row in banks["placement"]} == {"placement"}
    assert "placement" not in {row["level"] for row in banks["exams"]}


# --- 2. Coherencia interna del instrumento ----------------------------------


def test_bias_separa_examenes_de_placement_y_declara_el_k():
    groups = audit_dossier.mc_position_bias()["groups"]
    names = [group["name"] for group in groups]
    assert "exámenes finales" in names
    assert "placement" in names
    # El nombre que mezclaba dos instrumentos distintos ya no existe.
    assert all("level/placement" not in name for name in names)
    for group in groups:
        assert "options_count_distribution" in group
        assert sum(group["counts"].values()) == group["items"]


def test_los_grupos_de_bias_cubren_todos_los_bancos():
    groups = audit_dossier.mc_position_bias()["groups"]
    total = sum(group["items"] for group in groups if group["name"] in {
        "corpus listening (c*)",
        "checks currículo (niveles)",
        "exámenes finales",
        "placement",
    })
    assert total == sum(TAMANO_BANCOS.values())


def test_item_form_posiciones_y_k_suman_y_las_muertas_lo_son():
    for group in audit_dossier.item_form()["groups"]:
        if not group.get("n"):
            continue
        assert sum(group["positions"].values()) == group["n"], group["name"]
        assert sum(group["options_count_distribution"].values()) == group["n"]
        for k, sub in group["by_options_count"].items():
            assert sum(sub["positions"].values()) == sub["n"], (group["name"], k)
            assert list(sub["positions"]) == [str(i) for i in range(int(k))]
            assert sub["dead_positions"] == [
                i for i, count in enumerate(sub["positions"].values()) if count == 0
            ]


def test_item_form_marca_el_reparto_por_grupo_no_solo_el_agregado():
    """Una posición solo existe dentro de su `k`: el desglose no puede faltar."""
    groups = {group["name"]: group for group in audit_dossier.item_form()["groups"]}
    checks = groups["checks del currículum (todos)"]
    assert set(checks["by_options_count"]) == {"3", "4"}
    # El agregado de los 368 escondería que el 4.º distractor solo aparece en 10.
    assert checks["by_options_count"]["4"]["n"] == 10


# --- 3. Determinismo y solo lectura ----------------------------------------


def test_item_form_es_determinista():
    first = audit_dossier.item_form_markdown(audit_dossier.item_form())
    second = audit_dossier.item_form_markdown(audit_dossier.item_form())
    assert first == second


def test_distractor_signals_es_determinista():
    first = audit_dossier.distractor_signals_markdown(
        audit_dossier.distractor_signals()
    )
    second = audit_dossier.distractor_signals_markdown(
        audit_dossier.distractor_signals()
    )
    assert first == second


def test_el_instrumento_no_escribe_en_data_ni_en_curriculum():
    watched = (BACKEND / "data", BACKEND / "curriculum")
    before = {str(d): _snapshot(d) for d in watched}

    audit_dossier.item_form()
    audit_dossier.item_form_markdown(audit_dossier.item_form())
    audit_dossier.distractor_signals()
    audit_dossier.mc_position_bias()

    after = {str(d): _snapshot(d) for d in watched}
    assert before == after, "el instrumento escribió en data/ o en curriculum/"


# --- 4. El perfil de longitud (unidad, sin leer contenido) ------------------


def test_length_profile_marca_la_mas_larga_unica_y_los_empates():
    unique = audit_dossier._length_profile(["aa", "bbbb", "cc"], 1)
    assert unique is not None
    assert unique["correct_is_longest"] is True
    assert unique["correct_is_longest_or_tied"] is True

    tied = audit_dossier._length_profile(["aaaa", "bbbb", "cc"], 0)
    assert tied["correct_is_longest"] is False
    assert tied["correct_is_longest_or_tied"] is True

    shorter = audit_dossier._length_profile(["aaaa", "bbbb", "cc"], 2)
    assert shorter["correct_is_longest"] is False
    assert shorter["correct_is_longest_or_tied"] is False


def test_length_profile_rechaza_lo_que_no_es_un_mc_valido():
    assert audit_dossier._length_profile(["solo"], 0) is None
    assert audit_dossier._length_profile(["a", "b"], 2) is None
    assert audit_dossier._length_profile(["a", "b"], None) is None
    assert audit_dossier._length_profile(["a", "b"], True) is None


def test_shape_outlier_solo_dispara_con_la_desviacion_mayor():
    outlier = audit_dossier._length_profile(
        ["This is a much longer option", "a", "b"], 0
    )
    assert outlier is not None and outlier["shape_outlier"] is True
    # Si un distractor se desvía más que la correcta, no dispara.
    not_outlier = audit_dossier._length_profile(
        ["aaa", "b", "cccccccccccccccccccccccc"], 0
    )
    assert not_outlier["shape_outlier"] is False


# --- 5. Señales de distractor inferible ------------------------------------


def test_las_senales_declaradas_son_un_conjunto_cerrado_y_se_miden_todas():
    data = audit_dossier.distractor_signals()
    declared = set(audit_dossier.DISTRACTOR_SIGNALS)
    assert set(data["signals"]) == declared
    for bank, summary in data["banks"].items():
        assert set(summary["signal_counts"]) == declared, bank
        assert set(summary["signal_pct"]) == declared, bank
        assert summary["n_flagged"] <= summary["n"]
        for name in declared:
            assert summary["signal_counts"][name] <= summary["n_flagged"]
        # La muestra sale del conjunto marcado y es determinista.
        assert all(item["signals"] for item in summary["sample"])
        assert all(set(item["signals"]) <= declared for item in summary["sample"])


@pytest.mark.parametrize(
    "prompt, options, index, expected",
    (
        (
            "What does the customer want from the jacket shop?",
            ["A drink", "A jacket", "A ticket"],
            1,
            "prompt_keyword_echo",
        ),
        (
            "When does he go to work?",
            ["At night", "At eight", "Later"],
            1,
            "quantity_literal",
        ),
    ),
)
def test_las_senales_detectan_los_casos_declarados(prompt, options, index, expected):
    row = {
        "id": "x",
        "level": "A1",
        "prompt": prompt,
        "options": options,
        "correct_index": index,
    }
    assert expected in audit_dossier._signals_for(row)


# --- 6. Anti-drift de los artefactos generados ------------------------------


@pytest.mark.parametrize(
    "name, builder",
    (
        ("item-form", audit_dossier.item_form),
        ("distractor-signals", audit_dossier.distractor_signals),
    ),
)
def test_los_artefactos_generados_coinciden_con_el_disco(name, builder):
    generated = json.loads(
        (GENERATED_DIR / f"{name}.json").read_text(encoding="utf-8")
    )
    assert generated == json.loads(json.dumps(builder(), ensure_ascii=False))
