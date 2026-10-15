from __future__ import annotations

from datetime import datetime
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from teches_commit_message_generator import __version__
from teches_commit_message_generator.cli import (
    discover_repositories,
    format_compact_files,
    format_date,
    render_template,
    select_template,
    staged_files,
    strip_template_comments,
)


class CompactPathTests(unittest.TestCase):
    """Check exact file grouping and complete-directory wildcard behavior."""

    def test_keeps_a_root_file_exact_when_other_files_are_unstaged(self) -> None:
        """Do not imply the whole project is staged for one root-level file."""
        self.assertEqual(
            format_compact_files(
                [".gitignore"],
                [".gitignore", "README.md", "src/app.py"],
            ),
            "{proj}/.gitignore",
        )

    def test_groups_sibling_names_with_semicolons(self) -> None:
        """Represent staged siblings with one shared directory prefix."""
        self.assertEqual(
            format_compact_files(
                ["docs/guide.md", "docs/reference.md"],
                ["docs/guide.md", "docs/reference.md", "docs/draft.md"],
            ),
            "{proj}/docs/guide.md;reference.md",
        )

    def test_wildcards_only_fully_staged_directories(self) -> None:
        """Use a folder wildcard only when all visible files below it are staged."""
        self.assertEqual(
            format_compact_files(
                ["docs/guide.md", "docs/reference.md", "src/app.py"],
                [
                    ".gitignore",
                    "docs/guide.md",
                    "docs/reference.md",
                    "src/app.py",
                    "src/config.py",
                ],
            ),
            "{proj}/docs/*, {proj}/src/app.py",
        )

    def test_wildcards_project_root_only_when_every_file_is_staged(self) -> None:
        """Use the project wildcard only when all Git-visible files are staged."""
        files = [".gitignore", "docs/guide.md"]
        self.assertEqual(format_compact_files(files, files), "{proj}/*")

    def test_wildcard_does_not_claim_nested_directories(self) -> None:
        """Compact a leaf folder without implying its parent folder's files."""
        files = [
            "src/pkg/__init__.py",
            "src/pkg/cli.py",
        ]
        self.assertEqual(
            format_compact_files(files, files),
            "{proj}/src/pkg/*",
        )


class TemplateTests(unittest.TestCase):
    """Check comments, sections, dates, and template tag rendering."""

    def test_strips_block_and_line_comments(self) -> None:
        """Remove comments without collapsing the template's line structure."""
        self.assertEqual(
            strip_template_comments("before/// hide\nthis ///after // hidden\nlast"),
            "before\nafter \nlast",
        )

    def test_selects_repository_section_before_shared_fallback(self) -> None:
        """Prefer the matching repository section when a shared one also exists."""
        template = (
            "%%template:all%%\nshared\n"
            "%%template::teches%%\nproject\n"
        )
        self.assertEqual(select_template(template, "teches"), "project\n")
        self.assertEqual(select_template(template, "other"), "shared\n")

    def test_rejects_duplicate_template_sections(self) -> None:
        """Report ambiguous repeated section names instead of choosing silently."""
        with self.assertRaisesRegex(ValueError, "Duplicate template section"):
            select_template(
                "%%template:all%%\none\n%%template:all%%\ntwo\n",
                "teches",
            )

    def test_renders_tags_and_preserves_unknown_tags(self) -> None:
        """Fill supported indexed and compact tags while leaving unknown tags intact."""
        self.assertEqual(
            render_template(
                "%%nate-date%% %%staged-files%% %%staged-files-compact%% "
                "%%staged-files-compact[1]%% %%unknown%%",
                ["docs/guide.md", "docs/reference.md"],
                datetime(2026, 10, 15),
                ["docs/guide.md", "docs/reference.md", "docs/draft.md"],
            ),
            "10152026 docs/guide.md, docs/reference.md "
            "{proj}/docs/guide.md;reference.md {proj}/docs/guide.md %%unknown%%",
        )


class GitIntegrationTests(unittest.TestCase):
    """Exercise repository discovery and staged-path lookup against real Git."""

    def test_reports_package_version(self) -> None:
        """Expose the requested version through the installed package API."""
        self.assertEqual(__version__, "0.2.0")

    def test_discovers_repository_and_reads_staged_files(self) -> None:
        """Find a temporary repository and return its staged relative paths."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._git(root, "init", "-q")
            (root / ".gitignore").write_text("*.cache\n", encoding="utf-8")
            self._git(root, "add", ".gitignore")

            self.assertEqual(discover_repositories(root), [root.resolve()])
            self.assertEqual(staged_files(root), [".gitignore"])

    @staticmethod
    def _git(root: Path, *arguments: str) -> None:
        """Run a Git command in the temporary test repository."""
        subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
        )


if __name__ == "__main__":
    unittest.main()
