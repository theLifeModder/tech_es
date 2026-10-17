# `teches user`

This TechES command manages project-local user profiles stored in
`.infra/env/config/user/userdata.ini`. Install it alongside the TechES
initializer by running `teches init`, or install the package directly into the
same Python environment as `teches_init`:

```powershell
python -m pip install -e .infra\bin\teches_user
```

The command is registered as a `teches` subcommand:

```text
teches user --create-profile profname:<name> [uname:<username>] [email:<email>]
teches user --set-profile <name>
teches user --delete-profile <name>
teches user --update-gitinfo [<name>]
```

Short aliases are `-c`, `-s`, `-d`, and `-g`, respectively. Choose exactly one
action per invocation. For create, `profname:<name>` is required; omitted
username and email values are prompted for. Create values use the exact
`profname:`, `uname:`, and `email:` prefixes without spaces before the value.
Set and delete accept either a plain profile name or `profname:<name>`.

Named profiles are stored in `[profile <name>]` sections with `uname` and
`email` fields. `--set-profile` copies that identity to `[default]`, which is
the active profile used by `teches init`, and asks whether to update the
current repository's local Git identity. `--update-gitinfo` updates only the
local Git config, using the active profile when no name is given. Neither
operation changes global Git settings. Deleting removes a saved named profile;
it requires confirmation and does not remove or change `[default]`.
