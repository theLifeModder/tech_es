# TechES Keymap System

## Scope

The keymap system associates named environment values with functions. The
environment writer uses that mapping when generating the project's `.tesenv`
file. Its main components are:

- `keymap.json`, which maps names to function names and contains planned
  translator metadata;
- `setenv.js` and `setenv.py`, intended as source files for defining or
  generating environment-value functions;
- user-provided scripts that implement functions in other languages;
- the generated Python function module used by the current writer; and
- `envWriter.py`, which reads the requested keys, evaluates mappings, and
  writes the environment file.

NVCTX (environment contexts) is a separate system. The writer can read
context state supplied by NVCTX and gives that state precedence over keymap
values for requested names. NVCTX's storage and commands are documented
separately; this document only covers that integration point.

## Repository locations

The current checkout places keymap-related files here:

| Path                                               | Purpose                                                                                                                                                                                                                      |
| -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.infra/env/keymap/keymap.json`                  | Key definitions and translator metadata.                                                                                                                                                                                     |
| `.infra/env/keymap/scripts/setenv.js`            | JavaScript source placeholder for keymap functions or generation logic. If a user wishes to add a javascript keymap function to set a value in the generated .tesenv file, they will add it here.                           |
| `.infra/env/keymap/scripts/setenv.py`            | Python source for keymap functions or generation logic. If a user wishes to add a python keymap function to set a value in the generated .tesenv file, they will add it here.                                               |
| `.infra/env/keymap/scripts/setenv_transpiled.py` | Generated Python module imported by the current environment writer. It contains `setenv.py` and the Python output from each configured language transpiler. |
| `.infra/env/bin/envWriter.py`                    | Reads configuration/context/keymap values and writes `.tesenv`.                                                                                                                                                            |
| `.infra/env/config/tesconfig`                    | Intended configuration for output location and requested environment keys.                                                                                                                                                   |

The Python source defines the environment-discovery functions. The generated
Python file is rebuilt by `envWriter.py`; do not edit it directly.

## Keymap data format

The current `envWriter.py` implementation expects `keymap.json` to contain a
`keymap` object with a `keys` array. Each entry must have a `name` and a
`function`. An optional `input` value is passed as the function's argument:

```json
{
  "keymap": {
    "keys": [
      {
        "name": "PARENT_PROJECT_LOC",
        "function": "get_parent_project_loc"
      },
      {
        "name": "SOME_VALUE",
        "function": "format_value",
        "input": "some argument"
      }
    ]
  }
}
```

In this shape, the writer emits keys named in `envfile-keys-list` first, in
configured order, then appends any other keys from `keymap.keys` in list order.
Duplicate names are emitted only once. Each entry's `name` determines the
output variable and its `function` supplies the value.

The writer reads entries from `keymap.keys`; it does not currently accept a
top-level `keys` array as an alternative.

## Function scripts and language support

For each requested name without an NVCTX-provided value, the writer looks up
the matching keymap entry's `function` value in the imported
`setenv_transpiled.py` Python module. The value must identify a callable
function:

```python
def get_parent_project_loc():
    return "path/to/project"


def format_value(value):
    return value.strip()
