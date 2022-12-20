from __future__ import annotations

import subprocess

from functools import cached_property
from pathlib import Path

from poetry.core.constraints.version import Version

from poetry.utils._compat import decode
from poetry.utils.env.script_strings import GET_PYTHON_VERSION_ONELINER


class Python:
    def __init__(self, executable: str | Path) -> None:
        if not Path(executable).is_absolute():
            raise ValueError("Executable must be an absolute path.")

        self.executable = Path(executable)

    @cached_property
    def python_version(self) -> Version:
        _python_version = decode(
            subprocess.check_output(
                [str(self.executable), "-c", GET_PYTHON_VERSION_ONELINER],
                text=True,
            ).strip()
        )

        return Version.parse(_python_version)
