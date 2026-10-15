"""Click commands exposed by the TechES file-system package."""

from __future__ import annotations

import shutil
import subprocess

import click


@click.command("fs")
@click.option(
    "-e",
    "--edit",
    "edit_file",
    type=click.Path(path_type=str),
    required=True,
    help="Open a file in the current Visual Studio Code instance.",
)
def fs_command(edit_file: str) -> None:
    """Open a file in Visual Studio Code."""
    editor_binary = shutil.which("code")
    if editor_binary is None:
        raise click.ClickException(
            "Visual Studio Code's 'code' command was not found on PATH."
        )
    result = subprocess.run(
        [editor_binary, "-r", edit_file],
        check=False,
    )
    if result.returncode != 0:
        raise click.ClickException(
            f"Visual Studio Code exited with status {result.returncode}."
        )
