"""
The machine-wide list of attached projects, `projects.json`.

r2 owns this file; a human does not edit it. It is a cache of what the
repositories say: the existence of `.reportlab/config.toml` is what attaches
a project, so loading always prunes entries whose folder or config is gone.
There is no loader that does not prune.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ValidationError

from r2.core.files import atomic_write
from r2.core.reports.project import Project, describe
from r2.web.paths import registry_file
from r2.web.state import now

__all__ = [
    "Loaded",
    "Registry",
    "RegistryEntry",
    "load_projects",
    "read_registry",
    "register",
    "unregister",
    "write_registry",
]


class RegistryEntry(BaseModel):
    id: str
    name: str
    root: str
    last_seen: str = ""


class Registry(BaseModel):
    projects: list[RegistryEntry] = []


def read_registry() -> Registry:
    try:
        raw = json.loads(registry_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Registry()
    entries = raw.get("projects") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        return Registry()
    projects: list[RegistryEntry] = []
    for entry in entries:
        try:
            projects.append(RegistryEntry.model_validate(entry))
        except ValidationError:
            continue
    return Registry(projects=projects)


def write_registry(registry: Registry) -> None:
    file = registry_file()
    file.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(file, registry.model_dump_json(indent=2) + "\n")


def register(project: Project) -> Registry:
    """Add or refresh a project, putting it first."""
    registry = read_registry()
    entry = RegistryEntry(
        id=project.id, name=project.name, root=str(project.root), last_seen=now()
    )
    others = [item for item in registry.projects if item.id != project.id]
    updated = Registry(projects=[entry, *others])
    write_registry(updated)
    return updated


def unregister(project_id: str) -> bool:
    """Drop a project. False when it was not there, which is not an error."""
    registry = read_registry()
    remaining = [item for item in registry.projects if item.id != project_id]
    if len(remaining) == len(registry.projects):
        return False
    write_registry(Registry(projects=remaining))
    return True


@dataclass(frozen=True)
class Loaded:
    projects: list[Project]
    #: Entries dropped because their folder or config is gone.
    removed: list[RegistryEntry]


def load_projects() -> Loaded:
    """
    Load every project, forgetting the ones no longer there or no longer
    attached. Only a line of the registry is deleted, nothing on disk.
    """
    registry = read_registry()
    projects: list[Project] = []
    removed: list[RegistryEntry] = []
    for entry in registry.projects:
        try:
            project = describe(Path(entry.root))
        except OSError:
            removed.append(entry)
            continue
        if project.attached:
            projects.append(project)
        else:
            removed.append(entry)
    if removed:
        gone = {entry.id for entry in removed}
        write_registry(
            Registry(projects=[e for e in registry.projects if e.id not in gone])
        )
    return Loaded(projects, removed)
