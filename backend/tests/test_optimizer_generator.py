"""Tests for the deterministic candidate generator (Fase 10C-1)."""

import pytest

from app.modules.optimizer.generator import DEFAULT_MAX_CANDIDATES, CandidateGenerator


def _sample_vars():
    return {
        "altitude_m": [80, 90, 100, 110, 120],
        "speed_mps": [4, 5, 6, 7, 8],
        "front_overlap": [75, 80, 85],
        "side_overlap": [65, 70],
    }


# ── Determinism ──────────────────────────────────────────────────────────────


def test_same_input_produces_same_set_and_order():
    gen1 = CandidateGenerator(_sample_vars())
    gen2 = CandidateGenerator(_sample_vars())
    r1 = gen1.generate()
    r2 = gen2.generate()
    assert r1 == r2
    assert [c.label for c in r1.candidates] == [c.label for c in r2.candidates]
    assert [c.values for c in r1.candidates] == [c.values for c in r2.candidates]


def test_determinism_holds_under_truncation():
    gen1 = CandidateGenerator(_sample_vars(), max_candidates=20)
    gen2 = CandidateGenerator(_sample_vars(), max_candidates=20)
    assert gen1.generate() == gen2.generate()


# ── Full cartesian product ───────────────────────────────────────────────────


def test_full_cartesian_product_size_and_order():
    gen = CandidateGenerator(_sample_vars())
    result = gen.generate()
    assert result.total_possible == 5 * 5 * 3 * 2 == 150
    assert result.generated == 150
    assert result.truncated is False
    assert result.strategy == "full_cartesian"
    assert len(result.candidates) == 150

    # lexicographic order in the insertion order of the variables
    first = result.candidates[0].values
    assert first == {"altitude_m": 80, "speed_mps": 4, "front_overlap": 75, "side_overlap": 65}
    last = result.candidates[-1].values
    assert last == {"altitude_m": 120, "speed_mps": 8, "front_overlap": 85, "side_overlap": 70}
    assert [c.index for c in result.candidates] == list(range(150))


def test_variables_preserve_insertion_order():
    gen = CandidateGenerator({"z": [1], "a": [2], "m": [3]})
    assert gen.variables == ["z", "a", "m"]
    result = gen.generate()
    assert result.variables == ["z", "a", "m"]


def test_duplicate_values_are_deduped_preserving_order():
    gen = CandidateGenerator({"altitude_m": [100, 100, 120, 100]})
    result = gen.generate()
    assert result.total_possible == 2
    assert [c.values["altitude_m"] for c in result.candidates] == [100, 120]


# ── Explosion protection ─────────────────────────────────────────────────────


def test_no_truncation_when_product_fits():
    gen = CandidateGenerator({"a": [1, 2], "b": [3, 4]}, max_candidates=100)
    result = gen.generate()
    assert result.truncated is False
    assert result.generated == 4
    assert result.strategy == "full_cartesian"


def test_truncation_reports_possible_and_generated():
    gen = CandidateGenerator(_sample_vars(), max_candidates=50)
    result = gen.generate()
    assert result.total_possible == 150
    assert result.truncated is True
    assert result.generated <= 50
    assert result.strategy == "deterministic_decimation"
    # not silent: the report must tell how many were possible
    assert result.total_possible > result.generated


def test_truncation_keeps_endpoints_and_is_deterministic():
    gen = CandidateGenerator(_sample_vars(), max_candidates=1)
    result = gen.generate()
    assert result.generated == 1
    assert result.truncated is True
    assert result.candidates[0].values == {
        "altitude_m": 80,
        "speed_mps": 4,
        "front_overlap": 75,
        "side_overlap": 65,
    }


def test_decimation_preserves_first_and_last_of_reduced_variable():
    gen = CandidateGenerator(
        {"altitude_m": [80, 90, 100, 110, 120], "speed_mps": [4, 5]},
        max_candidates=2,
    )
    result = gen.generate()
    reduced_altitudes = sorted({c.values["altitude_m"] for c in result.candidates})
    # the extreme altitude values must survive the deterministic decimation
    assert reduced_altitudes[0] == 80
    assert reduced_altitudes[-1] == 120


def test_large_product_respects_hard_limit():
    gen = CandidateGenerator(
        {
            "altitude_m": list(range(80, 121, 5)),
            "speed_mps": [4, 5, 6, 7, 8],
            "front_overlap": [75, 80, 85],
            "side_overlap": [65, 70, 75],
            "photo_interval_s": [1, 2, 3, 4, 5, 6],
        },
        max_candidates=250,
    )
    result = gen.generate()
    assert result.total_possible > 250
    assert result.generated <= 250
    assert result.truncated is True
    assert result.strategy == "deterministic_decimation"


def test_categorical_values_are_supported():
    gen = CandidateGenerator({"turn_radius_m": ["AUTO"], "altitude_m": [80, 90]})
    result = gen.generate()
    assert result.generated == 2
    assert result.candidates[0].values["turn_radius_m"] == "AUTO"


# ── Validation of inputs ─────────────────────────────────────────────────────


def test_empty_variable_values_raises():
    with pytest.raises(ValueError):
        CandidateGenerator({})


def test_empty_value_list_raises():
    with pytest.raises(ValueError):
        CandidateGenerator({"altitude_m": []})


def test_max_candidates_zero_or_negative_raises():
    with pytest.raises(ValueError):
        CandidateGenerator({"a": [1]}, max_candidates=0)
    with pytest.raises(ValueError):
        CandidateGenerator({"a": [1]}, max_candidates=-5)


def test_default_max_candidates_is_positive():
    assert DEFAULT_MAX_CANDIDATES >= 1


# ── Labels ───────────────────────────────────────────────────────────────────


def test_labels_are_deterministic_and_readable():
    gen = CandidateGenerator({"altitude_m": [100.0], "speed_mps": [6.8]})
    result = gen.generate()
    assert result.candidates[0].label == "altitude_m=100 | speed_mps=6.8"


def test_label_float_formatting_is_compact():
    gen = CandidateGenerator({"altitude_m": [100.0, 100.5]})
    result = gen.generate()
    assert result.candidates[0].label == "altitude_m=100"
    assert result.candidates[1].label == "altitude_m=100.5"
