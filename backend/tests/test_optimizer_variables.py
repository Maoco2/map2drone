"""Tests for optimization variables (Fase 10C-2)."""

import pytest
from pydantic import ValidationError

from app.modules.optimizer.generator import CandidateGenerator
from app.modules.optimizer.variables import (
    OPTIMIZABLE_VARIABLES,
    OptimizationVariable,
    OptimizationVariables,
    VariableMode,
    expand_variable,
    expand_variables,
)


def _fixed(name, value):
    return OptimizationVariable(name=name, mode=VariableMode.FIXED, value=value)


def _range(name, min_value, max_value, step):
    return OptimizationVariable(
        name=name,
        mode=VariableMode.RANGE,
        min_value=min_value,
        max_value=max_value,
        step=step,
    )


def _candidates(name, values):
    return OptimizationVariable(
        name=name,
        mode=VariableMode.CANDIDATE_VALUES,
        values=values,
    )


# ── FIXED ────────────────────────────────────────────────────────────────────


def test_fixed_expands_to_single_value():
    var = _fixed("altitude_m", 100)
    assert expand_variable(var) == [100]


def test_fixed_accepts_string_categorical():
    var = _fixed("turn_radius_m", "AUTO")
    assert expand_variable(var) == ["AUTO"]


def test_fixed_missing_value_rejected():
    with pytest.raises(ValidationError):
        OptimizationVariable(name="altitude_m", mode=VariableMode.FIXED)


# ── RANGE ────────────────────────────────────────────────────────────────────


def test_range_integral_inclusive():
    values = expand_variable(_range("altitude_m", 80, 120, 10))
    assert values == [80, 90, 100, 110, 120]


def test_range_fractional_step_no_drift():
    values = expand_variable(_range("speed_mps", 4.0, 8.0, 0.5))
    assert values == [4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0]


def test_range_non_integral_spans_append_max():
    values = expand_variable(_range("front_overlap", 65.0, 75.0, 7.0))
    assert values == [65.0, 72.0, 75.0]


def test_range_single_step_interval():
    values = expand_variable(_range("altitude_m", 80, 80, 10))
    assert values == [80.0]


def test_range_deterministic():
    a = expand_variable(_range("speed_mps", 4.0, 8.0, 0.3))
    b = expand_variable(_range("speed_mps", 4.0, 8.0, 0.3))
    assert a == b


def test_range_min_greater_than_max_rejected():
    with pytest.raises(ValidationError):
        _range("altitude_m", 200, 80, 10)


def test_range_zero_or_negative_step_rejected():
    with pytest.raises(ValidationError):
        _range("altitude_m", 80, 120, 0)
    with pytest.raises(ValidationError):
        _range("altitude_m", 80, 120, -5)


def test_range_missing_fields_rejected():
    with pytest.raises(ValidationError):
        OptimizationVariable(
            name="altitude_m",
            mode=VariableMode.RANGE,
            min_value=80,
            max_value=120,
        )


# ── CANDIDATE_VALUES ─────────────────────────────────────────────────────────


def test_candidate_values_pass_through():
    var = _candidates("photo_interval_s", [1, 2, 3])
    assert expand_variable(var) == [1, 2, 3]


def test_candidate_values_empty_rejected():
    with pytest.raises(ValidationError):
        _candidates("photo_interval_s", [])


# ── Name contract ────────────────────────────────────────────────────────────


def test_unknown_variable_name_rejected():
    with pytest.raises(ValidationError):
        OptimizationVariable(
            name="hacienda_m",
            mode=VariableMode.FIXED,
            value=100,
        )


def test_canonical_variables_cover_optimizable_dimensions():
    assert set(OPTIMIZABLE_VARIABLES) == {
        "altitude_m",
        "speed_mps",
        "front_overlap",
        "side_overlap",
        "photo_interval_s",
        "turn_radius_m",
    }


# ── Collection / expansion ───────────────────────────────────────────────────


def test_expand_variables_preserves_insertion_order():
    varset = OptimizationVariables(
        variables=[
            _fixed("altitude_m", 100),
            _range("speed_mps", 4, 6, 1),
        ]
    )
    mapping = expand_variables(varset)
    assert list(mapping) == ["altitude_m", "speed_mps"]
    assert mapping["altitude_m"] == [100]
    assert mapping["speed_mps"] == [4.0, 5.0, 6.0]


def test_empty_collection_rejected():
    with pytest.raises(ValidationError):
        OptimizationVariables(variables=[])


def test_expansion_feeds_candidate_generator():
    varset = OptimizationVariables(
        variables=[
            _range("altitude_m", 80, 120, 10),
            _range("speed_mps", 4, 8, 1),
            _fixed("turn_radius_m", "AUTO"),
        ]
    )
    result = CandidateGenerator(expand_variables(varset)).generate()
    assert result.total_possible == 5 * 5 * 1
    assert result.generated == 25
    assert result.truncated is False
    assert result.candidates[0].values == {
        "altitude_m": 80.0,
        "speed_mps": 4.0,
        "turn_radius_m": "AUTO",
    }


def test_expansion_supports_decimation_integration():
    varset = OptimizationVariables(
        variables=[
            _range("altitude_m", 80, 120, 5),
            _range("speed_mps", 4, 8, 0.5),
            _range("front_overlap", 75, 85, 5),
            _range("side_overlap", 65, 75, 5),
        ]
    )
    mapping = expand_variables(varset)
    result = CandidateGenerator(mapping, max_candidates=100).generate()
    assert result.total_possible == 9 * 9 * 3 * 3
    assert result.generated <= 100
    assert result.truncated is True
    assert result.strategy == "deterministic_decimation"


def test_names_property():
    varset = OptimizationVariables(
        variables=[
            _fixed("altitude_m", 100),
            _fixed("speed_mps", 5),
        ]
    )
    assert varset.names == ["altitude_m", "speed_mps"]
