"""
Collect the panes of every global plugin that declares any in plugin.toml.
"""

from __future__ import annotations

from dataclasses import dataclass

from r2.core.plugins.discovery import GlobalPlugin, Problem, discover_global
from r2.core.plugins.loader import PluginError, load_plugin
from r2.tui.pane import PluginPane

__all__ = ["PaneEntry", "load_panes"]


@dataclass(frozen=True)
class PaneEntry:
    """
    A pane class ready to be shown.
    """

    #: Unique tab id: "<plugin>--<pane>".
    id: str
    title: str
    cls: type[PluginPane]


def load_panes(
    plugins: list[GlobalPlugin] | None = None,
) -> tuple[list[PaneEntry], list[Problem]]:
    """
    Import plugins with `[panes.*]` in their manifest and match the declared
    panes with the classes registered by `@plugin.pane()`.

    A plugin that fails to import, or a pane that does not check out, is
    reported and skipped; the rest still load.
    """
    problems: list[Problem] = []
    if plugins is None:
        plugins, problems = discover_global()

    entries: list[PaneEntry] = []
    for plugin in plugins:
        if not plugin.panes:
            continue
        try:
            loaded = load_plugin(plugin)
        except PluginError as exc:
            problems.append(Problem(plugin.root, str(exc)))
            continue

        for name, spec in plugin.panes.items():
            cls = loaded.panes.get(name)
            if cls is None:
                msg = (
                    f"pane {name!r} is in plugin.toml "
                    "but not registered with @plugin.pane()"
                )
                problems.append(Problem(plugin.manifest, msg))
                continue
            if not (isinstance(cls, type) and issubclass(cls, PluginPane)):
                msg = f"pane {name!r} must subclass r2.tui.PluginPane"
                problems.append(Problem(plugin.manifest, msg))
                continue
            entries.append(PaneEntry(f"{plugin.name}--{name}", spec.title or name, cls))

        for name in loaded.panes.keys() - plugin.panes.keys():
            msg = f"pane {name!r} is registered but missing from plugin.toml"
            problems.append(Problem(plugin.manifest, msg))

    return entries, problems
