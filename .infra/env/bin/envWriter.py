#!/usr/bin/env python3
"""Create the project's runtime environment file.

This script is intended to live at ``.infra/env/programs/write_envfile.py``.
All paths are resolved from the project root, which is derived from this file's
location rather than from the process working directory.
"""

from __future__ import annotations

import configparser
from dataclasses import dataclass
import importlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


CURRENT_CONTEXT_DIRECTORY = Path(".infra/env/nvctx/current")
KEYMAP_FILE = Path(".infra/env/keymap/keymap.json")
PYTHON_KEYMAP_SOURCE = Path(".infra/env/keymap/scripts/setenv.py")
KEYMAP_SCRIPT = Path(".infra/env/keymap/scripts/setenv_transpiled.py")
CONFIG_FILE = Path(".infra/env/config/tesconfig")

MULTIPLE_CONTEXT_ERROR = (
    "ERROR: you can only have 1 environment context file chosen as your current. "
    "That means 1 file in the '.infra\\env\\nvctx\\current\\' folder. "
    "The others should be kept in '.infra\\env\\nvctx\\saves'."
)


@dataclass(frozen=True)
class TranspilerConfig:
    """Describe one language's keymap source and transpiler callable."""

    language: str
    source: Path
    callable_path: str
    module_path: Path | None


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


def read_config(
    root: Path,
) -> tuple[Path, list[str], str, list[TranspilerConfig]]:
    """Load environment output, keymap, execution-mode, and transpiler settings."""
    config_path = root / CONFIG_FILE
    config = configparser.ConfigParser()
    if not config.read(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    envfile_location = config.get("env", "envfile-location")
    keys = parse_key_list(config.get("keymap", "envfile-keys-list"))
    execution_mode = config.get(
        "keymap", "execution-mode", fallback="transpiler"
    ).strip().lower()
    transpilers = []
    for section in config.sections():
        prefix = "keymap."
        suffix = "-transpiler"
        if not section.startswith(prefix) or not section.endswith(suffix):
            continue
        language = section[len(prefix) : -len(suffix)].strip().lower()
        if not language:
            raise ValueError(f"Invalid transpiler configuration section: {section!r}")
        source_value = config.get(section, "source", fallback="").strip()
        callable_path = config.get(section, "transpiler", fallback="").strip()
        module_path_value = config.get(section, "module-path", fallback="").strip()
        if not source_value or not callable_path:
            raise ValueError(
                f"Section [{section}] must define both 'source' and 'transpiler'."
            )
        source_path = Path(source_value)
        if not source_path.is_absolute():
            source_path = root / source_path
        module_path = Path(module_path_value) if module_path_value else None
        if module_path is not None and not module_path.is_absolute():
            module_path = root / module_path
        transpilers.append(
            TranspilerConfig(
                language=language,
                source=source_path,
                callable_path=callable_path,
                module_path=module_path,
            )
        )
    destination = Path(envfile_location)
    if not destination.is_absolute():
        destination = root / destination
    return destination, keys, execution_mode, transpilers


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
    """Load named key definitions from the project's keymap JSON file."""
    with (root / KEYMAP_FILE).open("r", encoding="utf-8") as handle:
        keymap_data = json.load(handle)
    keymap_section = (
        keymap_data.get("keymap") if isinstance(keymap_data, dict) else None
    )
    keys = keymap_section.get("keys") if isinstance(keymap_section, dict) else None
    if not isinstance(keys, list):
        raise ValueError("The keymap JSON must contain a 'keymap.keys' array.")
    return {item["name"]: item for item in keys if isinstance(item, dict) and "name" in item}


def invoke_transpiler(config: TranspilerConfig) -> str:
    """Import and call the configured transpiler on its source file."""
    if ":" not in config.callable_path:
        raise ValueError(
            "A configured transpiler must use 'module.path:callable' format, "
            f"got {config.callable_path!r}."
        )
    module_name, callable_name = config.callable_path.split(":", maxsplit=1)
    if not module_name or not callable_name:
        raise ValueError(
            "A configured transpiler must use 'module.path:callable' format, "
            f"got {config.callable_path!r}."
        )

    module_path = config.module_path.resolve() if config.module_path else None
    if module_path is not None and not module_path.is_dir():
        raise FileNotFoundError(
            f"Transpiler module path for {config.language} was not found: {module_path}"
        )
    added_to_path = module_path is not None and str(module_path) not in sys.path
    if added_to_path:
        sys.path.insert(0, str(module_path))
    try:
        transpiler: Any = importlib.import_module(module_name)
        for attribute in callable_name.split("."):
            transpiler = getattr(transpiler, attribute, None)
            if transpiler is None:
                raise AttributeError(
                    f"Transpiler callable {config.callable_path!r} was not found."
                )
        if not callable(transpiler):
            raise TypeError(
                f"Configured transpiler {config.callable_path!r} is not callable."
            )
        source = config.source.read_text(encoding="utf-8")
        result = transpiler(source)
        if not isinstance(result, str):
            raise TypeError(
                f"Transpiler {config.callable_path!r} for {config.language} "
                "must return Python source as a string."
            )
        return result
    finally:
        if added_to_path:
            sys.path.remove(str(module_path))


def transpile_keymap(root: Path, transpilers: list[TranspilerConfig]) -> None:
    """Combine Python and translated keymap functions into a validated script."""
    python_source_path = root / PYTHON_KEYMAP_SOURCE
    output_path = root / KEYMAP_SCRIPT
    if not python_source_path.is_file():
        raise FileNotFoundError(
            f"Python keymap source file was not found: {python_source_path}"
        )

    python_source = python_source_path.read_text(encoding="utf-8")
    translated_sources = []
    for transpiler_config in transpilers:
        if not transpiler_config.source.is_file():
            raise FileNotFoundError(
                f"{transpiler_config.language} keymap source file was not found: "
                f"{transpiler_config.source}"
            )
        translated_sources.append(invoke_transpiler(transpiler_config))
    combined_source = "\n\n".join(
        source
        for source in (python_source, *translated_sources)
        if source.strip()
    )
    generated_source = (
        "# Generated by envWriter.py from setenv.py and configured transpilers. "
        "Do not edit directly."
    )
    if combined_source:
        generated_source += "\n\n" + combined_source.rstrip("\n")
    compile(generated_source, str(output_path), "exec")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generated_source + "\n", encoding="utf-8")


