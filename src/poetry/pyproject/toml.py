from __future__ import annotations

from typing import TYPE_CHECKING

from packaging.utils import canonicalize_name
from poetry.core.packages.dependency import Dependency
from poetry.core.packages.dependency_group import MAIN_GROUP
from poetry.core.pyproject.toml import PyProjectTOML as BasePyProjectTOML
from tomlkit.api import table
from tomlkit.items import Table
from tomlkit.toml_document import TOMLDocument

from poetry.toml import TOMLFile


if TYPE_CHECKING:
    from pathlib import Path


class PyProjectTOML(BasePyProjectTOML):
    """
    Enhanced version of poetry-core's PyProjectTOML
    which is capable of writing pyproject.toml

    The poetry-core class uses tomli to read the file,
    here we use tomlkit to preserve comments and formatting when writing.
    """

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self._toml_file = TOMLFile(path=path)
        self._toml_document: TOMLDocument | None = None

    @property
    def file(self) -> TOMLFile:
        return self._toml_file

    @property
    def data(self) -> TOMLDocument:
        if self._toml_document is None:
            if not self.file.exists():
                self._toml_document = TOMLDocument()
            else:
                self._toml_document = self.file.read()

        return self._toml_document

    def _get_optional_dependency_names(self, optional: str) -> list[str]:
        if "project" in self.data and "optional-dependencies" not in self.data[
            "project"
        ].get("dynamic", {}):
            return [
                Dependency.create_from_pep_508(dep).name
                for dep in self.data["project"]
                .get("optional-dependencies", {})
                .get(optional, [])
            ]

        if not self.data.get("tool", {}).get("poetry", {}).get("extras", {}):
            return []

        return [
            canonicalize_name(name)
            for name in self.data["tool"]["poetry"]["extras"].get(optional, [])
        ]

    def _get_dependency_names_in_group(self, group: str) -> list[str]:
        if not self.data.get("tool", {}).get("poetry", {}).get("group", {}):
            return []

        return [
            canonicalize_name(name)
            for name in self.data["tool"]["poetry"]["group"]
            .get(group, {})
            .get("dependencies", [])
        ]

    def get_dependency_names(
        self, group: str = MAIN_GROUP, optional: str | None = None
    ) -> list[str]:
        if optional:
            return self._get_optional_dependency_names(optional)

        if group != MAIN_GROUP:
            return self._get_dependency_names_in_group(group)

        if "project" in self.data and "dependencies" not in self.data["project"].get(
            "dynamic", {}
        ):
            return [
                Dependency.create_from_pep_508(dep).name
                for dep in self.data["project"].get("dependencies", [])
            ]

        return [
            canonicalize_name(name)
            for name, constraint in self.data["tool"]["poetry"]
            .get("dependencies", {})
            .items()
            if isinstance(constraint, str) or not constraint.get("optional", False)
        ]

    def save(self) -> None:
        data = self.data

        if self._build_system is not None:
            if "build-system" not in data:
                data["build-system"] = table()

            build_system = data["build-system"]
            assert isinstance(build_system, Table)

            build_system["requires"] = self._build_system.requires
            build_system["build-backend"] = self._build_system.build_backend

        self.file.write(data=data)

    def reload(self) -> None:
        self._toml_document = None
        self._build_system = None
