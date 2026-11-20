"""The package version and the manifest version must agree."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import classics_index  # noqa: E402


class TestVersion(unittest.TestCase):
    def _pyproject(self):
        import tomllib
        with open(os.path.join(HERE, "pyproject.toml"), "rb") as fh:
            return tomllib.load(fh)["project"]["version"]

    def test_version_matches_pyproject(self):
        self.assertEqual(classics_index.__version__, self._pyproject())

    def test_version_is_semver(self):
        parts = classics_index.__version__.split(".")
        self.assertEqual(len(parts), 3, classics_index.__version__)
        self.assertTrue(all(p.isdigit() for p in parts), classics_index.__version__)


if __name__ == "__main__":
    unittest.main()
