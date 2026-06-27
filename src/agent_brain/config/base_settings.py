"""Base configuration for AI Waiter.

Project root resolution
-----------------------
- `find_project_root()` walks up from this file's directory looking for anchor
  files (`.git`, `pyproject.toml`, `README.md`, `package.xml`) and returns the
  first directory containing any of them. This makes the project relocatable —
  no more counting `parent.parent...` levels that break when files move.
- The `PROJECT_ROOT` env var (or `.env` entry) overrides the auto-detected
  root, useful for Docker / production deployments.
- `PACKAGE_ROOT` always points to the brain Python package
  (`src/agent_brain/`), resolved as `parents[1]`
  from this file.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


def find_project_root(start: Path = None, max_depth: int = 10) -> Path:
    """
    Walk up from `start` (default: this file's directory) looking for the
    project root.

    Anchors are checked in priority order — strongest signal first:
        1. `.git` — exists only at the true project root for a normal repo
        2. `pyproject.toml` — single source of project metadata

    We intentionally do NOT use `package.xml` or `README.md` as anchors because
    both exist at non-root levels in this project (every ROS package has its
    own `package.xml`; subprojects have their own `README.md`).

    Falls back to `parents[5]` (the original 6-parent chain) if no anchor is
    found within `max_depth` levels — defensive safety net for production /
    Docker environments where `.git` may be stripped.
    """
    start = (start or Path(__file__).resolve()).parent
    anchors = (".git", "pyproject.toml")

    current = start
    for _ in range(max_depth):
        if any((current / a).exists() for a in anchors):
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent

    return Path(__file__).resolve().parents[5]


ROOT = find_project_root()
PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class BaseSystemSettings(BaseSettings):
    PROJECT_ROOT: Path = Field(default=ROOT, env="PROJECT_ROOT")
    resources_dir: Path = Field(default=PACKAGE_ROOT / "agent" / "resources")
    storage_dir: Path = Field(default=ROOT / "storage")
    assets_dir: Path = Field(default=ROOT / "assets")
    inputs_dir: Path = Field(default=ROOT / "inputs")

    # Server network settings
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT", ge=1, le=65535)

    @field_validator("PROJECT_ROOT", mode="before")
    @classmethod
    def _coerce_empty_project_root(cls, v):
        # Pydantic converts "" -> Path(".") which would override our default
        # even with `env_ignore_empty=True`. Force fall-through to ROOT.
        if v is None or (isinstance(v, str) and not v.strip()):
            return ROOT
        return v

    # Absolute path anchored at the project root so .env loads regardless of CWD
    # (a relative ".env" is resolved against the current working directory).
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding='utf-8',
        extra="ignore",
        env_ignore_empty=True,
    )
