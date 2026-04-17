from pathlib import Path

import rich

from .utils import error, warn

ERRORS = {
    "package-forbidden": "Cannot specify a package when not using --py or --js",
}
BASH_ALIAS_PATH = Path.home() / ".bash_aliases"


def create_alias(py: bool, js: bool, package: str, alias: str, section: str):
    if [py, js].count(True) != 1:
        cmd = alias
        error(ERRORS["package-forbidden"], package != "")
    elif py and package:
        cmd = f"uvx --from {package} {alias}"
    elif py:
        cmd = f"uvx {alias}"
    elif js and package:
        cmd = f"npx --yes --package {package} {alias}"
    elif js:
        cmd = f"npx {alias}"
    else:
        raise RuntimeError("Invalid combination of options")

    alias_cmd = f"alias {alias}='{cmd}'\n"
    lines = BASH_ALIAS_PATH.read_text().splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"

    for line in lines:
        if line.startswith(f"alias {alias}="):
            error(f"Alias '{alias}' already exists.")

    section_header = "# " + (section or "other").strip().lower()

    start_aliases = None
    for i, line in enumerate(lines):
        if line.lower().strip() == section_header:
            start_aliases = i + 1
            break

    if start_aliases is None:
        lines.append(f"\n# {section or 'Other'}\n")
        if section:
            warn(f"Created new section '{section}' in {BASH_ALIAS_PATH}")
        lines.append(alias_cmd)
    elif start_aliases == len(lines):
        lines.append(alias_cmd)
    else:
        lines.insert(start_aliases, alias_cmd)

    BASH_ALIAS_PATH.write_text("".join(lines))
    rich.print(f"[b green]success[/]: Added alias '{alias}' to {BASH_ALIAS_PATH}")


def parse_sections() -> dict[str, list[tuple[str, str]]]:
    if not BASH_ALIAS_PATH.exists():
        return {}

    lines = BASH_ALIAS_PATH.read_text().splitlines()
    aliases: list[tuple[str, str]] = []
    sections = {"": aliases}

    for line in lines:
        line = line.strip()
        if line.startswith("# "):
            section = line[2:].strip()
            aliases = []
            sections[section] = aliases
        elif line.startswith("alias "):
            name, sep, value = line.partition("=")
            name = name.strip().removeprefix("alias").strip()
            if sep:
                aliases.append((name, value.strip()))

    return {k: v for k, v in sections.items() if v}


def get_path():
    return BASH_ALIAS_PATH
