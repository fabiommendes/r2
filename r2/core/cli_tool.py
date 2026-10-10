import os
import shutil
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Never, assert_never, cast

from r2.core import console
from r2.core.mode import mode

type CLIArg = str | int | float | bool


@dataclass(frozen=True)
class Completed:
    """
    Result of `CliTool.call`.
    """

    returncode: int
    stdout: str
    stderr: str


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
    install_hint: str = ""
    """How to install the program, shown when it is missing."""

    def __post_init__(self) -> None:
        if not self.name:
            object.__setattr__(self, "name", self.command)

    def available(self) -> bool:
        """
        Whether the program is on PATH.
        """
        return shutil.which(self.command) is not None

    def call(
        self,
        *args: CLIArg,
        _path: Path | None = None,
        _env: dict[str, str] | None = None,
        **kwargs: CLIArg,
    ) -> Completed:
        """
        Run the program and return its exit code and output. Never raises
        for a non-zero exit code; `on_error` and `parser` do not apply.
        Arguments render like `run`. `_env` is merged over the current
        environment.
        """
        cmd = self._command_line(args, kwargs)
        self._echo(cmd)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=_path,
            env=_merged_env(_env),
            stdin=subprocess.DEVNULL if mode.agent else None,
        )
        return Completed(result.returncode, result.stdout, result.stderr)

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

    def _command_line(
        self, args: Iterable[CLIArg], kwargs: dict[str, CLIArg]
    ) -> list[str]:
        """
        The program followed by the rendered positional and keyword arguments.
        """
        cmd_args = list(map(render_arg, args))
        for key, value in kwargs.items():
            if isinstance(value, bool):
                if value:
                    cmd_args.append(f"--{key.replace('_', '-')}")
                continue

            cmd_args.append(f"--{key.replace('_', '-')}")
            cmd_args.append(render_arg(value))
        return [self.command, *cmd_args]

    def _echo(self, cmd: list[str]) -> None:
        """
        Print the command line when `echo` is on.
        """
        if self.echo:
            msg = f"[b blue]$ :[/] [yellow]{' '.join(map(str, cmd))}[/]"
            console.stdout.print(msg)

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

        cmd = self._command_line(args, kwargs)
        parser = parser or self.parser
        self._echo(cmd)

        if exec:
            if path:
                os.chdir(path)
            os.execvpe(self.command, cmd, _merged_env(env) or os.environ)
            raise RuntimeError("os.execvpe failed to replace the current process")

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                cwd=path,
                env=_merged_env(env),
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


def _merged_env(env: dict[str, str] | None) -> dict[str, str] | None:
    """
    `env` merged over the current environment, or None to inherit it.
    """
    return None if env is None else {**os.environ, **env}
