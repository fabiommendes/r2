"""
Import a global plugin package on first use.
"""

from __future__ import annotations

import importlib.util
import sys

from r2.core.plugins.discovery import GlobalPlugin
from r2.plugin import Plugin

__all__ = ["PluginError", "load_plugin"]

PACKAGE_PREFIX = "r2_plugins"

_loaded: dict[str, Plugin] = {}


class PluginError(Exception):
    """
    A plugin package could not be imported or does not define `plugin`.
    """


def load_plugin(plugin: GlobalPlugin) -> Plugin:
    """
    Import `<root>/__init__.py` as the package `r2_plugins.<name>` and return
    its `plugin` object. Raises PluginError with a message pointing at the file.
    """
    if plugin.name in _loaded:
        return _loaded[plugin.name]

    module_name = f"{PACKAGE_PREFIX}.{plugin.name}"
    init = plugin.root / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        module_name, init, submodule_search_locations=[str(plugin.root)]
    )
    if spec is None or spec.loader is None:
        raise PluginError(f"cannot import plugin {plugin.name!r} from {init}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        error = f"{type(exc).__name__}: {exc}"
        msg = f"plugin {plugin.name!r} failed to import ({init}): {error}"
        raise PluginError(msg) from exc

    obj = getattr(module, "plugin", None)
    if not isinstance(obj, Plugin):
        expected = "plugin = r2.plugin.Plugin(...)"
        msg = f"plugin {plugin.name!r} must define `{expected}` in {init}"
        raise PluginError(msg)

    _loaded[plugin.name] = obj
    return obj


def reset() -> None:
    """
    Forget imported plugins. For tests.
    """
    for name in list(_loaded):
        sys.modules.pop(f"{PACKAGE_PREFIX}.{name}", None)
    _loaded.clear()
