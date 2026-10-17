from __future__ import annotations

import configparser
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from teches_init.profiles import PROFILE_FILE, create_profile, read_profile
from teches_user.cli import user_command


class UserProfileCommandTests(unittest.TestCase):
    """Exercise profile lifecycle and project-local Git identity commands."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.project_root = Path(self.temporary_directory.name)
        (self.project_root / ".infra" / "bin").mkdir(parents=True)
        self.profile_path = self.project_root / PROFILE_FILE
        self.runner = CliRunner()

    @patch("teches_user.cli.find_project_root")
    def test_create_profile_prompts_for_optional_identity_fields(
        self, find_root: unittest.mock.Mock
    ) -> None:
        find_root.return_value = self.project_root

        result = self.runner.invoke(
            user_command,
            ["--create-profile", "profname:work"],
            input="Work User\nwork@example.com\n",
        )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(read_profile(self.project_root, "work"), ("Work User", "work@example.com"))

    @patch("teches_user.cli.find_project_root")
    def test_create_rejects_duplicate_profile_without_overwriting(
        self, find_root: unittest.mock.Mock
    ) -> None:
        find_root.return_value = self.project_root
        create_profile(self.project_root, "work", "Original", "old@example.com")

        result = self.runner.invoke(
            user_command,
            [
                "--create-profile",
                "profname:work",
                "uname:Replacement",
                "email:new@example.com",
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("already exists", result.output)
        self.assertEqual(
            read_profile(self.project_root, "work"),
            ("Original", "old@example.com"),
        )

    def test_named_default_profile_is_distinct_from_active_profile(self) -> None:
        create_profile(
            self.project_root,
            "default",
            "Named Default",
            "named@example.com",
        )
        from teches_init.profiles import save_default_profile

        save_default_profile(self.project_root, "Active", "active@example.com")

        self.assertEqual(
            read_profile(self.project_root, "default"),
            ("Named Default", "named@example.com"),
        )
        self.assertEqual(
            read_profile(self.project_root),
            ("Active", "active@example.com"),
        )

    @patch("teches_user.cli.click.confirm", return_value=False)
    @patch("teches_user.cli.find_project_root")
    def test_set_profile_updates_active_default_without_git_changes(
        self,
        find_root: unittest.mock.Mock,
        _confirm: unittest.mock.Mock,
    ) -> None:
        find_root.return_value = self.project_root
        create_profile(self.project_root, "work", "Work User", "work@example.com")

        result = self.runner.invoke(user_command, ["--set-profile", "work"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(read_profile(self.project_root), ("Work User", "work@example.com"))

    @patch("teches_user.cli.subprocess.run")
    @patch("teches_user.cli.find_project_root")
    def test_update_gitinfo_uses_active_profile_by_default(
        self,
        find_root: unittest.mock.Mock,
        run_git: unittest.mock.Mock,
    ) -> None:
        find_root.return_value = self.project_root
        from teches_init.profiles import save_default_profile

        save_default_profile(self.project_root, "Work User", "work@example.com")

        result = self.runner.invoke(user_command, ["--update-gitinfo"])

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
                        "Work User",
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
                        "work@example.com",
                    ],
                    cwd=self.project_root,
                    check=True,
                    capture_output=True,
                    text=True,
                ),
            ],
        )

    @patch("teches_user.cli.find_project_root")
    def test_delete_profile_preserves_other_and_default_profiles(
        self, find_root: unittest.mock.Mock
    ) -> None:
        find_root.return_value = self.project_root
        create_profile(self.project_root, "work", "Work User", "work@example.com")
        create_profile(self.project_root, "personal", "Personal", "home@example.com")

        result = self.runner.invoke(
            user_command,
            ["--delete-profile", "work"],
            input="y\n",
        )

        self.assertEqual(result.exit_code, 0, result.output)
        config = configparser.ConfigParser(interpolation=None)
        config.read(self.profile_path, encoding="utf-8")
        self.assertFalse(config.has_section("profile work"))
        self.assertTrue(config.has_section("profile personal"))

    @patch("teches_user.cli.find_project_root")
    def test_declining_delete_confirmation_preserves_profile(
        self, find_root: unittest.mock.Mock
    ) -> None:
        find_root.return_value = self.project_root
        create_profile(self.project_root, "work", "Work User", "work@example.com")

        result = self.runner.invoke(
            user_command,
            ["--delete-profile", "work"],
            input="n\n",
        )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            read_profile(self.project_root, "work"),
            ("Work User", "work@example.com"),
        )

    def test_requires_exactly_one_action(self) -> None:
        result = self.runner.invoke(user_command, [])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Choose exactly one", result.output)

    def test_reports_local_git_write_failure(self) -> None:
        with patch(
            "teches_user.cli.find_project_root",
            return_value=self.project_root,
        ), patch(
            "teches_user.cli.subprocess.run",
            side_effect=subprocess.CalledProcessError(
                1, "git", stderr="not a repository"
            ),
        ):
            from teches_init.profiles import save_default_profile

            save_default_profile(self.project_root, "Work User", "work@example.com")
            result = self.runner.invoke(user_command, ["--update-gitinfo"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Could not update local Git config: not a repository", result.output)


if __name__ == "__main__":
    unittest.main()
