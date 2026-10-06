import os
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Never, assert_never, cast

from r2.core import console
from r2.core.mode import mode

type CLIArg = str | int | float | bool


@dataclass(frozen=True)
class CliTool[T = str]:
    """
    Abstracts a CLI tool, providing a unified interface for executing commands
    and handling errors.
    """

    command: str
    name: str = ""
    echo: bool = True
    on_error: Literal["log", "ignore", "raise"] = "raise"
    parser: Callable[[str], T] = lambda x: cast(T, x)

    def __post_init__(self) -> None:
        if not self.name:
            object.__setattr__(self, "name", self.command)

    def run(
        self,
        *args: CLIArg,
        _parser: Callable[[str], T] | None = None,
        _path: Path | None = None,
        _env: dict[str, str] | None = None,
        **kwargs: CLIArg,
    ) -> T:
        """
        Execute the CLI tool with the provided arguments and keyword arguments.
        """
        return self._run_or_exec(args, kwargs, parser=_parser, path=_path, env=_env)

    def exec(
        self,
        *args: CLIArg,
        _parser: Callable[[str], T] | None = None,
        _path: Path | None = None,
        _env: dict[str, str] | None = None,
        **kwargs: CLIArg,
    ) -> Never:
        """
        Execute the CLI tool with the provided arguments and keyword arguments,
        replacing the current process.
        """
        self._run_or_exec(args, kwargs, parser=_parser, path=_path, env=_env, exec=True)
        raise RuntimeError("os.execvpe failed to replace the current process")

    def _run_or_exec(
        self,
        args: Iterable[CLIArg],
        kwargs: dict[str, CLIArg],
        parser: Callable[[str], T] | None = None,
        path: Path | None = None,
        env: dict[str, str] | None = None,
        exec: bool = False,
    ) -> T:
        """
        Execute the CLI tool with the provided arguments and keyword arguments.
        """

        cmd_args = list(map(render_arg, args))
        for key, value in kwargs.items():
            if isinstance(value, bool):
                if value:
                    cmd_args.append(f"--{key.replace('_', '-')}")
                continue

            cmd_args.append(f"--{key.replace('_', '-')}")
            cmd_args.append(render_arg(value))

        cmd = [self.command, *cmd_args]
        parser = parser or self.parser

        if self.echo:
            msg = f"[b blue]$ :[/] [yellow]{' '.join(map(str, cmd))}[/]"
            console.stdout.print(msg)

        if exec:
            if path:
                os.chdir(path)
            os.execvpe(self.command, cmd, env or os.environ)
            raise RuntimeError("os.execvpe failed to replace the current process")

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                cwd=path,
                env=env,
                stdin=subprocess.DEVNULL if mode.agent else None,
            )
        except subprocess.CalledProcessError as e:
            match self.on_error:
                case "ignore":
                    return parser("error:\n" + e.stderr)
                case "raise":
                    raise
                case "log":
                    console.stderr.print(f"[b red]Error:[/] {e}")
                    return parser("error:\n" + e.stderr)
                case other:
                    assert_never(other)
        else:
            return parser(result.stdout)


def render_arg(arg: CLIArg) -> str:
    if isinstance(arg, bool):
        return "1" if arg else "0"
    return str(arg)
