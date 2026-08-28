"""Tests del marco de descriptores CEFR (Curriculum 2.0)."""

from services import cefr_descriptors as cd


def test_framework_loads_all_ladder_bands():
    fw = cd.load_framework()
    assert [b.id for b in fw.bands] == list(cd.CEFR_LADDER)


def test_framework_validates_clean():
    assert cd.validate_framework() == []


def test_every_band_has_nine_dimensions():
    for band in cd.bands():
        assert set(band.can_do) == set(cd.CEFR_DIMENSIONS), band.id


def test_band_for_numeric_maps_plus_bands():
    assert cd.band_for_numeric(0.0) == "pre-a1"
    assert cd.band_for_numeric(1.0) == "a1"
    assert cd.band_for_numeric(2.0) == "a2"
    assert cd.band_for_numeric(2.5) == "a2+"
    assert cd.band_for_numeric(3.0) == "b1"
    assert cd.band_for_numeric(3.6) == "b1+"
    assert cd.band_for_numeric(4.0) == "b2"
    assert cd.band_for_numeric(4.6) == "b2+"
    assert cd.band_for_numeric(5.0) == "c1"
    assert cd.band_for_numeric(6.0) == "c2"


def test_band_for_numeric_clamps_and_rounds():
    assert cd.band_for_numeric(-5.0) == "pre-a1"
    assert cd.band_for_numeric(99.0) == "c2"


def test_band_by_id_roundtrip():
    for band in cd.bands():
        assert cd.band_by_id(band.id) is band
    assert cd.band_by_id("nope") is None


def test_dimensions_are_ordered_and_labeled():
    dims = cd.dimensions()
    assert list(dims) == list(cd.CEFR_DIMENSIONS)
    assert dims["interaction"] == "Interaction"
    assert dims["mediation"] == "Mediation"


def test_plus_bands_have_distinct_descriptors_from_base():
    a2 = cd.band_by_id("a2")
    a2p = cd.band_by_id("a2+")
    assert a2.title != a2p.title
    assert a2.can_do["speaking"] != a2p.can_do["speaking"]
