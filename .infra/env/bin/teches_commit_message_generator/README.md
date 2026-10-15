# TechES Commit Message Generator

Version `0.2.0`. This package builds a commit message from the current Git
repository's staged files and `.infra/env/config/commit-message-template`.

Run it from the repository root with Python:

```powershell
python -m pip install -e .infra\env\bin\teches_commit_message_generator
teches-commit-message
```

The VS Code task **Generate commit message template** runs the package directly
from the workspace source, so it does not require an editable install. Add
`--print-only` to print the generated message instead of copying it to the
Windows clipboard.

The generator checks the root repository and immediate nested repositories.
It requires exactly one of them to have staged files. Compact paths group
staged siblings with semicolons and use a directory wildcard only when all
Git-visible files directly inside that directory are staged.
