from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from teches_init.installer import _install_editable


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


if __name__ == "__main__":
    unittest.main()
