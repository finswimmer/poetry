from __future__ import annotations

import contextlib
import dataclasses

from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar

from cleo.helpers import argument
from cleo.helpers import option
from packaging.utils import canonicalize_name
from poetry.core.packages.dependency import Dependency
from poetry.core.packages.dependency_group import MAIN_GROUP
from tomlkit.toml_document import TOMLDocument

from poetry.console.commands.env_command import EnvCommand
from poetry.console.commands.init import InitBase
from poetry.console.commands.init import InitCommand
from poetry.console.commands.installer_command import InstallerCommand


if TYPE_CHECKING:
    from collections.abc import Collection

    from cleo.io.inputs.argument import Argument
    from cleo.io.inputs.option import Option
    from cleo.io.io import IO
    from packaging.utils import NormalizedName

    from poetry.installation import Installer
    from poetry.poetry import Poetry
    from poetry.repositories import RepositoryPool
    from poetry.utils.env import Env


class AddCommandHandler(InitBase):
    def __init__(
        self,
        poetry: Poetry,
        env: Env | None,
        pool: RepositoryPool,
        io: IO,
        installer: Installer,
    ) -> None:
        super().__init__(poetry, env, pool, io)

        self.installer = installer

        # tomlkit types are awkward to work with, treat content as a mostly untyped
        # dictionary.
        from tomlkit import table

        self._content: dict[str, Any] = self.poetry.file.read()
        self._project_content = self._content.get("project", table())
        self._poetry_content = self._content.get("tool", {}).get("poetry", table())
        self._project_name = (
            canonicalize_name(name)
            if (
                name := self._project_content.get(
                    "name", self._poetry_content.get("name")
                )
            )
            else None
        )

    @staticmethod
    def get_existing_packages_from_input(
        packages: list[str],
        section: dict[str, Any],
        project_dependencies: Collection[NormalizedName],
    ) -> list[str]:
        existing_packages = []

        for name in packages:
            normalized_name = canonicalize_name(name)
            if normalized_name in project_dependencies:
                existing_packages.append(name)
                continue
            for key in section:
                if normalized_name == canonicalize_name(key):
                    existing_packages.append(name)

        return existing_packages

    @classmethod
    def _hint_update_packages(cls) -> str:
        return (
            "\nIf you want to update it to the latest compatible version, you can use"
            " `poetry update package`.\nIf you prefer to upgrade it to the latest"
            " available version, you can use `poetry add package@latest`.\n"
        )

    def notify_about_existing_packages(self, existing_packages: list[str]) -> None:
        self.io.write_line(
            "The following packages are already present in the pyproject.toml and will"
            " be skipped:\n"
        )
        for name in existing_packages:
            self.io.write_line(f"  - <c1>{name}</c1>")
        self.io.write_line(self._hint_update_packages())

    def _add_dependency_to_extras(
        self, dependency: Dependency, extra_name: NormalizedName
    ) -> None:
        extras = dict(self.poetry.package.extras)
        extra_deps = []
        replaced = False
        for dep in extras.get(extra_name, ()):
            if dep.name == dependency.name:
                extra_deps.append(dependency)
                replaced = True
            else:
                extra_deps.append(dep)
        if not replaced:
            extra_deps.append(dependency)
        extras[extra_name] = extra_deps
        self.poetry.package.extras = extras

    def add(
        self, options: AddOptions, lock: bool = False, dry_run: bool = False
    ) -> int:
        from poetry.core.constraints.generic import parse_constraint
        from tomlkit import array
        from tomlkit import inline_table
        from tomlkit import nl
        from tomlkit import table

        from poetry.factory import Factory

        use_project_section = False
        project_dependency_names = []
        if options.group == MAIN_GROUP:
            if (
                "dependencies" in self._project_content
                or "optional-dependencies" in self._project_content
            ):
                use_project_section = True
                if options.optional:
                    project_section = self._project_content.get(
                        "optional-dependencies", {}
                    ).get(options.optional, array())
                else:
                    project_section = self._project_content.get("dependencies", array())
                project_dependency_names = [
                    Dependency.create_from_pep_508(dep).name for dep in project_section
                ]
            else:
                project_section = array()

            poetry_section = self._poetry_content.get("dependencies", table())
        else:
            if "group" not in self._poetry_content:
                self._poetry_content["group"] = table(is_super_table=True)

            groups = self._poetry_content["group"]

            if options.group not in groups:
                groups[options.group] = table()
                groups.add(nl())

            this_group = groups[options.group]

            if "dependencies" not in this_group:
                this_group["dependencies"] = table()

            poetry_section = this_group["dependencies"]
            project_section = []

        existing_packages = self.get_existing_packages_from_input(
            options.packages, poetry_section, project_dependency_names
        )

        if existing_packages:
            self.notify_about_existing_packages(existing_packages)

        packages = [name for name in options.packages if name not in existing_packages]

        if not packages:
            self.io.write_line("Nothing to add.")
            return 0

        if options.optional and not use_project_section:
            self.io.write_error_line(
                "<warning>Optional dependencies will not be added to extras"
                " in legacy mode. Consider converting your project to use the [project]"
                " section.</warning>"
            )

        requirements = self._resolve_requirements(
            packages,
            allow_prereleases=options.allow_prereleases or None,
            source=options.source,
        )

        for _constraint in requirements:
            version = _constraint.get("version")
            if version is not None:
                # Validate version constraint
                assert isinstance(version, str)

                parse_constraint(version)

            constraint: dict[str, Any] = inline_table()
            for key, value in _constraint.items():
                if key == "name":
                    continue

                constraint[key] = value

            if options.optional:
                constraint["optional"] = True

            if options.allow_prereleases:
                constraint["allow-prereleases"] = True

            if options.extras:
                extras = []
                for extra in options.extras:
                    extras += extra.split()

                constraint["extras"] = extras

            if options.editable:
                if "git" in _constraint or "path" in _constraint:
                    constraint["develop"] = True
                else:
                    self.io.write_error_line(
                        "\n"
                        "<error>Failed to add packages. "
                        "Only vcs/path dependencies support editable installs. "
                        f"<c1>{_constraint['name']}</c1> is neither."
                    )
                    self.io.write_error_line("\nNo changes were applied.")
                    return 1

            if python := options.python:
                constraint["python"] = python

            if platform := options.platform:
                constraint["platform"] = platform

            if markers := options.markers:
                constraint["markers"] = markers

            if source := options.source:
                constraint["source"] = source

            if len(constraint) == 1 and "version" in constraint:
                constraint = constraint["version"]

            constraint_name = _constraint["name"]
            assert isinstance(constraint_name, str)

            canonical_constraint_name = canonicalize_name(constraint_name)

            if canonical_constraint_name == self._project_name:
                self.io.write_error_line(
                    f"<error>Cannot add dependency on <c1>{constraint_name}</c1> to"
                    " project with the same name."
                )
                self.io.write_error_line("\nNo changes were applied.")
                return 1

            with contextlib.suppress(ValueError):
                self.poetry.package.dependency_group(options.group).remove_dependency(
                    constraint_name
                )

            dependency = Factory.create_dependency(
                constraint_name,
                constraint,
                groups=[options.group],
                root_dir=self.poetry.file.path.parent,
            )
            self.poetry.package.add_dependency(dependency)

            if use_project_section:
                try:
                    index = project_dependency_names.index(canonical_constraint_name)
                except ValueError:
                    project_section.append(dependency.to_pep_508())
                else:
                    project_section[index] = dependency.to_pep_508()

                # create a second constraint for tool.poetry.dependencies with keys
                # that cannot be stored in the project section
                poetry_constraint: dict[str, Any] = inline_table()
                if not isinstance(constraint, str):
                    for key in ["allow-prereleases", "develop", "source"]:
                        if value := constraint.get(key):
                            poetry_constraint[key] = value
                    if poetry_constraint:
                        # add marker related keys to avoid ambiguity
                        for key in ["python", "platform"]:
                            if value := constraint.get(key):
                                poetry_constraint[key] = value
            else:
                poetry_constraint = constraint

            if poetry_constraint:
                for key in poetry_section:
                    if canonicalize_name(key) == canonical_constraint_name:
                        poetry_section[key] = poetry_constraint
                        break
                else:
                    poetry_section[constraint_name] = poetry_constraint

            if options.optional:
                extra_name = canonicalize_name(options.optional)
                # _in_extras must be set after converting the dependency to PEP 508
                # and adding it to the project section to avoid a redundant extra marker
                dependency._in_extras = [extra_name]
                self._add_dependency_to_extras(dependency, extra_name)

        # Refresh the locker
        if project_section:
            assert options.group == MAIN_GROUP
            if options.optional:
                if "optional-dependencies" not in self._project_content:
                    self._project_content["optional-dependencies"] = table()
                if (
                    options.optional
                    not in self._project_content["optional-dependencies"]
                ):
                    self._project_content["optional-dependencies"][options.optional] = (
                        project_section
                    )
            elif "dependencies" not in self._project_content:
                self._project_content["dependencies"] = project_section
        if poetry_section:
            if "tool" not in self._content:
                self._content["tool"] = table()
            if "poetry" not in self._content["tool"]:
                self._content["tool"]["poetry"] = self._poetry_content
            if (
                options.group == MAIN_GROUP
                and "dependencies" not in self._poetry_content
            ):
                self._poetry_content["dependencies"] = poetry_section
        self.poetry.locker.set_pyproject_data(self._content)
        self.installer.set_locker(self.poetry.locker)

        # Cosmetic new line
        self.io.write_line("")

        self.installer.set_package(self.poetry.package)
        self.installer.dry_run(dry_run)
        self.installer.verbose(self.io.is_verbose())
        self.installer.update(True)
        self.installer.execute_operations(not lock)

        self.installer.whitelist([r["name"] for r in requirements])

        status = self.installer.run()

        if status == 0 and not dry_run:
            assert isinstance(self._content, TOMLDocument)
            self.poetry.file.write(self._content)

        return status


