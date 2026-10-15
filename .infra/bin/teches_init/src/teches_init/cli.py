"""Command-line interface for the TechES bootstrap installer."""

from __future__ import annotations

import configparser
import subprocess
from importlib.metadata import entry_points
from pathlib import Path

import click

from teches_init.installer import (
    InstallOptions,
    VALID_MODULES,
    find_project_root,
    install_infrastructure,
)
from teches_init.profiles import save_default_profile


class SynopsisCommand(click.Command):
    """Reject command help combined with other options, as the synopsis states."""

    @staticmethod
    def _expand_module_lists(args: list[str]) -> list[str]:
        """Normalize space-separated module values into repeated Click options."""
        expanded: list[str] = []
        index = 0
        list_options = {"-i", "--include", "-x", "--exclude"}
        while index < len(args):
            argument = args[index]
            inline_option = next(
                (
                    option
                    for option in ("--include=", "--exclude=")
                    if argument.startswith(option)
                ),
                None,
            )
            option = argument.split("=", maxsplit=1)[0] if inline_option else argument
            if option not in list_options and inline_option is None:
                expanded.append(argument)
                index += 1
                continue

            values = []
            if inline_option:
                values.append(argument.split("=", maxsplit=1)[1])
            index += 1
            while index < len(args) and not args[index].startswith("-"):
                values.append(args[index])
                index += 1
            if not values:
                expanded.append(option)
                continue
            for value in values:
                expanded.extend((option, value))
        return expanded

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        """Expand module lists and enforce the command's standalone help syntax."""
        args = self._expand_module_lists(args)
        if any(argument in {"--help", "-h"} for argument in args) and len(args) != 1:
            raise click.UsageError("--help/-h cannot be combined with other options.")
        return super().parse_args(ctx, args)


@click.group()
def cli() -> None:
    """Initialize TechES infrastructure and expose installed TechES commands."""


@cli.command(
    "init",
    cls=SynopsisCommand,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "-f",
    "--force",
    is_flag=False,
    flag_value=True,
    type=click.BOOL,
    default=False,
    help="Force operations that would otherwise stop on existing files or installs.",
)
@click.option(
    "-I",
    "--install-loc",
    type=click.Path(path_type=Path, file_okay=False),
    help="Destination directory for the complete .infra tree.",
)
@click.option(
    "-k",
    "--keymap-loc",
    type=click.Path(path_type=Path, file_okay=False),
    help="Parent directory for the installed keymap/ folder.",
)
@click.option(
    "-n",
    "--nvctx-loc",
    type=click.Path(path_type=Path, file_okay=False),
    help="Parent directory for the installed nvctx/ folder.",
)
@click.option(
    "-p",
    "--project-restore-loc",
    type=click.Path(path_type=Path, file_okay=False),
    help="Parent directory for the installed restore-sys/ folder.",
)
@click.option(
    "-i",
    "--include",
    "include_modules",
    type=click.Choice(VALID_MODULES, case_sensitive=False),
    multiple=True,
    help="Install one or more named modules. Repeat the option if preferred.",
)
@click.option(
    "-x",
    "--exclude",
    "exclude_modules",
    type=click.Choice(VALID_MODULES, case_sensitive=False),
    multiple=True,
    help="Skip one or more named modules. Repeat the option if preferred.",
)
@click.option(
    "-m",
    "--module",
    type=click.Choice(VALID_MODULES, case_sensitive=False),
    help="Module whose package location is being overridden.",
)
@click.option(
    "-l",
    "--location",
    type=click.Path(path_type=Path, file_okay=False),
    help="Package directory, or its parent directory, for --module.",
)
@click.option("--username", "-U", help="Username stored in the default user profile.")
@click.option("--email", "-E", help="Email stored in the default user profile.")
def init_command(
    force: bool,
    install_loc: Path | None,
    keymap_loc: Path | None,
    nvctx_loc: Path | None,
    project_restore_loc: Path | None,
    include_modules: tuple[str, ...],
    exclude_modules: tuple[str, ...],
    module: str | None,
    location: Path | None,
    username: str | None,
    email: str | None,
) -> None:
    """Save your profile, then install selected TechES tools and systems."""
    if (module is None) != (location is None):
        raise click.UsageError("--module and --location must be used together.")

    if username is None:
        username = click.prompt("Username").strip()
    if email is None:
        email = click.prompt("Email").strip()
    update_git_config = click.confirm(
        "Do you want to update git config with this info?", default=False
    )

    try:
        project_root = find_project_root(Path.cwd())
        profile_path = save_default_profile(project_root, username, email)
    except (configparser.Error, OSError, ValueError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"Saved default user profile: {profile_path}")

    if update_git_config:
        try:
            for key, value in (("user.name", username), ("user.email", email)):
                subprocess.run(
                    ["git", "config", "--local", "--replace-all", key, value],
                    cwd=project_root,
                    check=True,
                    capture_output=True,
                    text=True,
                )
        except (OSError, subprocess.CalledProcessError) as error:
            detail = (
                (error.stderr or "").strip()
                if isinstance(error, subprocess.CalledProcessError)
                else str(error)
            )
            raise click.ClickException(
                f"Could not update local Git config: {detail or error}"
            ) from error

    options = InstallOptions(
        force=force,
        install_location=install_loc,
        keymap_location=keymap_loc,
        nvctx_location=nvctx_loc,
        project_restore_location=project_restore_loc,
        include=tuple(value.lower() for value in include_modules),
        exclude=tuple(value.lower() for value in exclude_modules),
        module=module.lower() if module else None,
        module_location=location,
    )
    try:
        installed = install_infrastructure(project_root, options)
    except (OSError, ValueError, RuntimeError) as error:
        raise click.ClickException(str(error)) from error

    if installed:
        click.echo("Installed TechES packages:")
        for package_directory in installed:
            click.echo(f"  {package_directory}")
    else:
        click.echo("No TechES command packages were selected.")


def _register_installed_commands() -> None:
    """Load unique Click subcommands advertised by installed TechES plugins."""
    for entry_point in entry_points(group="teches.commands"):
        if entry_point.name in cli.commands:
            raise RuntimeError(
                f"Multiple TechES commands are registered as {entry_point.name!r}."
            )
        command = entry_point.load()
        if not isinstance(command, click.Command):
            raise TypeError(
                f"TechES command entry point {entry_point.name!r} "
                "did not load a Click command."
            )
        cli.add_command(command, entry_point.name)


_register_installed_commands()
