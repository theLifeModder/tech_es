"""Read and write per-project user profile data."""

from __future__ import annotations

import configparser
from pathlib import Path


PROFILE_FILE = Path(".infra/env/config/user/userdata.ini")
PROFILE_NAME = "default"


def save_default_profile(project_root: Path, username: str, email: str) -> Path:
    """Create or update the default profile without discarding other profiles."""
    values = {"username": username.strip(), "email": email.strip()}
    for field_name, value in values.items():
        if not value:
            raise ValueError(f"The {field_name} must not be empty.")
        if "\n" in value or "\r" in value:
            raise ValueError(f"The {field_name} must not contain a newline.")

    profile_path = project_root / PROFILE_FILE
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    config = configparser.ConfigParser(
        default_section="__global_defaults__", interpolation=None
    )
    if profile_path.exists():
        with profile_path.open("r", encoding="utf-8") as profile_file:
            config.read_file(profile_file)
    if not config.has_section(PROFILE_NAME):
        config.add_section(PROFILE_NAME)
    for field_name, value in values.items():
        config.set(PROFILE_NAME, field_name, value)

    temporary_path = profile_path.with_suffix(profile_path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="\n") as profile_file:
        config.write(profile_file)
    temporary_path.replace(profile_path)
    return profile_path
