"""Optimizer — mission scoring entry point (Fase 10B + 10E).

Fase 10E moved the scoring math to :mod:`app.modules.optimizer.preferences`
(continuous utility functions + scoring breakdown). This module keeps the
historical ``score_mission`` name and signature so callers import scoring from
one stable place. Feasibility is deliberately out of scope here — the
constraint PASS/WARNING/FAIL fold lives in ``evaluator.py``.
"""

from __future__ import annotations

from app.modules.optimizer.preferences import score_mission

__all__ = ["score_mission"]
