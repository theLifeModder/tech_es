"""Discover and install TechES packages and project infrastructure."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit
from urllib.request import url2pathname


VALID_MODULES = (
    "install",
    "config",
    "infra",
    "repo",
    "fs",
    "version",
    "project",
    "env",
    "nvctx",
    "keymap",
)
PACKAGE_NAME_BY_MODULE = {"install": "teches_init"}
SYSTEM_SOURCE_BY_MODULE = {
    "config": Path("env/config"),
    "env": Path("env"),
    "infra": Path("."),
    "keymap": Path("env/keymap"),
    "nvctx": Path("env/nvctx"),
    "project": Path("env/restore-sys"),
}
SYSTEM_NAME_BY_MODULE = {
    "keymap": "keymap",
    "nvctx": "nvctx",
    "project": "restore-sys",
}
COMMIT_MESSAGE_GENERATOR_DIRECTORY = Path("env/bin/teches_commit_message_generator")
INITIALIZER_PACKAGE_DIRECTORY = Path("teches_init")


@dataclass(frozen=True)
class InstallOptions:
    """Capture package filters, force behavior, and installation destinations."""

    force: bool = False
    install_location: Path | None = None
    keymap_location: Path | None = None
    nvctx_location: Path | None = None
    project_restore_location: Path | None = None
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    module: str | None = None
    module_location: Path | None = None


def find_project_root(start: Path) -> Path:
    """Find the nearest directory containing the project's .infra/bin folder."""
    resolved_start = start.resolve()
    for candidate in (resolved_start, *resolved_start.parents):
        if (candidate / ".infra" / "bin").is_dir():
            return candidate
    raise FileNotFoundError(
        f"Could not find a project root with .infra/bin above {resolved_start}."
    )


def module_for_package(package_directory: Path) -> str:
    """Derive a TechES module name from a package directory's name."""
    package_name = package_directory.name.lower().replace("-", "_")
    if package_name == "teches_init":
        return "install"
    if package_name.startswith("teches_"):
        return package_name.removeprefix("teches_")
    return package_name


def _is_selected(module: str, options: InstallOptions) -> bool:
    """Apply include and exclude filters to a module name."""
    if (
        module == "install"
        and "install" not in options.include
        and options.module != "install"
    ):
        return False
    if options.include and module not in options.include:
        return False
    return module not in options.exclude


def _package_candidates(
    source_bin: Path, options: InstallOptions
) -> list[tuple[str, Path]]:
    """Find package directories eligible for installation, including overrides."""
    candidates: dict[str, Path] = {}
    if source_bin.is_dir():
        for package_directory in sorted(source_bin.iterdir()):
            if (
                package_directory.is_dir()
                and package_directory.name.lower().startswith("teches")
                and (package_directory / "pyproject.toml").is_file()
            ):
                candidates[module_for_package(package_directory)] = package_directory
        initializer_directory = source_bin / INITIALIZER_PACKAGE_DIRECTORY
        if (initializer_directory / "pyproject.toml").is_file():
            candidates["install"] = initializer_directory

    if (
        options.module is not None
        and options.module_location is not None
        and options.module not in SYSTEM_SOURCE_BY_MODULE
    ):
        module_name = PACKAGE_NAME_BY_MODULE.get(
            options.module, f"teches_{options.module}"
        )
        location = options.module_location.expanduser().resolve()
        package_directory = (
            location
            if (location / "pyproject.toml").is_file()
            else location / module_name
        )
        if (
            options.module == "install"
            and not (package_directory / "pyproject.toml").is_file()
        ):
            package_directory = location / INITIALIZER_PACKAGE_DIRECTORY
        if not (package_directory / "pyproject.toml").is_file():
            raise FileNotFoundError(
                f"Package for module {options.module!r} was not found at "
                f"{package_directory}."
            )
        candidates[options.module] = package_directory

    selected = [
        (module, directory)
        for module, directory in candidates.items()
        if _is_selected(module, options)
    ]
    if options.include:
        unavailable = set(options.include) - candidates.keys() - set(
            SYSTEM_SOURCE_BY_MODULE
        )
        if unavailable:
            raise FileNotFoundError(
                "No package or installable system was found for: "
                + ", ".join(sorted(unavailable))
            )
    return sorted(selected)


def _copy_directory(source: Path, destination: Path, force: bool) -> None:
    """Copy an infrastructure directory while guarding conflicts and nesting."""
    if not source.is_dir():
        raise FileNotFoundError(f"Infrastructure source directory not found: {source}")
    resolved_source = source.resolve()
    resolved_destination = destination.resolve()
    if resolved_source == resolved_destination:
        return
    if (
        resolved_source in resolved_destination.parents
        or resolved_destination in resolved_source.parents
    ):
        raise ValueError(
            "Source and destination directories cannot contain one another: "
            f"{resolved_source} -> {resolved_destination}"
        )
    if resolved_destination.exists() and not force:
        raise FileExistsError(
            f"Destination already exists: {resolved_destination}. "
            "Use --force to merge and replace files."
        )
    resolved_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=force)


def _install_editable(package_directory: Path, force: bool) -> None:
    """Install a package editable unless this environment already uses its source."""
    if not force and _is_installed_editable_package(package_directory):
        return

    command = [sys.executable, "-m", "pip", "install", "-e", str(package_directory)]
    if force:
        command.append("--force-reinstall")
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"Editable install failed for {package_directory} "
            f"(exit code {result.returncode})."
        )


