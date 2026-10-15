# `teches_init`

This package supplies the bootstrap `teches` command. Install it first from
the project root:

```powershell
python -m pip install -e .infra\bin\teches_init
```

Then initialize the project:

```powershell
teches init
```

The command prompts for a username and email, then asks whether to update the
current project's local Git config with those values. If confirmed, it sets
`user.name` and `user.email` in that project's `.git/config`; it does not
change the global Git config. It also writes the values to
`.infra/env/config/user/userdata.ini` under the `[default]` profile, then
installs editable TechES packages found under `.infra/bin`.

Command packages register subcommands through the `teches.commands` Python
entry-point group. The bootstrap package owns the `teches` executable so
installing additional command packages does not replace that executable.

The installer uses the running interpreter to execute the equivalent of
`python -m pip install -e <package-directory>` for each discovered package.
Packages already installed in editable mode from the same directory are left
in place, so an initialization run does not try to replace its own active
command executable.
