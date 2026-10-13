#!/usr/bin/env python3
"""Create the project's runtime environment file.

This script is intended to live at ``.infra/env/programs/write_envfile.py``.
All paths are resolved from the project root, which is derived from this file's
location rather than from the process working directory.
"""

from __future__ import annotations

import configparser
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


CURRENT_CONTEXT_DIRECTORY = Path(".infra/env/nvctx/current")
KEYMAP_FILE = Path(".infra/env/keymap/keymap.json")
KEYMAP_SCRIPT = Path(".infra/env/keymap/scripts/setenv_transpiled.py")
CONFIG_FILE = Path(".infra/tesconfig")

MULTIPLE_CONTEXT_ERROR = (
    "ERROR: you can only have 1 environment context file chosen as your current. "
    "That means 1 file in the '.infra\\env\\nvctx\\current\\' folder. "
    "The others should be kept in '.infra\\env\\nvctx\\saves'."
)


def project_root() -> Path:
    """Return the root for a script located in .infra/env/programs/."""
    script = Path(__file__).resolve()
    # programs -> env -> .infra -> project root
    return script.parents[3]


def parse_key_list(raw_value: str) -> list[str]:
    """Parse an INI value such as [A, B, C] into a list of key names."""
    value = raw_value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    if not value.strip():
        return []
    return [item.strip().strip("'\"") for item in value.split(",") if item.strip()]


def read_config(root: Path) -> tuple[Path, list[str]]:
    config_path = root / CONFIG_FILE
    config = configparser.ConfigParser()
    if not config.read(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    envfile_location = config.get("env", "envfile-location")
    keys = parse_key_list(config.get("keymap", "envfile-keys-list"))
    destination = Path(envfile_location)
    if not destination.is_absolute():
        destination = root / destination
    return destination, keys


def context_state_lines(root: Path) -> list[str]:
    """Read the selected context's state object as ``key = value`` lines."""
    directory = root / CURRENT_CONTEXT_DIRECTORY
    context_files = [path for path in directory.iterdir() if path.is_file()] if directory.exists() else []

    if len(context_files) > 1:
        print(MULTIPLE_CONTEXT_ERROR, file=sys.stderr)
        raise RuntimeError("More than one current environment context file")
    if not context_files:
        return []

    with context_files[0].open("r", encoding="utf-8") as handle:
        context = json.load(handle)

    state = context.get("state")
    if not isinstance(state, dict):
        raise ValueError(f"Context file {context_files[0]} must contain an object named 'state'.")
    return [f"{key} = {value}" for key, value in state.items()]


def read_keymap(root: Path) -> dict[str, dict[str, Any]]:
    with (root / KEYMAP_FILE).open("r", encoding="utf-8") as handle:
        keymap = json.load(handle)
    keys = keymap.get("keys")
    if not isinstance(keys, list):
        raise ValueError("The keymap JSON must contain a 'keys' array.")
    return {item["name"]: item for item in keys if isinstance(item, dict) and "name" in item}


def load_function_module(root: Path):
    module_path = root / KEYMAP_SCRIPT
    spec = importlib.util.spec_from_file_location("setenv_transpiled", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load keymap functions from: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call_keymap_function(module: Any, mapping: dict[str, Any]) -> Any:
    function_name = mapping.get("function")
    if not isinstance(function_name, str):
        raise ValueError(f"Keymap entry {mapping.get('name')!r} has no function name.")
    function = getattr(module, function_name, None)
    if not callable(function):
        raise AttributeError(f"Function {function_name!r} was not found in {KEYMAP_SCRIPT}.")
    return function(mapping["input"]) if "input" in mapping and mapping["input"] is not None else function()


def create_envfile() -> None:
    root = project_root()
    envfile, requested_keys = read_config(root)
    state_lines = context_state_lines(root)
    keymap = read_keymap(root)
    functions = load_function_module(root)

    output = [f"PROJECT_ROOT_LOC = {root}"]
    for key in requested_keys:
        # Context state takes precedence. The requested matching rule is a
        # prefix match against the stored ``key = value`` strings.
        matching_index = next(
            (index for index, line in enumerate(state_lines) if line.startswith(key)),
            None,
        )
        if matching_index is not None:
            output.append(state_lines.pop(matching_index))
        elif key in keymap:
            output.append(f"{key} = {call_keymap_function(functions, keymap[key])}")
        else:
            output.append(f"{key} = none")

    output.extend(state_lines)
    envfile.parent.mkdir(parents=True, exist_ok=True)
    envfile.write_text("\n".join(output) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        create_envfile()
    except Exception as error:
        # The required multi-context message is already printed above; this makes
        # all other configuration or JSON failures actionable as well.
        if not (isinstance(error, RuntimeError) and str(error).startswith("More than one")):
            print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
