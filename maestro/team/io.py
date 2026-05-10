"""team.yaml read/write helpers — ADR-0004 (format) & ADR-0003 (location).

Three-state load semantics (absent / valid / invalid) and atomic save via
os.replace.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import yaml
from pydantic import ValidationError

from maestro.paths import team_config_path, project_home
from maestro.team.models import TeamConfig

# Header rewritten on every save (pyyaml does not preserve comments
# on round-trip per ADR-0004). User-added inline comments inside the
# file body are dropped on Web-UI saves.
_HEADER = (
    "# Maestro 团队配置文件，请通过 Web UI 编辑。\n"
    "# 启动 maestro-webui 后访问 http://localhost:19830/team\n"
    "# Schema 参考：docs/design/13-epic1-team-composition.md\n"
)


@dataclass(frozen=True)
class TeamConfigInvalid:
    """team.yaml exists but cannot be loaded as a valid TeamConfig.

    Distinct from "absent" (load_team_config returns None for that).
    `reason` is a short human-readable summary suitable for logs and
    wizard error display. `pydantic_error` is set when a Pydantic
    ValidationError caused the failure (carries field-level errors
    that the HTTP API surfaces as a 422 field-map). When YAML parsing
    itself failed, `pydantic_error` is None and `reason` carries the
    detail.
    """

    reason: str
    pydantic_error: ValidationError | None = None


def load_team_config(project_root: Union[Path, str]) -> TeamConfig | TeamConfigInvalid | None:
    """Read team.yaml from <project_root>/.maestro/team.yaml.

    Returns:
        None: file does not exist.
        TeamConfig: file parsed and validated.
        TeamConfigInvalid: file exists but YAML parse or schema validation failed.
    """
    target = team_config_path(project_root)
    if not target.exists():
        return None

    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        return TeamConfigInvalid(reason=f"failed to read team.yaml: {exc}")

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return TeamConfigInvalid(reason=f"yaml parse error: {exc}")

    if raw is None:
        return TeamConfigInvalid(reason="team.yaml is empty")
    if not isinstance(raw, dict):
        return TeamConfigInvalid(
            reason=f"team.yaml top-level must be a mapping, got {type(raw).__name__}"
        )

    try:
        return TeamConfig.model_validate(raw)
    except ValidationError as exc:
        return TeamConfigInvalid(
            reason="team.yaml failed schema validation", pydantic_error=exc
        )


def save_team_config(project_root: Union[Path, str], config: TeamConfig) -> None:
    """Write team.yaml atomically. Creates <project_root>/.maestro/ if absent.

    Header comment block is rewritten on every save (pyyaml does not
    preserve user comments — ADR-0004). Atomicity is via _atomic_write_text:
    a concurrent reader sees either the previous file or the new file,
    never a partial / torn read.
    """
    target = team_config_path(project_root)
    project_home(project_root).mkdir(parents=True, exist_ok=True)

    payload = config.model_dump()
    body = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    _atomic_write_text(target, _HEADER + body)


def _atomic_write_text(target: Path, content: str) -> None:
    """Write content to target atomically: write to <target>.tmp, then os.replace.

    On any failure during the write phase, removes the tmp file so callers
    do not need to clean up. The os.replace itself is atomic on POSIX.
    """
    tmp = target.with_suffix(target.suffix + ".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, target)
    except Exception:
        # Best-effort cleanup of the tmp file. If it doesn't exist (e.g. write_text
        # failed before creating it) the missing_ok=True keeps unlink quiet.
        tmp.unlink(missing_ok=True)
        raise
