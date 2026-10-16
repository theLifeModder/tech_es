from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from teches_init.installer import (
    COMMIT_MESSAGE_GENERATOR_DIRECTORY,
    INITIALIZER_PACKAGE_DIRECTORY,
    InstallOptions,
    _install_commit_message_generator,
    _install_editable,
    _package_candidates,
)


class EditableInstallTests(unittest.TestCase):
    """Verify editable package installs are skipped or forced as requested."""

    def setUp(self) -> None:
        """Prepare metadata identifying a package installed from the test source."""
        self.package_directory = Path("teches_fs").resolve()
        self.direct_url = json.dumps(
            {
                "dir_info": {"editable": True},
                "url": self.package_directory.as_uri(),
            }
        )

    def test_discovers_initializer_in_its_package_directory(self) -> None:
        """Find the initializer project directly under the package source directory."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_bin = Path(temporary_directory)
            initializer_directory = source_bin / INITIALIZER_PACKAGE_DIRECTORY
            initializer_directory.mkdir(parents=True)
            (initializer_directory / "pyproject.toml").write_text(
                "[project]\nname = 'teches_init'\n",
                encoding="utf-8",
            )

            candidates = _package_candidates(source_bin, InstallOptions())

        self.assertIn(("install", initializer_directory), candidates)

    @patch("teches_init.installer.subprocess.run")
    @patch("teches_init.installer.distribution")
    def test_skips_reinstall_of_same_editable_source(
        self, installed_distribution: unittest.mock.Mock, run_pip: unittest.mock.Mock
    ) -> None:
        """Avoid pip uninstalling an executable already running from this source."""
        installed_distribution.return_value.read_text.return_value = self.direct_url

        _install_editable(self.package_directory, force=False)

        run_pip.assert_not_called()

    @patch("teches_init.installer.subprocess.run")
    @patch("teches_init.installer.distribution")
    def test_force_reinstalls_same_editable_source(
        self, installed_distribution: unittest.mock.Mock, run_pip: unittest.mock.Mock
    ) -> None:
        """Honor force by invoking pip even when the source is already installed."""
        installed_distribution.return_value.read_text.return_value = self.direct_url
        run_pip.return_value = SimpleNamespace(returncode=0)

        _install_editable(self.package_directory, force=True)

        run_pip.assert_called_once_with(
            [
                unittest.mock.ANY,
                "-m",
                "pip",
                "install",
                "-e",
                str(self.package_directory),
                "--force-reinstall",
            ],
            check=False,
        )


class CommitMessageGeneratorInstallTests(unittest.TestCase):
    """Check initialization installs the bundled generator and reports its outcome."""

    def setUp(self) -> None:
        """Create a temporary project containing the expected generator package."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.project_root = Path(self.temporary_directory.name)
        self.generator_directory = (
            self.project_root / ".infra" / COMMIT_MESSAGE_GENERATOR_DIRECTORY
        )
        self.generator_directory.mkdir(parents=True)
        (self.generator_directory / "pyproject.toml").write_text(
            "[project]\nname = 'teches-commit-message-generator'\n",
            encoding="utf-8",
        )

    @patch("teches_init.installer._install_editable")
    def test_reports_start_and_successful_install(
        self, install_editable: unittest.mock.Mock
    ) -> None:
        """Log the generator's start and success while installing the project source."""
        messages: list[str] = []

        _install_commit_message_generator(
            self.project_root,
            self.project_root / ".infra",
            custom_infra_root=False,
            copy_whole_infra=False,
            force=False,
            status_callback=messages.append,
        )

        install_editable.assert_called_once_with(self.generator_directory, False)
        self.assertEqual(
            messages,
            [
                "Installing TechES commit message generator...",
                "Successfully installed TechES commit message generator.",
            ],
        )

    @patch(
        "teches_init.installer._install_editable",
        side_effect=RuntimeError("pip returned exit code 1"),
    )
    def test_raises_package_specific_error_on_install_failure(
        self, install_editable: unittest.mock.Mock
    ) -> None:
        """Propagate install failures with the generator package named explicitly."""
        messages: list[str] = []

        with self.assertRaisesRegex(
            RuntimeError,
            "Failed to install TechES commit message generator: pip returned exit code 1",
        ):
            _install_commit_message_generator(
                self.project_root,
                self.project_root / ".infra",
                custom_infra_root=False,
                copy_whole_infra=False,
                force=False,
                status_callback=messages.append,
            )

        install_editable.assert_called_once()
        self.assertEqual(messages, ["Installing TechES commit message generator..."])


if __name__ == "__main__":
    unittest.main()
