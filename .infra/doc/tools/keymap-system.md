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

The two source placeholders are empty in the current checkout. The generated
Python file currently contains only a header comment, so there are no usable
keymap functions supplied yet.

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

In this shape, the writer indexes entries by `name`. Names should correspond
to the identifiers listed in `envfile-keys-list` in `tesconfig`.

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

The writer is part of the keymap system's runtime use: it determines which
values to emit and invokes the mapped functions when context state does not
provide a requested value.

The current flow in `envWriter.py` is:

1. Determine the project root relative to the writer's own file location.
2. Read the configuration file for the destination `.tesenv` path and list
   of requested key names.
3. Read a context `state` object if a file exists in the writer's configured
   current-context directory. More than one file is an error.
4. Load `keymap.json`, combine `setenv.py` with outputs from each configured
   language transpiler, then import the generated `setenv_transpiled.py`.
5. Begin output with `PROJECT_ROOT_LOC = <project root>`.
6. For each requested name, in configured order:
   - use a matching context-state line if found;
   - otherwise call the keymap function for that name if an entry exists;
   - otherwise write `NAME = none`.
7. Append state lines not consumed by requested names.
8. Create the destination directory if required and write the `.tesenv` file
   with a final newline.

Context state takes precedence over the keymap for requested names. The
current code identifies a context entry using `line.startswith(key)`, so
state lines should use the expected `NAME = value` format; this is a prefix
check rather than an exact parsed-key comparison.

## Configuration used by the writer

The project configuration is INI-style and parsed with Python's
`configparser`. Section and key names are project-defined. In the current
`tesconfig`, the writer-relevant settings are:

```ini
[env]
envfile-location = C:/path/to/project/.infra/.tesenv

[keymap]
keymap-base-location = .infra/env/keymap/
envfile-keys-list = [DEVICE_NAME, OS, USER, PARENT_PROJECT_LOC]
```

`envfile-location` selects the output file. `envfile-keys-list` is parsed as
a comma-separated list; optional surrounding square brackets are removed,
whitespace is trimmed, and optional quotes around items are stripped. Key
names cannot contain commas with this parser.

`keymap-base-location` is present in the config but the current writer does
not read it. The writer uses source-code constants for the keymap, scripts,
context directory, and config-file paths.

## Commands and installation

### Environment writer command

The implemented command that consumes the keymap is the Python environment
writer. From the project root, its intended invocation is:

```powershell
python .infra\env\bin\envWriter.py
```

It takes no command-line arguments. It derives the project root from its own
file location, reads its configuration, looks for context state, evaluates
requested keymap functions, and writes the configured `.tesenv` output.
Because it currently derives paths from the repository layout and fixed
constants, changing the working directory is not intended to change which
project it processes.

Before invoking it, the config path, keymap JSON shape, and generated Python
functions must match the assumptions documented above. With the files in the
current checkout, the config path and `keys` JSON nesting mismatch mean this
command will fail until those are reconciled. See
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
- `setenv.py` and the configured JavaScript source are empty, so the generated module
  currently contains no keymap functions.
- `keymap-base-location`, `supported-langs`, and the translator declarations
  in `keymap.json` are not currently consumed by the writer.
- The writer's `project_root()` calculation (`script.parents[3]`) resolves to
  the repository root for its current `.infra/env/bin/` location. Its
  docstring still mentions the older `.infra/env/programs/` layout.

These limitations are recorded to distinguish the intended system design
from behavior implemented by the current files.