```

An entry without a non-null `input` calls the function with no arguments. An
entry with `input` calls it with that single argument. The return value is
converted to text when the writer builds the `NAME = value` output line.

## Python environment keys

The configured Python keymap reports:

- `PYTHON_USER_INSTALL`: directory containing the base Python interpreter.
- `PYTHON_VENV_INSTALL`: the virtual environment's Python executable.
- `PYTHON_USER_VERSION` and `PYTHON_VENV_VERSION`: versions reported by those
  interpreters.
- `USER_VENV_BASE_LOCATION`: virtual environment root.
- `USER_VENV_SCRIPTS_LOCATION` and `USER_VENV_BIN_LOCATION`: the conventional
  `Scripts` and `bin` paths under that root. On Windows, `Scripts` is used for
  the venv executable; `bin` is still reported as a path even if it does not
  exist on that platform.
- `COMMAND_TOOLS_LOCATION`: resolved path configured by
  `[tools] command-tools-location` in `tesconfig`.

`[python] venv-location` accepts `auto` or an absolute/project-relative venv
directory. In auto mode the functions use, in order, an activated
`VIRTUAL_ENV`, the interpreter running the writer if it is itself a venv, or
the project's `.venv`. The selected directory must contain `pyvenv.cfg` and
its platform's Python executable. `[python] user-interpreter` accepts `auto`
or an explicit interpreter path. Auto mode reads the base interpreter path
from the selected venv's `pyvenv.cfg`, so a moved venv can still be located by
setting `venv-location` without losing the base-Python association.

The default command tools path is `.infra/bin`, relative to the project root.
Set `command-tools-location` to another absolute or project-relative path if
the TechES command packages are stored elsewhere.

The existing machine, project, Node.js, MCT, and NVCTX keys are also mapped.
Machine/OS/user/project-root values are detected, and common root Node.js paths
are emitted only when those files or directories exist. Keys whose conventions
are not yet defined (`INSTALLED_CHILDREN`, `CHILD_LOCS`, the MCT file
locations, `RC_FILE_PRESENT_IN_ENV`, and `LAST_LOADED_NVCTX`) emit the literal
`null`. The stray `PARENT_` line in the original `.tesenv` template is not a
valid variable assignment and is not included.

The writer copies `setenv.py` and invokes each configured transpiler to turn
its source into Python. Configuration sections follow the pattern
`[keymap.<language>-transpiler]`, with `source` and `transpiler` options.
`transpiler` is a `module.path:callable` reference. The callable accepts source
text and must return Python source text. An optional `module-path` adds a
vendored transpiler's import root to Python's module search path. For example,
the checked-in JavaScript config points `jsconvert.transpiler:format_code` at
`.infra/env/bin/transpilers/JSConvert/src`.

To add a language, add a matching section with its source path, callable
reference, and optional import root; the writer runs all configured
transpilers and combines their Python output with `setenv.py`. To switch the
JavaScript transpiler, change only the `transpiler` value if the replacement
module is already importable (otherwise set its `module-path` as well). Every
transpiler must use the same callable contract, regardless of its source
language. The combined Python source is syntax-compiled before it replaces the
generated module.

For example, an additional language can be wired in without changing the
writer:

```ini
[keymap.java-transpiler]
source = .infra/env/keymap/scripts/setenv.java
transpiler = my_java_converter:convert
module-path = .infra/env/bin/transpilers/my-java-converter
```

The adapter's `convert(source_text)` callable must return Python source text.
For command-line transpilers, provide a small Python adapter implementing this
contract; the writer does not guess command-line arguments or output formats.

The native Python source is placed before configured transpiler output, so a
transpiled definition takes effect if it shares a name with a Python
definition. Output order follows config section order. Avoid duplicate names
unless overriding an earlier definition is intentional.

### User-added scripts in other languages

`keymap.json` has translator metadata describing language commands/scripts,
and a `translators_dir` field. The checked-in JSON lists JavaScript, Java, and
C++ examples. This appears intended to let users provide implementations in
other languages and connect them to the keymap system through translators.

The current writer does not use the translator metadata in `keymap.json` or
execute the language commands described there. Other languages can be enabled
through their own `keymap.<language>-transpiler` config sections, provided
their configured callable converts source text to Python source text.

## Environment writer integration

The writer is part of the keymap system's runtime use: it emits every
configured key and every keymap key, then invokes mapped functions when context
state does not provide an override.

The current flow in `envWriter.py` is:

1. Determine the project root relative to the writer's own file location.
2. Read `tesconfig` for the output keys, keymap execution-mode, and transpiler
   settings.
3. Read a context `state` object if a file exists in the writer's configured
   current-context directory. More than one file is an error.
4. Load `keymap.json`, combine `setenv.py` with outputs from each configured
   language transpiler, then import the generated `setenv_transpiled.py`.
5. Begin output with `PROJECT_ROOT_LOC = <project root>`.
6. For configured names followed by any remaining names from `keymap.keys`:
   - use a matching context-state line if found;
   - otherwise call its mapped function if a keymap entry exists;
   - otherwise write `NAME = none`.
7. Append state lines not consumed by keymap entries.
8. Write `.infra/env/config/.tesenv` under the project root with a final
   newline.

Context state takes precedence over mapped values. The current code identifies
a context entry using `line.startswith(key)`, so state lines should use the
expected `NAME = value` format; this is a prefix check rather than an exact
parsed-key comparison.

## Configuration used by the writer

The project configuration is INI-style and parsed with Python's
`configparser`. It configures environment discovery and keymap execution. For
example:

```ini
[keymap]
keymap-base-location = .infra/env/keymap/
execution-mode = transpiler

