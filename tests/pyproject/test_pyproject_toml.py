from __future__ import annotations

import uuid

from typing import TYPE_CHECKING

from poetry.pyproject.toml import PyProjectTOML


if TYPE_CHECKING:
    from pathlib import Path


def test_pyproject_toml_reload(pyproject_toml: Path, poetry_section: str) -> None:
    pyproject = PyProjectTOML(pyproject_toml)
    name_original = pyproject.poetry_config["name"]
    name_new = str(uuid.uuid4())

    pyproject.poetry_config["name"] = name_new
    assert isinstance(pyproject.poetry_config["name"], str)
    assert pyproject.poetry_config["name"] == name_new

    pyproject.reload()
    assert pyproject.poetry_config["name"] == name_original


def test_pyproject_toml_save(
    pyproject_toml: Path, poetry_section: str, build_system_section: str
) -> None:
    pyproject = PyProjectTOML(pyproject_toml)

    name = str(uuid.uuid4())
    build_backend = str(uuid.uuid4())
    build_requires = str(uuid.uuid4())

    pyproject.poetry_config["name"] = name
    pyproject.build_system.build_backend = build_backend
    pyproject.build_system.requires.append(build_requires)

    pyproject.save()

    pyproject = PyProjectTOML(pyproject_toml)

    assert isinstance(pyproject.poetry_config["name"], str)
    assert pyproject.poetry_config["name"] == name
    assert pyproject.build_system.build_backend == build_backend
    assert build_requires in pyproject.build_system.requires


def test_get_dependency_names_from_project(tmp_path: Path) -> None:
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        """\
        [project]
        name="simple"
        version="0.1.0"
        dependencies = [
            "foo",
            "bar>=1.0",
            "Foo_bar"
        ]
        """
    )
    pyproject = PyProjectTOML(pyproject_toml)
    assert pyproject.get_dependency_names() == ["foo", "bar", "foo-bar"]


def test_get_dependency_names_from_project_no_dependencies_yet(tmp_path: Path) -> None:
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        """\
        [project]
        name="simple"
        version="0.1.0"
        """
    )
    pyproject = PyProjectTOML(pyproject_toml)
    assert pyproject.get_dependency_names() == []


def test_get_dependency_names_from_poetry(tmp_path: Path) -> None:
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        """\
        [tool.poetry]
        name="simple"
        version="0.1.0"

        [tool.poetry.dependencies]
        foo = "*"
        bar = ">=1.0"
        Foo_bar = { version = "*" }
        """
    )
    pyproject = PyProjectTOML(pyproject_toml)
    assert pyproject.get_dependency_names() == ["foo", "bar", "foo-bar"]


def test_get_dependency_names_from_poetry_no_depencies_yet(tmp_path: Path) -> None:
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        """\
        [tool.poetry]
        name="simple"
        version="0.1.0"
        """
    )
    pyproject = PyProjectTOML(pyproject_toml)
    assert pyproject.get_dependency_names() == []


def test_get_dependency_names_dynamic(tmp_path: Path) -> None:
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        """\
        [project]
        name="simple"
        version="0.1.0"
        dynamic = ["dependencies"]

        [tool.poetry.dependencies]
        foo = "*"
        bar = ">=1.0"
        Foo_bar = { version = "*" }
        """
    )
    pyproject = PyProjectTOML(pyproject_toml)
    assert pyproject.get_dependency_names() == ["foo", "bar", "foo-bar"]


def test_get_optional_dependency_names_from_project(tmp_path: Path) -> None:
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        """\
        [project]
        name="simple"
        version="0.1.0"
        dependencies = [
            "foo",
            "bar>=1.0",
        ]

        [project.optional-dependencies]
        testing = [
            "pytest",
            "Pytest-Cov>=1.2.3",
        ]
        """
    )
    pyproject = PyProjectTOML(pyproject_toml)

    assert pyproject.get_dependency_names() == ["foo", "bar"]
    assert pyproject.get_dependency_names(optional="testing") == [
        "pytest",
        "pytest-cov",
    ]


