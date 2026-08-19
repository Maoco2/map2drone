"""Optimizer — deterministic candidate generator (Fase 10C-1).

Generates the cartesian product of the configured optimisation variables with
protection against combinatorial explosion. Determinism is a hard guarantee:
the same input produces exactly the same set and order of candidates (no
randomness anywhere).

Strategy when the full product exceeds ``max_candidates``
----------------------------------------------------------
The generator never fails silently and never drops candidates without
documenting it. ``CandidateGenerationResult`` reports ``total_possible`` (the
full product) and ``generated`` (what was actually produced). The limiting
strategy is **deterministic decimation**: the variable with the fewest values
(above one) is reduced (to ``ceil(len / 2)``, keeping the first, the last and
evenly spaced interior values), iterating until the product fits — preserving
the resolution and the endpoints of the variables that carry the most values.
When the full product fits, the strategy is ``full_cartesian``.

The generator is variable-name agnostic: every variable contributes a list of
candidate values (``int`` / ``float`` / ``str``, e.g. ``turn_radius = ["AUTO"]``).
The semantic meaning of each variable (engine input vs. post-check) belongs to
the later integration steps (10C-4/5/6).
"""

from __future__ import annotations

import itertools
from typing import Any, Iterable

from app.modules.optimizer.models import (
    DEFAULT_MAX_CANDIDATES,
    CandidateConfig,
    CandidateGenerationResult,
)


class CandidateGenerator:
    """Deterministic cartesian generator for optimisation variables.

    Args:
        variable_values: mapping ``name -> ordered candidate values``. The
            insertion order defines the cartesian iteration order.
        max_candidates: hard cap on generated candidates (>= 1).

    Raises:
        ValueError: empty variable set, empty value list or invalid limit.
    """

    def __init__(self, variable_values: dict[str, list[Any]], max_candidates: int = DEFAULT_MAX_CANDIDATES):
        if not variable_values:
            raise ValueError("variable_values must contain at least one variable")
        if max_candidates < 1:
            raise ValueError(f"max_candidates must be >= 1 (got {max_candidates})")
        self._max_candidates = max_candidates
        self._names = list(variable_values)
        self._lists: dict[str, list[Any]] = {}
        for name, values in variable_values.items():
            values = _dedup_ordered(values)
            if not values:
                raise ValueError(f"Variable {name!r} has no candidate values")
            self._lists[name] = values

    # ── Queries ─────────────────────────────────────────────────────────────

    @property
    def variables(self) -> list[str]:
        """Optimisable variable names (insertion order)."""
        return list(self._names)

    @property
    def max_candidates(self) -> int:
        return self._max_candidates

    def total_possible(self) -> int:
        """Size of the full cartesian product (before any limiting)."""
        return _product([len(self._lists[n]) for n in self._names])

    # ── Generation ──────────────────────────────────────────────────────────

    def generate(self) -> CandidateGenerationResult:
        """Generate the deterministic candidate set.

        Returns a :class:`CandidateGenerationResult` that always documents how
        many candidates were possible and how many were generated.
        """
        total_possible = self.total_possible()
        fitted = self._fit_lists(self._lists, self._max_candidates)
        generated = _product([len(fitted[n]) for n in self._names])
        truncated = total_possible > self._max_candidates
        strategy = "deterministic_decimation" if truncated else "full_cartesian"

        candidates: list[CandidateConfig] = []
        for index, combo in enumerate(itertools.product(*(fitted[n] for n in self._names))):
            values = {n: v for n, v in zip(self._names, combo)}
            candidates.append(
                CandidateConfig(
                    index=index,
                    label=_build_label(self._names, values),
                    values=values,
                )
            )

        return CandidateGenerationResult(
            variables=list(self._names),
            total_possible=total_possible,
            generated=generated,
            truncated=truncated,
            strategy=strategy,
            candidates=candidates,
        )

    # ── Explosion protection (deterministic) ────────────────────────────────

    def _fit_lists(self, lists: dict[str, list[Any]], limit: int) -> dict[str, list[Any]]:
        fitted = {name: list(values) for name, values in lists.items()}
        while _product([len(fitted[n]) for n in self._names]) > limit:
            target = _smallest_reducible_name(fitted, self._names)
            if target is None:
                break
            keep = max(1, _ceil_half(len(fitted[target])))
            fitted[target] = _decimate(fitted[target], keep)
        return fitted


# ── Internal helpers (deterministic) ────────────────────────────────────────


def _dedup_ordered(values: Iterable[Any]) -> list[Any]:
    """Remove duplicates while preserving first-seen order."""
    return list(dict.fromkeys(values))


def _product(sizes: list[int]) -> int:
    result = 1
    for size in sizes:
        result *= size
    return result


def _ceil_half(n: int) -> int:
    return (n + 1) // 2


def _smallest_reducible_name(lists: dict[str, list[Any]], names: list[str]) -> str | None:
    """Variable with the fewest values above 1 (ties → first in order).

    Reducing the smallest dimension first keeps the resolution (and the
    first/last endpoints) of the variables that carry the most values.
    Returns ``None`` when every list already has a single value.
    """
    best = None
    best_len = None
    for name in names:
        length = len(lists[name])
        if length > 1 and (best_len is None or length < best_len):
            best, best_len = name, length
    return best


def _decimate(values: list[Any], keep: int) -> list[Any]:
    """Deterministically reduce ``values`` to ``keep``, preserving first/last.

    Interior values are chosen at evenly spaced indices (rounding down), so the
    same input always yields the same output.
    """
    n = len(values)
    if keep <= 0 or keep >= n:
        return list(values)
    if keep == 1:
        return [values[0]]
    step = (n - 1) / (keep - 1)
    indices = sorted({int(round(i * step)) for i in range(keep)})
    if indices[0] != 0:
        indices.insert(0, 0)
    if indices[-1] != n - 1:
        indices.append(n - 1)
    indices = sorted(set(indices))
    return [values[i] for i in indices]


def _fmt_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _build_label(names: list[str], values: dict[str, Any]) -> str:
    return " | ".join(f"{name}={_fmt_value(values[name])}" for name in names)


__all__ = ["CandidateGenerator", "DEFAULT_MAX_CANDIDATES"]
