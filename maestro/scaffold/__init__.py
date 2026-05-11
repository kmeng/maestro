"""Maestro project scaffolding engine.

Pure-logic core: operation taxonomy + plan generation. File I/O lives in
``maestro.scaffold.io`` (T2.2); pre-flight checks in
``maestro.scaffold.preflight`` (T2.3); template content in
``maestro.scaffold.templates`` (T2.4).

Public API:

- :class:`Operation` — what happens to a file (CREATE / APPEND_DELIMITED /
  NOOP / CONFLICT).
- :class:`ConflictReason` — finer-grained reason when op is CONFLICT.
- :class:`ReplacementFile`, :class:`MergeableFile`, :data:`FileSpec` — input
  shapes describing what Maestro wants to ensure on disk.
- :class:`PlanRow`, :class:`Plan` — the engine's output, one row per FileSpec.
- :func:`generate_plan` — the engine entry point.
"""
from __future__ import annotations

from .operations import (
    ConflictReason,
    FileSpec,
    MergeableFile,
    Operation,
    Plan,
    PlanRow,
    PreflightCheck,
    ReplacementFile,
)
from .engine import generate_plan
from .preflight import run_preflight

__all__ = [
    "Operation",
    "ConflictReason",
    "ReplacementFile",
    "MergeableFile",
    "FileSpec",
    "PlanRow",
    "Plan",
    "PreflightCheck",
    "generate_plan",
    "run_preflight",
]