def _is_installed_editable_package(package_directory: Path) -> bool:
    """Return whether the matching package is already editable from this directory."""
    try:
        package = distribution(package_directory.name)
    except PackageNotFoundError:
        return False

    direct_url = package.read_text("direct_url.json")
    if direct_url is None:
        return False
    try:
        install_info = json.loads(direct_url)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Invalid direct_url.json metadata for {package_directory.name!r}."
        ) from error

    if install_info.get("dir_info", {}).get("editable") is not True:
        return False
    url = install_info.get("url")
    if not isinstance(url, str) or urlsplit(url).scheme != "file":
        return False

    installed_directory = Path(url2pathname(urlsplit(url).path))
    return installed_directory.resolve() == package_directory.resolve()


def _target_system_directory(
    infra_root: Path, module: str, options: InstallOptions
) -> Path:
    """Choose the destination directory for a selected infrastructure system."""
    configured_location = {
        "keymap": options.keymap_location,
        "nvctx": options.nvctx_location,
        "project": options.project_restore_location,
    }.get(module)
    folder_name = SYSTEM_NAME_BY_MODULE.get(module)
    if configured_location is not None and folder_name is not None:
        return configured_location.expanduser().resolve() / folder_name
    return infra_root / SYSTEM_SOURCE_BY_MODULE[module]


def _system_source_directory(
    source_infra: Path, module: str, options: InstallOptions
) -> Path:
    """Resolve a system's source directory, honoring an explicit location override."""
    if options.module == module and options.module_location is not None:
        location = options.module_location.expanduser().resolve()
        expected_name = SYSTEM_SOURCE_BY_MODULE[module].name
        if location.name == expected_name:
            source_directory = location
        else:
            child = location / expected_name
            source_directory = child if child.is_dir() else location
        if not source_directory.is_dir():
            raise FileNotFoundError(
                f"Location for module {module!r} was not found: {source_directory}"
            )
        return source_directory
    return source_infra / SYSTEM_SOURCE_BY_MODULE[module]


def _install_commit_message_generator(
    project_root: Path,
    infra_root: Path,
    custom_infra_root: bool,
    copy_whole_infra: bool,
    force: bool,
    status_callback: Callable[[str], None] | None,
) -> None:
    """Install the commit-message generator and report progress through the CLI."""
    source_directory = project_root / ".infra" / COMMIT_MESSAGE_GENERATOR_DIRECTORY
    if not source_directory.is_dir():
        raise FileNotFoundError(
            f"Commit message generator package was not found: {source_directory}"
        )

    install_directory = source_directory
    if custom_infra_root:
        install_directory = infra_root / COMMIT_MESSAGE_GENERATOR_DIRECTORY
        if not copy_whole_infra:
            _copy_directory(source_directory, install_directory, force)

    if status_callback is not None:
        status_callback("Installing TechES commit message generator...")
    try:
        _install_editable(install_directory, force)
    except (OSError, RuntimeError) as error:
        raise RuntimeError(
            f"Failed to install TechES commit message generator: {error}"
        ) from error
    if status_callback is not None:
        status_callback("Successfully installed TechES commit message generator.")


def install_infrastructure(
    project_root: Path,
    options: InstallOptions,
    status_callback: Callable[[str], None] | None = None,
) -> list[Path]:
    """Install selected command packages and copy selected system directories."""
    source_infra = project_root / ".infra"
    infra_root = (
        options.install_location.expanduser().resolve()
        if options.install_location is not None
        else source_infra
    )

    custom_infra_root = infra_root != source_infra.resolve()
    copy_whole_infra = custom_infra_root and (
        (not options.include and not options.exclude)
        or "infra" in options.include
    )
    if copy_whole_infra:
        _copy_directory(source_infra, infra_root, options.force)

    source_bin = source_infra / "bin"
    installed_packages: list[Path] = []
    for module, package_directory in _package_candidates(source_bin, options):
        install_directory = package_directory
        if custom_infra_root and options.module != module:
            install_directory = (
                infra_root / "bin" / package_directory.relative_to(source_bin)
            )
            if not copy_whole_infra:
                _copy_directory(package_directory, install_directory, options.force)
        _install_editable(install_directory, options.force)
        installed_packages.append(install_directory)

    _install_commit_message_generator(
        project_root,
        infra_root,
        custom_infra_root,
        copy_whole_infra,
        options.force,
        status_callback,
    )

    for module in SYSTEM_SOURCE_BY_MODULE:
        if not _is_selected(module, options):
            continue
        source_directory = _system_source_directory(source_infra, module, options)
        destination = _target_system_directory(infra_root, module, options)
        has_location_override = (
            options.module == module and options.module_location is not None
        )
        system_destination = {
            "keymap": options.keymap_location,
            "nvctx": options.nvctx_location,
            "project": options.project_restore_location,
        }.get(module)
        has_install_destination = (
            options.install_location is not None or system_destination is not None
        )
        if has_location_override and not has_install_destination:
            continue
        if (
            copy_whole_infra
            and module != options.module
            and destination.resolve().is_relative_to(infra_root.resolve())
        ):
            continue
        if source_directory.is_dir() and source_directory.resolve() != destination.resolve():
            _copy_directory(
                source_directory,
                destination,
                options.force or (copy_whole_infra and has_location_override),
            )
        elif options.include and module in options.include and not source_directory.is_dir():
            raise FileNotFoundError(
                f"The requested {module} system is not available at {source_directory}."
            )

    return installed_packages