def test_get_optional_dependency_names_from_project_no_deps_yet(tmp_path: Path) -> None:
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        """\
        [project]
        name="simple"
        version="0.1.0"
        dependencies = [
            "foo",
            "bar>=1.0",
        ]
        """
    )
    pyproject = PyProjectTOML(pyproject_toml)

    assert pyproject.get_dependency_names() == ["foo", "bar"]
    assert pyproject.get_dependency_names(optional="testing") == []


def test_get_optional_dependency_names_from_poetry(tmp_path: Path) -> None:
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        """\
        [tool.poetry]
        name="simple"
        version="0.1.0"

        [tool.poetry.dependencies]
        foo = "*"
        bar = ">=1.0"
        pytest = {version="*", optional=true}
        Pytest-Cov = {version=">=1.2.3", optional=true}

        [tool.poetry.extras]
        testing = ["pytest", "Pytest-Cov"]
        """
    )
    pyproject = PyProjectTOML(pyproject_toml)

    assert pyproject.get_dependency_names() == ["foo", "bar"]
    assert pyproject.get_dependency_names(optional="testing") == [
        "pytest",
        "pytest-cov",
    ]


def test_get_optional_dependency_names_from_poetry_no_deps_yet(tmp_path: Path) -> None:
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        """\
        [tool.poetry]
        name="simple"
        version="0.1.0"

        [tool.poetry.dependencies]
        foo = "*"
        bar = ">=1.0"
        """
    )
    pyproject = PyProjectTOML(pyproject_toml)

    assert pyproject.get_dependency_names() == ["foo", "bar"]
    assert pyproject.get_dependency_names(optional="testing") == []


def test_get_optional_dependency_names_dynamic(tmp_path: Path) -> None:
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        """\
        [project]
        name="simple"
        version="0.1.0"
        dependencies = [
            "foo",
            "bar>=1.0",
        ]
        dynamic = ["optional-dependencies"]

        [tool.poetry.dependencies]
        pytest = {version="*", optional=true}
        pytest-cov = {version=">=1.2.3", optional=true}

        [tool.poetry.extras]
        testing = ["pytest", "pytest-cov"]
        """
    )
    pyproject = PyProjectTOML(pyproject_toml)

    assert pyproject.get_dependency_names() == ["foo", "bar"]
    assert pyproject.get_dependency_names(optional="testing") == [
        "pytest",
        "pytest-cov",
    ]


def test_get_dependency_names_from_poetry_groups(tmp_path: Path) -> None:
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        """\
        [tool.poetry]
        name="simple"
        version="0.1.0"

        [tool.poetry.dependencies]
        foo = "*"
        bar = ">=1.0"

        [tool.poetry.group.testing.dependencies]
        pytest = "*"
        Pytest-Cov = {version=">=1.2.3"}
        """
    )
    pyproject = PyProjectTOML(pyproject_toml)

    assert pyproject.get_dependency_names() == ["foo", "bar"]
    assert pyproject.get_dependency_names(group="testing") == [
        "pytest",
        "pytest-cov",
    ]


def test_get_dependency_names_from_poetry_groups_group_not_found(
    tmp_path: Path,
) -> None:
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        """\
        [tool.poetry]
        name="simple"
        version="0.1.0"

        [tool.poetry.dependencies]
        foo = "*"
        bar = ">=1.0"

        [tool.poetry.group.testing.dependencies]
        pytest = "*"
        pytest-cov = {version=">=1.2.3"}
        """
    )
    pyproject = PyProjectTOML(pyproject_toml)

    assert pyproject.get_dependency_names(group="docs") == []


def test_get_dependency_names_from_poetry_groups_no_groups_yet(tmp_path: Path) -> None:
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        """\
        [tool.poetry]
        name="simple"
        version="0.1.0"

        [tool.poetry.dependencies]
        foo = "*"
        bar = ">=1.0"
        """
    )
    pyproject = PyProjectTOML(pyproject_toml)

    assert pyproject.get_dependency_names(group="docs") == []
