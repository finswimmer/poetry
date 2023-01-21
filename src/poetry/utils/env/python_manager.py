from __future__ import annotations

import contextlib
import subprocess
import sys

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

import pythonfinder

from poetry.core.constraints.version import Version

from poetry.config.config import Config
from poetry.utils._compat import decode
from poetry.utils.env.exceptions import NoCompatiblePythonVersionFound
from poetry.utils.env.script_strings import GET_PYTHON_VERSION_ONELINER


if TYPE_CHECKING:
    from poetry.poetry import Poetry


class Python:
    def __init__(
        self,
        executable: str | Path,
        python_version: Version | None = None,
        config: Config | None = None,
    ) -> None:
        self._config = config or Config.create()
        self._executable = Path(executable)
        self._python_version = python_version

    @property
    def executable(self) -> Path:
        if not Path(self._executable).is_absolute():
            if self._config.get("virtualenvs.prefer-active-python"):
                self._executable = Path(
                    decode(
                        subprocess.check_output(
                            [
                                self._executable,
                                "-c",
                                '"import sys; print(sys.executable)"',
                            ]
                        ),
                    ).strip()
                )
            else:
                finder = pythonfinder.Finder()
                self._executable = finder.which(str(self._executable)).path

        return self._executable

    @cached_property
    def python_version(self) -> Version:
        if not self._python_version:
            python_version = decode(
                subprocess.check_output(
                    [str(self.executable), "-c", GET_PYTHON_VERSION_ONELINER],
                    text=True,
                ).strip()
            )

            self._python_version = Version.parse(python_version)

        return self._python_version

    @staticmethod
    def _get_sys_version() -> Version:
        return Version.parse(".".join(str(v) for v in sys.version_info[:3]))

    @staticmethod
    def get_preferred_python(config: Config) -> Python:
        executable = sys.executable
        python_version: Version | None = Python._get_sys_version()

        if config.get("virtualenvs.prefer-active-python"):
            with contextlib.suppress(subprocess.CalledProcessError):
                executable = decode(
                    subprocess.check_output(
                        ["python3", "-c", '"import sys; print(sys.executable)"'],
                        text=True,
                    ).strip()
                )
                python_version = None

        return Python(executable=executable, python_version=python_version)

    @staticmethod
    def get_system_python() -> Python:
        python_version = Python._get_sys_version()

        return Python(executable=sys.executable, python_version=python_version)

    @staticmethod
    def get_compatible_python(poetry: Poetry) -> Python:
        supported_python = poetry.package.python_constraint
        executable = None
        python_version = None
        finder = pythonfinder.Finder()

        for python_to_try in finder.find_all_python_versions(3):
            python_version = Version.parse(str(python_to_try.py_version.version))
            if supported_python.allows(python_version):
                executable = python_to_try.path
                break

        if not executable:
            raise NoCompatiblePythonVersionFound(poetry.package.python_versions)

        return Python(executable=executable, python_version=python_version)

    @staticmethod
    def get_by_version(version: Version) -> Python:
        finder = pythonfinder.Finder()
        python = finder.find_python_version(version.to_string())

        if not python:
            raise NoCompatiblePythonVersionFound(version.to_string())

        executable = python.path
        python_version = Version.parse(str(python.py_version.version))

        return Python(executable=executable, python_version=python_version)
