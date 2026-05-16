"""Pydantic contract for team.yaml (ADR-0004 + design 13).

Pure data models, no I/O. Validates role set, member/model strings,
alias uniqueness, and schema version.
"""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

ROLE_IDS: tuple[str, ...] = ("coder", "librarian", "reviewer", "scribe")

# Shipped infrastructure tools — dispatched like roles, but not user-
# configurable via team.yaml. No team member is assigned; the MCP server
# uses DEFAULT_MODELS for these directly.
SHIPPED_TOOL_IDS: tuple[str, ...] = ("verifier", "spec-writer")

# DEFAULT_MODELS sourced from Epic 5's worker fleet design (docs/design/52-...).
# For ROLE_IDS entries, the wizard pre-fills these and the MCP server uses
# them when team.yaml is absent. For SHIPPED_TOOL_IDS entries (verifier
# and future), the MCP server always uses these — team.yaml does not
# configure them.
# Typed as dict[str, str] (not dict[RoleId, str]) for ergonomic use without
# importing the Literal alias at every call site.
DEFAULT_MODELS: dict[str, str] = {
    "coder": "deepseek-v4-pro",
    "librarian": "deepseek-v4-flash",
    "reviewer": "deepseek-v4-pro",
    "scribe": "deepseek-v4-flash",
    "verifier": "deepseek-v4-flash",
    "spec-writer": "deepseek-v4-flash",
}

RoleId = Literal["coder", "librarian", "reviewer", "scribe", "verifier", "spec-writer"]


class RoleEntry(BaseModel):
    """A single role's member alias and model assignment."""

    member: str
    model: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("member")
    @classmethod
    def _validate_member(cls, v: str) -> str:
        """Refuse control characters anywhere, then strip and check length.

        Control-char check runs on the raw input — strip would silently
        discard \\n / \\t and we want to reject those, not normalise them.
        """
        if any(ord(c) < 0x20 or ord(c) == 0x7F for c in v):
            raise ValueError("member must not contain control characters")
        stripped = v.strip()
        if not stripped:
            raise ValueError("member must not be empty after stripping whitespace")
        if len(stripped) > 64:
            raise ValueError("member must be at most 64 characters")
        return stripped

    @field_validator("model")
    @classmethod
    def _validate_model(cls, v: str) -> str:
        """Strip, refuse empty, length ≤128, enforce lowercase slug pattern."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("model must not be empty after stripping whitespace")
        if len(stripped) > 128:
            raise ValueError("model must be at most 128 characters")
        if re.fullmatch(r"[a-z0-9][a-z0-9._-]*", stripped) is None:
            raise ValueError("model must match pattern '^[a-z0-9][a-z0-9._-]*$'")
        return stripped


class TeamConfig(BaseModel):
    """Top-level team configuration with version and role mappings."""

    schema_version: int
    roles: dict[RoleId, RoleEntry]

    model_config = ConfigDict(extra="forbid")

    @field_validator("schema_version")
    @classmethod
    def _check_schema_version(cls, v: int) -> int:
        if v != 1:
            raise ValueError("schema_version must be 1 (v0.0.3 only supports version 1)")
        return v

    @model_validator(mode="after")
    def _validate_role_set_and_aliases(self) -> "TeamConfig":
        """Guarantee exactly the four required roles and unique aliases."""
        # Role-set: pydantic's Literal already rejects unknown keys; this
        # catches the missing-keys case (partial configs).
        if set(self.roles.keys()) != set(ROLE_IDS):
            raise ValueError(
                f"roles must contain exactly {ROLE_IDS}, got {sorted(self.roles.keys())}"
            )

        # Alias uniqueness: case-insensitive + whitespace-trimmed comparison
        # prevents users from accidentally giving two roles the same person.
        seen: dict[str, list[tuple[str, str]]] = {}
        for role_id, entry in self.roles.items():
            key = entry.member.strip().lower()
            seen.setdefault(key, []).append((role_id, entry.member))

        for entries in seen.values():
            if len(entries) > 1:
                first_role, first_member = entries[0]
                roles = sorted([role for role, _ in entries])
                raise ValueError(
                    f"member alias '{first_member}' is used by multiple roles: {roles}"
                )

        return self
