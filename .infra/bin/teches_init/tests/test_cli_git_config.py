from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from teches_init import cli as cli_module


class GitConfigPromptTests(unittest.TestCase):
    """Check that the init prompt writes or preserves project-local Git identity."""

    def setUp(self) -> None:
        """Create a CLI runner and stable project path for the command tests."""
        self.runner = CliRunner()
        self.project_root = Path("project")

    @patch("teches_init.cli.install_infrastructure", return_value=[])
    @patch("teches_init.cli.save_default_profile", return_value=Path("userdata.ini"))
    @patch("teches_init.cli.find_project_root", return_value=Path("project"))
    @patch("teches_init.cli.subprocess.run")
    def test_yes_updates_project_local_git_identity(
        self,
        run_git: unittest.mock.Mock,
        _find_project_root: unittest.mock.Mock,
        _save_default_profile: unittest.mock.Mock,
        _install_infrastructure: unittest.mock.Mock,
    ) -> None:
        """A yes answer writes both supplied values to local Git config."""
        result = self.runner.invoke(
            cli_module.cli,
            ["init", "--username", "Example User", "--email", "user@example.com"],
            input="y\n",
        )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            run_git.call_args_list,
            [
                unittest.mock.call(
                    [
                        "git",
                        "config",
                        "--local",
                        "--replace-all",
                        "user.name",
                        "Example User",
                    ],
                    cwd=self.project_root,
                    check=True,
                    capture_output=True,
                    text=True,
                ),
                unittest.mock.call(
                    [
                        "git",
                        "config",
                        "--local",
                        "--replace-all",
                        "user.email",
                        "user@example.com",
                    ],
                    cwd=self.project_root,
                    check=True,
                    capture_output=True,
                    text=True,
                ),
            ],
        )

    @patch("teches_init.cli.install_infrastructure", return_value=[])
    @patch("teches_init.cli.save_default_profile", return_value=Path("userdata.ini"))
    @patch("teches_init.cli.find_project_root", return_value=Path("project"))
    @patch("teches_init.cli.subprocess.run")
    def test_no_leaves_git_config_unchanged(
        self,
        run_git: unittest.mock.Mock,
        _find_project_root: unittest.mock.Mock,
        _save_default_profile: unittest.mock.Mock,
        _install_infrastructure: unittest.mock.Mock,
    ) -> None:
        """A no answer skips Git config writes while allowing initialization."""
        result = self.runner.invoke(
            cli_module.cli,
            ["init", "--username", "Example User", "--email", "user@example.com"],
            input="n\n",
        )

        self.assertEqual(result.exit_code, 0, result.output)
        run_git.assert_not_called()

    @patch("teches_init.cli.install_infrastructure", return_value=[])
    @patch("teches_init.cli.save_default_profile", return_value=Path("userdata.ini"))
    @patch("teches_init.cli.find_project_root", return_value=Path("project"))
    @patch(
        "teches_init.cli.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "git", stderr="not a repository"),
    )
    def test_git_failure_is_reported(
        self,
        _run_git: unittest.mock.Mock,
        _find_project_root: unittest.mock.Mock,
        _save_default_profile: unittest.mock.Mock,
        install_infrastructure: unittest.mock.Mock,
    ) -> None:
        """A failed Git write is surfaced and prevents later package installation."""
        result = self.runner.invoke(
            cli_module.cli,
            ["init", "--username", "Example User", "--email", "user@example.com"],
            input="y\n",
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "Could not update local Git config: not a repository", result.output
        )
        install_infrastructure.assert_not_called()


if __name__ == "__main__":
    unittest.main()
