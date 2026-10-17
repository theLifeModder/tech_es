# TechES

TechES is a project workspace for shared development tools and project
infrastructure. It includes the `teches` bootstrap CLI, command plugins,
environment/keymap tooling, and the `bio_fuel` Minecraft Bedrock add-on project.

## Getting started

### Prerequisites

- Python 3.10 or newer.
- Git.
- Node.js and npm if you plan to build or work on `bio_fuel`.
- Visual Studio Code is recommended for the included tasks and file-system
  command.

### Install the TechES initializer

From the repository root, create and activate a virtual environment, then
install the initializer in that same environment:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .\.infra\bin\teches_init
```

In Git Bash, activate the environment with:

```bash
source .venv/Scripts/activate
```

The editable install lets the CLI import its source directly from this checkout.
If PowerShell reports that the generated `teches.exe` launcher is blocked, run
the CLI through the active environment's Python instead:

```powershell
python -c "from teches_init.cli import cli; cli()" init
```

Use the same active Python environment for the install and command. The
initializer installs the TechES packages it discovers under `.infra/bin` and
the commit-message generator under `.infra/env/bin`. It also prompts for a
username and email to save in the project's default profile. It asks separately
before changing this repository's local Git `user.name` and `user.email`; it
does not change the global Git configuration.

Run `teches init --help` to see initialization options. If the launcher is
blocked, the Python invocation above also works with `--help` in place of
`init`.

### Refresh the generated environment file

Run the environment writer from the repository root:

```powershell
python .infra\env\bin\envWriter.py
```

It regenerates `.infra/env/config/.tesenv` from `tesconfig`, `keymap.json`,
the Python keymap functions, and any configured transpilers. The venv
configuration defaults to automatic detection: an activated venv is preferred,
then the writer's venv if applicable, then the repository's `.venv`. To use a
venv in a different location, set `venv-location` in `.infra/env/config/tesconfig`.

TechES tools that require current environment values should refresh this file
before use. The writer currently needs to be run explicitly; automatic refresh
before every TechES tool invocation is not yet wired in.

## Using the tools

### Commit-message generator

After `teches init`, run it from the repository root:

```powershell
teches-commit-message
```

The generator summarizes staged changes using
`.infra/env/config/commit-message-template` and copies the result to the
Windows clipboard. Use `--print-only` to print the message instead. The VS Code
task **Generate commit message template** is also available.

### File-system command

The `teches_fs` package registers the `fs` command with the `teches` CLI. For
example, to open a file in the current VS Code instance:

```powershell
teches fs --edit path\to\file
```

The `code` command must be available on `PATH`.

### User profiles

The `teches_user` package adds profile management for project-local user and
Git identity:

```powershell
teches user --create-profile profname:work uname:"Work User" email:work@example.com
teches user --set-profile work
teches user --update-gitinfo
```

Named profiles are stored in `.infra/env/config/user/userdata.ini`. Activating
a profile updates the `[default]` profile and offers to update this repository's
local Git identity; global Git config is not changed. See the
[`teches user` guide](.infra/bin/teches_user/README.md) for all options.

### `bio_fuel` Bedrock add-on

Install its JavaScript dependencies from the project directory:

```powershell
Set-Location bio_fuel
npm install
```

Useful scripts include:

```powershell
npm run build
npm run build:production
npm run lint
npm run mcaddon
```

The generated add-on and deployment commands depend on the Minecraft Bedrock
development tools available in the environment.

## Repository layout

```text
.infra/
  bin/teches_init/                 Bootstrap CLI package
  bin/teches_fs/                   `teches fs` command plugin
  env/
    bin/envWriter.py               Generates the project .tesenv file
    bin/teches_commit_message_generator/
                                    Commit-message generator package
    config/                        TechES configuration and templates
    keymap/                        Environment-value functions and mapping
bio_fuel/                          Minecraft Bedrock add-on project
extra/                             Additional project files
```

## Documentation

- [Keymap and environment system](.infra/doc/systems/keymap-system.md)
- [Initializer package guide](.infra/bin/teches_init/README.md)
- [Commit-message generator guide](.infra/env/bin/teches_commit_message_generator/README.md)

## Keeping this README current

Update this README alongside significant changes to project setup, major
components, or developer workflows so the onboarding instructions remain
accurate.
