"""Manage TechES project user profiles."""

from __future__ import annotations

import subprocess
from pathlib import Path

import click

from teches_init.installer import find_project_root
from teches_init.profiles import (
    activate_profile,
    create_profile as create_user_profile,
    delete_profile as remove_user_profile,
    read_profile,
)


def _parse_create_values(values: tuple[str, ...]) -> dict[str, str]:
    """Parse profname:, uname:, and email: arguments for profile creation."""
    parsed: dict[str, str] = {}
    for value in values:
        key, separator, content = value.partition(":")
        if not separator or key not in {"profname", "uname", "email"} or not content:
            raise click.UsageError(
                "Create-profile values must use profname:<name>, uname:<username>, "
                "or email:<email>."
            )
        if key in parsed:
            raise click.UsageError(f"The {key}: value may only be provided once.")
        parsed[key] = content
    if "profname" not in parsed:
        raise click.UsageError("--create-profile requires profname:<profile-name>.")
    return parsed


def _parse_profile_name(values: tuple[str, ...], action: str) -> str:
    """Parse one plain or profname:-prefixed profile name."""
    if len(values) != 1:
        raise click.UsageError(f"{action} requires exactly one profile name.")
    value = values[0]
    if value.startswith("profname:"):
        value = value.removeprefix("profname:")
    if not value.strip():
        raise click.UsageError("The profile name must not be empty.")
    return value


def _update_git_identity(project_root: Path, profile_name: str | None) -> None:
    """Write a saved profile's name and email to this repository's local Git config."""
    username, email = read_profile(project_root, profile_name)
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


@click.command("user", context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-c",
    "--create-profile",
    is_flag=True,
    help="Create a profile using profname:, uname:, and email: values.",
)
@click.option(
    "-s",
    "--set-profile",
    is_flag=True,
    help="Set the active profile and optionally update local Git identity.",
)
@click.option(
    "-d",
    "--delete-profile",
    is_flag=True,
    help="Delete a saved profile.",
)
@click.option(
    "-g",
    "--update-gitinfo",
    is_flag=True,
    help="Update local Git identity from a profile, or the active profile.",
)
@click.argument("values", nargs=-1)
def user_command(
    create_profile: bool,
    set_profile: bool,
    delete_profile: bool,
    update_gitinfo: bool,
    values: tuple[str, ...],
) -> None:
    """Create, activate, delete, or apply TechES user profiles."""
    actions = [
        create_profile,
        set_profile,
        delete_profile,
        update_gitinfo,
    ]
    if sum(actions) != 1:
        raise click.UsageError("Choose exactly one user-profile action.")

    try:
        project_root = find_project_root(Path.cwd())
        if create_profile:
            profile_values = _parse_create_values(values)
            username = profile_values.get("uname")
            email = profile_values.get("email")
            if username is None:
                username = click.prompt("Username").strip()
            if email is None:
                email = click.prompt("Email").strip()
            profile_path = create_user_profile(
                project_root,
                profile_values["profname"],
                username,
                email,
            )
            click.echo(f"Created profile {profile_values['profname']!r}: {profile_path}")
            return

        if set_profile:
            profile_name = _parse_profile_name(values, "--set-profile")
            profile_path = activate_profile(project_root, profile_name)
            click.echo(f"Set active profile to {profile_name!r}: {profile_path}")
            if click.confirm(
                "Do you want to update local Git config with this profile?",
                default=False,
            ):
                _update_git_identity(project_root, None)
            return

        if delete_profile:
            profile_name = _parse_profile_name(values, "--delete-profile")
            if not click.confirm(
                f"Delete saved profile {profile_name!r}? This cannot be undone.",
                default=False,
            ):
                click.echo("Profile deletion cancelled.")
                return
            profile_path = remove_user_profile(project_root, profile_name)
            click.echo(f"Deleted profile {profile_name!r}: {profile_path}")
            return

        profile_name = (
            _parse_profile_name(values, "--update-gitinfo") if values else None
        )
        _update_git_identity(project_root, profile_name)
        label = profile_name or "active profile"
        click.echo(f"Updated local Git config from {label!r}.")
    except (OSError, ValueError) as error:
        raise click.ClickException(str(error)) from error