@dataclasses.dataclass
class AddOptions:
    packages: list[str]
    group: str
    extras: list[str] = dataclasses.field(default_factory=list)
    editable: bool = False
    optional: str | None = None
    python: str | None = None
    platform: str | None = None
    source: str | None = None
    markers: str | None = None
    allow_prereleases: bool = False

    def __post_init__(self) -> None:
        if len(self.extras) and len(self.packages) > 1:
            raise ValueError(
                "You can only specify one package when using the --extras option"
            )

        if self.optional and self.group != MAIN_GROUP:
            raise ValueError("You can only add optional dependencies to the main group")


class AddCommand(InstallerCommand, InitCommand):
    name = "add"
    description = "Adds a new dependency to <comment>pyproject.toml</> and installs it."

    arguments: ClassVar[list[Argument]] = [
        argument("name", "The packages to add.", multiple=True)
    ]
    options: ClassVar[list[Option]] = [
        option(
            "group",
            "-G",
            "The group to add the dependency to.",
            flag=False,
            default=MAIN_GROUP,
        ),
        option(
            "dev",
            "D",
            "Add as a development dependency. (shortcut for '-G dev')",
        ),
        option("editable", "e", "Add vcs/path dependencies as editable."),
        option(
            "extras",
            "E",
            "Extras to activate for the dependency.",
            flag=False,
            multiple=True,
        ),
        option(
            "optional",
            None,
            "Add as an optional dependency to an extra.",
            flag=False,
        ),
        option(
            "python",
            None,
            "Python version for which the dependency must be installed.",
            flag=False,
        ),
        option(
            "platform",
            None,
            "Platforms for which the dependency must be installed.",
            flag=False,
        ),
        option(
            "markers",
            None,
            "Environment markers which describe when the dependency should be installed.",
            flag=False,
        ),
        option(
            "source",
            None,
            "Name of the source to use to install the package.",
            flag=False,
        ),
        option("allow-prereleases", None, "Accept prereleases."),
        option(
            "dry-run",
            None,
            "Output the operations but do not execute anything (implicitly enables"
            " --verbose).",
        ),
        option("lock", None, "Do not perform operations (only update the lockfile)."),
    ]
    examples = """\
If you do not specify a version constraint, poetry will choose a suitable one based on\
 the available package versions.

You can specify a package in the following forms:
  - A single name (<b>requests</b>)
  - A name and a constraint (<b>requests@^2.23.0</b>)
  - A git url (<b>git+https://github.com/python-poetry/poetry.git</b>)
  - A git url with a revision\
 (<b>git+https://github.com/python-poetry/poetry.git#develop</b>)
  - A subdirectory of a git repository\
 (<b>git+https://github.com/python-poetry/poetry.git#subdirectory=tests/fixtures/sample_project</b>)
  - A git SSH url (<b>git+ssh://github.com/python-poetry/poetry.git</b>)
  - A git SSH url with a revision\
 (<b>git+ssh://github.com/python-poetry/poetry.git#develop</b>)
  - A file path (<b>../my-package/my-package.whl</b>)
  - A directory (<b>../my-package/</b>)
  - A url (<b>https://example.com/packages/my-package-0.1.0.tar.gz</b>)
"""
    help = f"""\
The add command adds required packages to your <comment>pyproject.toml</> and installs\
 them.

{examples}
"""

    loggers: ClassVar[list[str]] = [
        "poetry.repositories.pypi_repository",
        "poetry.inspection.info",
    ]

    def handle(self) -> int:
        if self.option("dev"):
            group = "dev"
        else:
            group = self.option("group", self.default_group or MAIN_GROUP)

        add_options = AddOptions(
            packages=self.argument("name"),
            group=group,
            extras=self.option("extras"),
            editable=self.option("editable"),
            optional=self.option("optional"),
            python=self.option("python"),
            platform=self.option("platform"),
            source=self.option("source"),
            markers=self.option("markers"),
            allow_prereleases=self.option("allow-prereleases"),
        )

        return AddCommandHandler(
            poetry=self.poetry,
            env=self.env if isinstance(self, EnvCommand) else None,  # type: ignore[redundant-expr]
            pool=self._get_pool(),
            io=self.io,
            installer=self.installer,
        ).add(
            add_options,
            lock=self.option("lock"),
            dry_run=self.option("dry-run"),
        )
