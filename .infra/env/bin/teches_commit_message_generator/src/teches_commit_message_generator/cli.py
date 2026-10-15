"""Build commit messages from staged Git paths and a project template."""

from __future__ import annotations

import argparse
import base64
from collections.abc import Sequence
from datetime import datetime
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


TEMPLATE_RELATIVE_PATH = Path(
    ".infra",
    "env",
    "config",
    "commit-message-template",
)
SKIPPED_DIRECTORY_NAMES = {".git", "node_modules"}


def git_root(directory: Path) -> Path | None:
    """Return a Git repository's root, or None when the directory is outside one."""
    result = subprocess.run(
        ["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def discover_repositories(workspace_root: Path) -> list[Path]:
    """Find the workspace repository and any immediate nested repositories."""
    root = git_root(workspace_root)
    if root is None:
        raise ValueError(f"Not inside a Git repository: {workspace_root}")

    roots = [root]
    for entry in root.iterdir():
        if not entry.is_dir() or entry.name in SKIPPED_DIRECTORY_NAMES:
            continue
        nested_root = git_root(entry)
        if (
            nested_root is not None
            and nested_root != root
            and nested_root not in roots
        ):
            roots.append(nested_root)
    return roots


def _git_paths(repository_root: Path, *arguments: str) -> list[str]:
    """Run a Git path-list command and decode its NUL-separated result."""
    result = subprocess.run(
        ["git", "-C", str(repository_root), *arguments, "-z"],
        check=True,
        capture_output=True,
    )
    return [os.fsdecode(path) for path in result.stdout.split(b"\0") if path]


def staged_files(repository_root: Path) -> list[str]:
    """Return staged file paths in stable sorted order."""
    return sorted(_git_paths(repository_root, "diff", "--cached", "--name-only"))


def repository_files(repository_root: Path) -> list[str]:
    """Return tracked and non-ignored untracked paths visible to Git."""
    return _git_paths(
        repository_root,
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
    )


def file_directories(files: Sequence[str]) -> set[str]:
    """Collect every parent directory of the supplied repository-relative paths."""
    directories: set[str] = set()
    for file in files:
        directory = PurePosixPath(file).parent.as_posix()
        while True:
            directories.add(directory)
            if directory == ".":
                break
            directory = PurePosixPath(directory).parent.as_posix()
    return directories


def format_file_path(file: str) -> str:
    """Format a staged path with the commit template's project-relative prefix."""
    return f"{{proj}}/{file}"


def format_compact_files(
    files: Sequence[str],
    all_files: Sequence[str] | None = None,
) -> str:
    """Group staged siblings and wildcard only directories that are fully staged."""
    staged = set(files)
    repository_paths = set(all_files or ()) | staged
    directories = file_directories(sorted(repository_paths))
    wildcard_directories: list[str] = []

    for directory in sorted(
        directories,
        key=lambda value: (value.count("/"), value.casefold()),
    ):
        if any(
            parent == "." or directory.startswith(f"{parent}/")
            for parent in wildcard_directories
        ):
            continue

        files_in_directory = [
            file
            for file in repository_paths
            if PurePosixPath(file).parent.as_posix() == directory
        ]
        if files_in_directory and all(file in staged for file in files_in_directory):
            wildcard_directories.append(directory)

    compact_paths: list[tuple[str, str]] = [
        (
            directory,
            "{proj}/*" if directory == "." else f"{{proj}}/{directory}/*",
        )
        for directory in wildcard_directories
    ]

    staged_by_directory: dict[str, list[str]] = {}
    for file in files:
        directory = PurePosixPath(file).parent.as_posix()
        if any(
            wildcard == "."
            or directory == wildcard
            or directory.startswith(f"{wildcard}/")
            for wildcard in wildcard_directories
        ):
            continue
        staged_by_directory.setdefault(directory, []).append(
            PurePosixPath(file).name
        )

    for directory, filenames in staged_by_directory.items():
        common_path = "{proj}" if directory == "." else f"{{proj}}/{directory}"
        sort_path = (
            filenames[0]
            if directory == "."
            else f"{directory}/{filenames[0]}"
        )
        compact_paths.append((sort_path, f"{common_path}/{';'.join(filenames)}"))

    return ", ".join(value for _, value in sorted(compact_paths, key=lambda item: item[0].casefold()))


def format_date(date: datetime | None = None) -> str:
    """Format a date as the template's MMDDYYYY value."""
    return (date or datetime.now()).strftime("%m%d%Y")


def strip_template_comments(template: str) -> str:
    """Remove template comment blocks and line comments while retaining line breaks."""
    output: list[str] = []
    cursor = 0
    while cursor < len(template):
        opening = template.find("///", cursor)
        if opening == -1:
            output.append(template[cursor:])
            break
        output.append(template[cursor:opening])
        closing = template.find("///", opening + 3)
        if closing == -1:
            break
        comment = template[opening : closing + 3]
        output.extend(re.findall(r"\r\n|\r|\n", comment))
        cursor = closing + 3

    uncommented = "".join(output)
    prefix_comment = uncommented.find("//<")
    if (
        prefix_comment != -1
        and uncommented.find("//<", prefix_comment + 3) == -1
    ):
        uncommented = uncommented[prefix_comment + 3 :]
    return re.sub(r"//[^\r\n]*", "", uncommented)


def select_template(template_file: str, repository_name: str) -> str:
    """Select a repository-specific template section, shared section, or whole file."""
    uncommented_template = strip_template_comments(template_file)
    sections: dict[str, str] = {}
    current_section: str | None = None
    marker_pattern = re.compile(r"^[ \t]*%%template::?([^%]+)%%[ \t]*(?:\r?\n)?$")

    for line in uncommented_template.splitlines(keepends=True):
        marker = marker_pattern.match(line)
        if marker:
            current_section = marker.group(1).strip()
            if current_section in sections:
                raise ValueError(f"Duplicate template section: {current_section}")
            sections[current_section] = ""
        elif current_section is not None:
            sections[current_section] += line

    if not sections:
        return template_file
    if repository_name in sections:
        return sections[repository_name]
    if "all" in sections:
        return sections["all"]
    raise ValueError(
        f'No commit message template for repository "{repository_name}" '
        "and no template::all fallback was found."
    )


def render_template(
    template: str,
    files: Sequence[str],
    date: datetime | None = None,
    all_files: Sequence[str] | None = None,
) -> str:
    """Replace known template tags with the date and staged-file values."""
    values = {
        "nate-date": format_date(date),
        "staged-files": ", ".join(files),
        "staged-files-compact": format_compact_files(files, all_files),
    }
    tag_pattern = re.compile(r"%%([^%]+)%%")
    indexed_pattern = re.compile(r"^(staged-files(?:-compact)?)\[(\d+)\]$")

    def replace_tag(match: re.Match[str]) -> str:
        """Resolve a single recognized template placeholder."""
        tag = match.group(0)
        name = match.group(1)
        if name in values:
            return values[name]
        indexed = indexed_pattern.match(name)
        if indexed is None:
            return tag
        index = int(indexed.group(2)) - 1
        if index < 0 or index >= len(files):
            return ""
        file = files[index]
        if indexed.group(1) == "staged-files-compact":
            return format_file_path(file)
        return file

    return tag_pattern.sub(replace_tag, template)


def copy_to_clipboard(text: str) -> None:
    """Copy text to the Windows clipboard and verify it was copied unchanged."""
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    command = (
        '$ErrorActionPreference = "Stop"; '
        "$encoded = [Console]::In.ReadLine(); "
        "if ($null -eq $encoded) { exit 1 }; "
        "$text = [Text.Encoding]::UTF8.GetString("
        "[Convert]::FromBase64String($encoded)); "
        "Set-Clipboard -Value $text; "
        "$copied = Get-Clipboard -Raw; "
        'if ($copied -cne $text) { throw "Clipboard verification failed." }'
    )
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-STA",
            "-Command",
            command,
        ],
        input=encoded,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
            or "PowerShell could not copy the message to the clipboard."
        )


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for workspace and print-only options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "workspace_root",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="Workspace directory to inspect (defaults to the current directory).",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print the generated message instead of copying it to the clipboard.",
    )
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    """Generate one message for the repository with staged files."""
    args = build_parser().parse_args(argv)
    workspace_root = args.workspace_root.resolve()
    repositories = discover_repositories(workspace_root)
    repositories_with_staged = [
        (repository, staged_files(repository))
        for repository in repositories
    ]
    repositories_with_staged = [
        (repository, files)
        for repository, files in repositories_with_staged
        if files
    ]

    if not repositories_with_staged:
        raise ValueError("No staged files found in the workspace Git repositories.")
    if len(repositories_with_staged) > 1:
        raise ValueError(
            "Staged files were found in more than one Git repository. "
            "Stage changes in only the repository whose message you are preparing."
        )

    repository_root, files = repositories_with_staged[0]
    all_files = repository_files(repository_root)
    template_path = repositories[0] / TEMPLATE_RELATIVE_PATH
    if not template_path.is_file():
        raise FileNotFoundError(f"Commit message template not found: {template_path}")

    template_file = template_path.read_text(encoding="utf-8")
    template = select_template(template_file, repository_root.name)
    message = render_template(template, files, all_files=all_files)
    if args.print_only:
        sys.stdout.write(message)
    else:
        copy_to_clipboard(message)
        print(f"Commit message copied to clipboard for {repository_root}.")
    return 0


def main() -> int:
    """Run the CLI and report failures as actionable error messages."""
    try:
        return run()
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
