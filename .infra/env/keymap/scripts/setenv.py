"""Discover the configured Python environments and TechES tools location."""

from __future__ import annotations

import configparser
import getpass
import os
from pathlib import Path
import platform
import subprocess
import sys


def _project_root() -> Path:
    """Find the project root from this generated keymap module's location."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / ".infra" / "env" / "config" / "tesconfig").is_file():
            return candidate
    raise FileNotFoundError("Could not locate the project tesconfig file.")


def _read_config() -> configparser.ConfigParser:
    """Load the project environment configuration."""
    config_path = _project_root() / ".infra" / "env" / "config" / "tesconfig"
    config = configparser.ConfigParser(interpolation=None)
    if not config.read(config_path, encoding="utf-8"):
        raise FileNotFoundError(f"Could not read environment config: {config_path}")
    return config


def _configured_path(value: str, root: Path) -> Path:
    """Resolve a configured path against the project root when it is relative."""
    path = Path(os.path.expandvars(value)).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def _pyvenv_values(venv_location: Path) -> dict[str, str]:
    """Read simple key/value entries from a venv's pyvenv.cfg."""
    config_path = venv_location / "pyvenv.cfg"
    if not config_path.is_file():
        raise FileNotFoundError(
            f"Virtual environment configuration was not found: {config_path}"
        )
    values: dict[str, str] = {}
    for line in config_path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip().lower()] = value.strip()
    return values


def _venv_location() -> Path:
    """Find the configured, activated, or project-local virtual environment."""
    root = _project_root()
    config = _read_config()
    configured = config.get("python", "venv-location", fallback="auto").strip()
    if configured.lower() != "auto":
        location = _configured_path(configured, root)
        _pyvenv_values(location)
        return location

    activated = os.environ.get("VIRTUAL_ENV")
    if activated:
        location = Path(activated).expanduser().resolve()
        _pyvenv_values(location)
        return location

    if sys.prefix != sys.base_prefix:
        location = Path(sys.prefix).resolve()
        _pyvenv_values(location)
        return location

    location = (root / ".venv").resolve()
    _pyvenv_values(location)
    return location


def _venv_interpreter() -> Path:
    """Return the virtual environment's Python executable."""
    venv_location = _venv_location()
    if os.name == "nt":
        interpreter = venv_location / "Scripts" / "python.exe"
    else:
        interpreter = venv_location / "bin" / "python"
    if not interpreter.is_file():
        raise FileNotFoundError(
            f"Python interpreter was not found in the virtual environment: "
            f"{interpreter}"
        )
    return interpreter


def _user_interpreter() -> Path:
    """Return the base Python executable used to create the venv."""
    root = _project_root()
    configured = _read_config().get(
        "python", "user-interpreter", fallback="auto"
    ).strip()
    if configured.lower() != "auto":
        interpreter = _configured_path(configured, root)
    else:
        venv_config = _pyvenv_values(_venv_location())
        executable = venv_config.get("executable")
        if executable:
            interpreter = Path(os.path.expandvars(executable)).expanduser()
            if not interpreter.is_absolute():
                home = venv_config.get("home")
                if not home:
                    raise ValueError(
                        "Relative Python executable in pyvenv.cfg requires a "
                        "'home' entry."
                    )
                interpreter = Path(home).expanduser() / interpreter
            interpreter = interpreter.resolve()
        else:
            home = venv_config.get("home")
            if not home:
                raise ValueError(
                    "The venv pyvenv.cfg has neither 'executable' nor 'home'."
                )
            interpreter_name = "python.exe" if os.name == "nt" else "python"
            interpreter = (
                Path(os.path.expandvars(home)).expanduser() / interpreter_name
            ).resolve()

    if not interpreter.is_file():
        raise FileNotFoundError(f"User-level Python interpreter not found: {interpreter}")
    return interpreter


def _python_version(interpreter: Path) -> str:
    """Return the version reported by a Python interpreter."""
    result = subprocess.run(
        [str(interpreter), "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    output = (result.stdout or result.stderr).strip()
    if not output.startswith("Python "):
        raise RuntimeError(
            f"Unexpected version response from {interpreter}: {output!r}"
        )
    return output.removeprefix("Python ").strip()


def get_python_user_install() -> str:
    """Return the base Python installation directory."""
    return str(_user_interpreter().parent)


def get_python_venv_install() -> str:
    """Return the virtual environment's Python executable."""
    return str(_venv_interpreter())


def get_python_user_version() -> str:
    """Return the version of the base Python installation."""
    return _python_version(_user_interpreter())


def get_python_venv_version() -> str:
    """Return the version of the virtual environment's Python."""
    return _python_version(_venv_interpreter())


def get_user_venv_base_location() -> str:
    """Return the virtual environment directory."""
    return str(_venv_location())


def get_user_venv_scripts_location() -> str:
    """Return the Windows Scripts directory within the virtual environment."""
    return str(_venv_location() / "Scripts")


def get_user_venv_bin_location() -> str:
    """Return the bin directory within the virtual environment."""
    return str(_venv_location() / "bin")


def get_command_tools_location() -> str:
    """Return the configured directory containing TechES command packages."""
    root = _project_root()
    configured = _read_config().get("tools", "command-tools-location")
    return str(_configured_path(configured, root))


def _project_path(relative_path: str) -> str:
    """Return an existing path under the project root, or the envfile null token."""
    path = _project_root() / relative_path
    return str(path.resolve()) if path.exists() else "null"


def get_device_name() -> str:
    """Return the current computer's network host name."""
    return platform.node() or "null"


def get_os() -> str:
    """Return a readable operating-system name and version."""
    if sys.platform == "win32":
        version = sys.getwindowsversion()
        release = "11" if version.build >= 22000 else "10"
        return f"Windows {release}"
    return f"{platform.system()} {platform.release()}"


def get_user() -> str:
    """Return the current operating-system user's login name."""
    return getpass.getuser() or "null"


def get_parent_project_loc() -> str:
    """Return the project root discovered from the environment configuration."""
    return str(_project_root())


def get_installed_children() -> str:
    """Return null until TechES child-project discovery is defined."""
    return "null"


def get_child_locs() -> str:
    """Return null until TechES child-project discovery is defined."""
    return "null"


def get_mct_scripts_loc() -> str:
    """Return the MCT scripts directory when it exists."""
    return _project_path("MCT/scripts")


def get_mct_rp_files_loc() -> str:
    """Return null until the MCT RP-files directory convention is defined."""
    return "null"


def get_mct_bp_files_loc() -> str:
    """Return null until the MCT BP-files directory convention is defined."""
    return "null"


def get_parent_package_json_loc() -> str:
    """Return the root package.json path if this is a Node.js project."""
    return _project_path("package.json")


def get_parent_package_lock_json_loc() -> str:
    """Return the root package-lock.json path if present."""
    return _project_path("package-lock.json")


def get_parent_node_modules_loc() -> str:
    """Return the root node_modules path if present."""
    return _project_path("node_modules")


def get_parent_prettier_rc_loc() -> str:
    """Return the root Prettier config if one of the common filenames exists."""
    for name in (".prettierrc", ".prettierrc.json", ".prettierrc.js", "prettier.config.js"):
        value = _project_path(name)
        if value != "null":
            return value
    return "null"


def get_rc_file_present_in_env() -> str:
    """Return null until RC_FILE_PRESENT_IN_ENV has a defined meaning."""
    return "null"


def get_last_loaded_nvctx() -> str:
    """Return null when no concrete NVCTX last-loaded value is defined."""
    return "null"
