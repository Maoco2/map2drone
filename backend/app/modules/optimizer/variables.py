"""Optimizer — optimization variables (Fase 10C-2).

Defines the *what can be optimized* contract: each optimizable variable is
declared as ``FIXED`` (single value), ``RANGE`` (deterministic expansion from
``min_value`` to ``max_value`` with ``step``) or ``CANDIDATE_VALUES`` (explicit
list). The values themselves always come from configuration / the API request —
nothing is hardcoded here except the canonical variable names (the contract).

Expansion feeds the deterministic :class:`~app.modules.optimizer.generator.CandidateGenerator`:
``expand_variables`` returns the ``variable_values`` mapping (insertion order
preserved). RANGE expansion uses ``Decimal`` arithmetic to avoid floating point
drift, is inclusive on both ends, and always reproduces the same sequence.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class VariableMode(str, Enum):
    """How an optimizable variable is declared by the caller."""

    FIXED = "fixed"
    RANGE = "range"
    CANDIDATE_VALUES = "candidate_values"


#: Canonical optimizable variable names. This is the contract shared with the
#: integration steps (10C-4/5/6); an unknown name is a configuration error.
OPTIMIZABLE_VARIABLES: tuple[str, ...] = (
    "altitude_m",
    "speed_mps",
    "front_overlap",
    "side_overlap",
    "photo_interval_s",
    "turn_radius_m",
)


class OptimizationVariable(BaseModel):
    """A single optimizable variable declaration.

    Only the fields relevant to ``mode`` are used: ``value`` (FIXED),
    ``min_value`` / ``max_value`` / ``step`` (RANGE) and ``values``
    (CANDIDATE_VALUES). Validation rejects inconsistent combinations.
    """

    name: str
    mode: VariableMode
    value: Optional[Any] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    values: list[Any] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_mode(self) -> "OptimizationVariable":
        if self.name not in OPTIMIZABLE_VARIABLES:
            allowed = ", ".join(OPTIMIZABLE_VARIABLES)
            raise ValueError(f"Unknown optimizable variable {self.name!r} (allowed: {allowed})")
        if self.mode is VariableMode.FIXED:
            if self.value is None:
                raise ValueError(f"Variable {self.name!r} is FIXED but has no value")
        elif self.mode is VariableMode.RANGE:
            missing = [f for f in ("min_value", "max_value", "step") if getattr(self, f) is None]
            if missing:
                raise ValueError(f"Variable {self.name!r} is RANGE but {', '.join(missing)} missing")
            if self.min_value > self.max_value:
                raise ValueError(f"Variable {self.name!r}: min_value > max_value ({self.min_value} > {self.max_value})")
            if self.step <= 0:
                raise ValueError(f"Variable {self.name!r}: step must be > 0 (got {self.step})")
        elif not self.values:
            raise ValueError(f"Variable {self.name!r} is CANDIDATE_VALUES but has no values")
        return self


class OptimizationVariables(BaseModel):
    """Ordered set of optimizable variables (insertion order = search order)."""

    variables: list[OptimizationVariable] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_non_empty(self) -> "OptimizationVariables":
        if not self.variables:
            raise ValueError("OptimizationVariables requires at least one variable")
        return self

    @property
    def names(self) -> list[str]:
        """Variable names in insertion order."""
        return [v.name for v in self.variables]


# ── Expansion ────────────────────────────────────────────────────────────────


def expand_variable(variable: OptimizationVariable) -> list[Any]:
    """Expand a single variable into its deterministic candidate value list."""
    if variable.mode is VariableMode.FIXED:
        return [variable.value]
    if variable.mode is VariableMode.RANGE:
        return _expand_range(variable.min_value, variable.max_value, variable.step)
    return list(variable.values)


def expand_variables(variables: OptimizationVariables) -> dict[str, list[Any]]:
    """Expand every variable into the ``variable_values`` mapping.

    The dict preserves the insertion order of ``variables``, which fixes the
    cartesian iteration order of the candidate generator.
    """
    return {v.name: expand_variable(v) for v in variables.variables}


def _expand_range(min_value: float, max_value: float, step: float) -> list[float]:
    """Deterministic inclusive RANGE expansion (Decimal based, no drift)."""
    dmin = Decimal(str(min_value))
    dmax = Decimal(str(max_value))
    dstep = Decimal(str(step))
    count = int((dmax - dmin) // dstep)
    values = [float(dmin + dstep * i) for i in range(count + 1)]
    if values[-1] < max_value:
        values.append(max_value)
    return values


__all__ = [
    "OPTIMIZABLE_VARIABLES",
    "OptimizationVariable",
    "OptimizationVariables",
    "VariableMode",
    "expand_variable",
    "expand_variables",
]
