from __future__ import annotations

import contextlib
import subprocess
import sys

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

import pythonfinder

from poetry.core.constraints.version import Version

from poetry.utils._compat import decode
from poetry.utils.env.exceptions import NoCompatiblePythonVersionFound
from poetry.utils.env.script_strings import GET_PYTHON_VERSION_ONELINER


if TYPE_CHECKING:
    from poetry.config.config import Config
    from poetry.poetry import Poetry


class Python:
    def __init__(
        self, executable: str | Path, python_version: Version | None = None
    ) -> None:
        if not Path(executable).is_absolute():
            raise ValueError("Executable must be an absolute path.")

        self.executable = Path(executable)
        self._python_version = python_version

    @cached_property
    def python_version(self) -> Version:
        if not self._python_version:
            _python_version = decode(
                subprocess.check_output(
                    [str(self.executable), "-c", GET_PYTHON_VERSION_ONELINER],
                    text=True,
                ).strip()
            )

            self._python_version = Version.parse(_python_version)

        return self._python_version

    @staticmethod
    def _get_sys_version() -> Version:
        return Version.parse(".".join(str(v) for v in sys.version_info[:3]))

    @staticmethod
    def get_preferred_python(config: Config) -> Python:
        _executable = sys.executable
        _python_version: Version | None = Python._get_sys_version()

        if config.get("virtualenvs.prefer-active-python"):
            with contextlib.suppress(subprocess.CalledProcessError):
                _executable = decode(
                    subprocess.check_output(
                        ["python3", "-c", '"import sys; print(sys.executable)"'],
                        text=True,
                    ).strip()
                )
                _python_version = None

        return Python(executable=_executable, python_version=_python_version)

    @staticmethod
    def get_system_python() -> Python:
        _python_version = Python._get_sys_version()

        return Python(executable=sys.executable, python_version=_python_version)

    @staticmethod
    def get_compatible_python(poetry: Poetry) -> Python:
        supported_python = poetry.package.python_constraint
        _executable = None
        _python_version = None
        finder = pythonfinder.Finder()

        for python_to_try in finder.find_all_python_versions(3):
            _python_version = Version.parse(str(python_to_try.py_version.version))
            if supported_python.allows(
                Version.parse(str(python_to_try.py_version.version))
            ):
                _executable = python_to_try.path
                break

        if not _executable:
            raise NoCompatiblePythonVersionFound(poetry.package.python_versions)

        return Python(executable=_executable, python_version=_python_version)

    @staticmethod
    def get_by_version(version: Version) -> Python:
        finder = pythonfinder.Finder()
        python = finder.find_python_version(version.to_string())

        if not python:
            raise NoCompatiblePythonVersionFound(version.to_string())

        _executable = python.path
        _python_version = Version.parse(str(python.py_version.version))

        return Python(executable=_executable, python_version=_python_version)