[python]
venv-location = auto
user-interpreter = auto

[tools]
command-tools-location = .infra/bin
```

`envfile-keys-list` selects the initial values and their order;
`keymap.json` maps those names to functions and is also the safety net: every
key declared there is emitted even if it is omitted from the config list.
Configured names without keymap entries are emitted as `none`. The writer
always places `.tesenv` at `.infra/env/config/.tesenv` under the project root.
The config does not select the output path or contain executable code.

## Commands and installation

### Environment writer command

The implemented command that consumes the keymap is the Python environment
writer. From the project root, its intended invocation is:

```powershell
python .infra\env\bin\envWriter.py
```

It takes no command-line arguments. It derives the project root from its own
file location, reads its environment/keymap configuration, looks for context
state, evaluates the configured keymap functions, and writes the fixed project
`.tesenv` output.
Because it currently derives paths from the repository layout and fixed
constants, changing the working directory is not intended to change which
project it processes.

Before invoking it, the config path, keymap JSON shape, and generated Python
functions must match the assumptions documented above. See
[Current implementation limitations](#current-implementation-limitations).

### Infrastructure management command

The mounted `teches-infra-documentation.txt` gives this proposed syntax:

```text
teches infra [&(--location|-l) <system:path>]
             [&(--keymap-add-lang <language>)]
```

The longer `teches-init1-documentation.txt` spells out the location systems
as `nvctx`, `env`, `restore`, `keymap-sys`, and `keymap-map`. In that
notation, `&(...)` means the enclosed option is optional. The documented
location option is intended to select a system and a path, for example:

```text
teches infra --location keymap-map:.infra/env/keymap/keymap.json
teches infra --location keymap-sys:.infra/env/keymap
teches infra --keymap-add-lang javascript
```

These examples illustrate the notation and intended areas of configuration;
they are **not currently executable usage examples**. The documentation has
no detailed semantics for the location values or the language option. The
`teches-infra-documentation.txt` description explicitly says that this
command currently returns the string `"true"`, and the option descriptions
are blank. No working `teches infra` implementation is present in this
checkout.

### Project initialization and keymap location

The mounted initialization notes describe `teches init` as the installer for
project infrastructure, including the keymap and NVCTX systems. They specify
the keymap location option as:

```text
teches init [--keymap-loc|-k <parent-path>]
```

The intended default is `{project}/.infra/env/keymap/`. If a custom parent
path is supplied, the keymap folder is intended to be installed at
`<parent-path>/keymap/`. The notes say this option can be combined with the
other initialization options. The same notes characterize `teches init` as
unfinished and say it currently returns `"true"`; treat this as planned
installer behavior, not a supported command in this checkout.

### `teches keymap` command status

The mounted initialization document contains a `teches keymap` heading, but
its synopsis, description, options, and usage are blank. It does not provide
enough information to specify or document a functioning standalone keymap
management command. In particular, don't assume that the `teches infra`
location/language options are implemented by a `teches keymap` command.

The command documents consulted for these planned interfaces are stored in
the user's mounted Tech-ES Google Drive under
`Tech-ES/Environment/Commands/Documentation/`.

## Errors and troubleshooting

The writer reports errors to standard error and exits with a non-zero status
for problems including:

- a missing config file, keymap JSON file, or generated Python module;
- invalid JSON or a missing `keymap.keys` array;
- more than one context file in its configured current-context directory;
- a context JSON file without a dictionary-valued `state`;
- a keymap entry with no string function name; or
- a function name that is missing or not callable in `setenv_transpiled.py`.

When run as a VS Code task, inspect the task terminal for the diagnostic.

## Current implementation limitations

The current checkout has a few remaining path/documentation mismatches:

- `envWriter.py` sets `CURRENT_CONTEXT_DIRECTORY` to
  `.infra/env/nvctx/current`, while the checked-in NVCTX context layout is
  under `.infra/env/nvctx/contexts/current`.
- The configured JavaScript source is empty; the Python keymap functions are
  supplied by `setenv.py`.
- `keymap-base-location`, `supported-langs`, and the translator declarations
  in `keymap.json` are not currently consumed by the writer.
- The writer's `project_root()` calculation (`script.parents[3]`) resolves to
  the repository root for its current `.infra/env/bin/` location. Its
  docstring still mentions the older `.infra/env/programs/` layout.

These limitations are recorded to distinguish the intended system design
from behavior implemented by the current files.
