"""Read and write per-project user profile data."""

from __future__ import annotations

import configparser
from pathlib import Path


PROFILE_FILE = Path(".infra/env/config/user/userdata.ini")
PROFILE_NAME = "default"
SAVED_PROFILE_PREFIX = "profile "


def save_default_profile(project_root: Path, username: str, email: str) -> Path:
    """Create or update the default profile without discarding other profiles."""
    values = _validate_profile_values(username, email, username_label="username")
    profile_path = project_root / PROFILE_FILE
    config = _read_profiles(profile_path)
    if not config.has_section(PROFILE_NAME):
        config.add_section(PROFILE_NAME)
    for field_name, value in (("username", values["uname"]), ("email", values["email"])):
        config.set(PROFILE_NAME, field_name, value)
    _write_profiles(profile_path, config)
    return profile_path


def create_profile(
    project_root: Path, name: str, username: str, email: str
) -> Path:
    """Create a named profile without replacing an existing profile."""
    profile_name = _validate_profile_name(name)
    values = _validate_profile_values(username, email)
    profile_path = project_root / PROFILE_FILE
    config = _read_profiles(profile_path)
    section = _profile_section(profile_name)
    if config.has_section(section):
        raise ValueError(f"Profile {profile_name!r} already exists.")
    config.add_section(section)
    config.set(section, "uname", values["uname"])
    config.set(section, "email", values["email"])
    _write_profiles(profile_path, config)
    return profile_path


def read_profile(
    project_root: Path, name: str | None = None
) -> tuple[str, str]:
    """Return a profile's username and email; no name selects the active profile."""
    profile_path = project_root / PROFILE_FILE
    config = _read_profiles(profile_path)
    section = PROFILE_NAME if name is None else _profile_section(name)
    if not config.has_section(section):
        label = PROFILE_NAME if name is None else name
        raise ValueError(f"Profile {label!r} was not found in {profile_path}.")
    username_key = "username" if section == PROFILE_NAME else "uname"
    username = config.get(section, username_key, fallback="").strip()
    email = config.get(section, "email", fallback="").strip()
    values = _validate_profile_values(username, email)
    return values["uname"], values["email"]


def activate_profile(project_root: Path, name: str) -> Path:
    """Copy a named profile's identity into the active default profile."""
    username, email = read_profile(project_root, name)
    return save_default_profile(project_root, username, email)


def delete_profile(project_root: Path, name: str) -> Path:
    """Delete a saved named profile without changing the active default profile."""
    profile_name = _validate_profile_name(name)
    profile_path = project_root / PROFILE_FILE
    config = _read_profiles(profile_path)
    section = _profile_section(profile_name)
    if not config.has_section(section):
        raise ValueError(f"Profile {profile_name!r} was not found in {profile_path}.")
    config.remove_section(section)
    _write_profiles(profile_path, config)
    return profile_path


def _read_profiles(profile_path: Path) -> configparser.ConfigParser:
    """Read the profile file while preserving unrelated sections."""
    config = configparser.ConfigParser(
        default_section="__global_defaults__", interpolation=None
    )
    if profile_path.exists():
        with profile_path.open("r", encoding="utf-8") as profile_file:
            config.read_file(profile_file)
    return config


def _write_profiles(
    profile_path: Path, config: configparser.ConfigParser
) -> None:
    """Atomically write all profile sections to disk."""
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = profile_path.with_suffix(profile_path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="\n") as profile_file:
        config.write(profile_file)
    temporary_path.replace(profile_path)


def _profile_section(name: str) -> str:
    """Build the section name for a saved profile."""
    return SAVED_PROFILE_PREFIX + _validate_profile_name(name)


def _validate_profile_name(name: str) -> str:
    """Validate names used in INI section headers."""
    profile_name = name.strip()
    if not profile_name:
        raise ValueError("The profile name must not be empty.")
    if any(character in profile_name for character in "[]\r\n"):
        raise ValueError("The profile name must not contain brackets or newlines.")
    return profile_name


def _validate_profile_values(
    username: str,
    email: str,
    username_label: str = "uname",
) -> dict[str, str]:
    """Validate profile fields and return normalized values."""
    values = {"uname": username.strip(), "email": email.strip()}
    for field_name, value in (
        (username_label, values["uname"]),
        ("email", values["email"]),
    ):
        if not value:
            raise ValueError(f"The {field_name} must not be empty.")
        if "\n" in value or "\r" in value:
            raise ValueError(f"The {field_name} must not contain a newline.")
    return values