def load_function_module(
    root: Path, execution_mode: str, transpilers: list[TranspilerConfig]
):
    """Generate and import the configured keymap functions as a Python module."""
    if execution_mode != "transpiler":
        raise ValueError(
            f"Unsupported keymap execution mode: {execution_mode!r}. "
            "The environment writer currently supports 'transpiler'."
        )
    transpile_keymap(root, transpilers)

    module_path = root / KEYMAP_SCRIPT
    spec = importlib.util.spec_from_file_location("setenv_transpiled", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load keymap functions from: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call_keymap_function(module: Any, mapping: dict[str, Any]) -> Any:
    """Call the function named by a keymap entry with its optional input value."""
    function_name = mapping.get("function")
    if not isinstance(function_name, str):
        raise ValueError(f"Keymap entry {mapping.get('name')!r} has no function name.")
    function = getattr(module, function_name, None)
    if not callable(function):
        raise AttributeError(f"Function {function_name!r} was not found in {KEYMAP_SCRIPT}.")
    return function(mapping["input"]) if "input" in mapping and mapping["input"] is not None else function()


def create_envfile() -> None:
    """Build the configured environment file from context and keymap values."""
    root = project_root()
    envfile, requested_keys, execution_mode, transpilers = read_config(root)
    state_lines = context_state_lines(root)
    keymap = read_keymap(root)
    functions = load_function_module(root, execution_mode, transpilers)

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
