from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "release.py"
SPEC = importlib.util.spec_from_file_location("limitful_release", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
release = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release
SPEC.loader.exec_module(release)


class ReleaseMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository_root = Path(__file__).parents[3]

    def test_every_configured_package_has_consistent_versions(self) -> None:
        catalog = release.load_catalog(self.repository_root)

        self.assertEqual(
            set(catalog.packages),
            {
                "csharp/Limitful.Core",
                "typescript/main",
                "rust/main",
                "go",
                "python/main",
            },
        )
        for package_id in catalog.packages:
            metadata = release.validate_package(self.repository_root, catalog, package_id)
            self.assertEqual(metadata.version, "0.0.0")
            self.assertTrue(metadata.tag.endswith("v0.0.0"))

    def test_release_ready_rejects_zero_version(self) -> None:
        catalog = release.load_catalog(self.repository_root)

        with self.assertRaisesRegex(release.ReleaseError, "0.0.0"):
            release.validate_package(
                self.repository_root,
                catalog,
                "typescript/main",
                release_ready=True,
            )

    def test_unknown_package_is_rejected(self) -> None:
        catalog = release.load_catalog(self.repository_root)

        with self.assertRaisesRegex(release.ReleaseError, "Unknown package"):
            release.validate_package(self.repository_root, catalog, "java/main")

    def test_mismatched_version_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_fixture(root, manifest_version="1.2.3", package_version="1.2.4")
            catalog = release.load_catalog(root)

            with self.assertRaisesRegex(release.ReleaseError, "version mismatch"):
                release.validate_package(root, catalog, "fixture/main")

    def test_malformed_toml_is_rejected_with_the_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_fixture(root, manifest_version="1.2.3", package_version="1.2.3")
            (root / "fixture" / "main" / "pyproject.toml").write_text(
                "[project\nversion = nope\n", encoding="utf-8"
            )
            catalog = release.load_catalog(root)

            with self.assertRaisesRegex(release.ReleaseError, "pyproject.toml"):
                release.validate_package(root, catalog, "fixture/main")

    def test_changelog_notes_select_only_the_requested_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_fixture(root, manifest_version="1.2.3", package_version="1.2.3")
            changelog = root / "fixture" / "main" / "CHANGELOG.md"
            changelog.write_text(
                "# Changelog\n\n"
                "## [1.2.3](https://example.test/v1.2.3) (2026-10-10)\n\n"
                "* Added safe publishing.\n\n"
                "## 1.2.2 (2026-10-09)\n\n"
                "* Older release.\n",
                encoding="utf-8",
            )
            catalog = release.load_catalog(root)

            notes = release.release_notes(root, catalog, "fixture/main")

            self.assertIn("Added safe publishing", notes)
            self.assertNotIn("Older release", notes)

    def test_changelog_without_current_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_fixture(root, manifest_version="1.2.3", package_version="1.2.3")
            changelog = root / "fixture" / "main" / "CHANGELOG.md"
            changelog.write_text("# Changelog\n\n## 1.2.2\n\nOld.\n", encoding="utf-8")
            catalog = release.load_catalog(root)

            with self.assertRaisesRegex(release.ReleaseError, "1.2.3"):
                release.release_notes(root, catalog, "fixture/main")

    @staticmethod
    def _write_fixture(root: Path, *, manifest_version: str, package_version: str) -> None:
        package_root = root / "fixture" / "main"
        package_root.mkdir(parents=True)
        (root / ".release-please-manifest.json").write_text(
            json.dumps({"fixture/main": manifest_version}), encoding="utf-8"
        )
        (root / ".github" / "release").mkdir(parents=True)
        (root / ".github" / "release" / "packages.json").write_text(
            json.dumps(
                {
                    "repository": "MatanelGordon/Limitful",
                    "owner": "MatanelGordon",
                    "default_branch": "master",
                    "packages": {
                        "fixture/main": {
                            "display_name": "fixture",
                            "ecosystem": "python",
                            "package_name": "fixture",
                            "path": "fixture/main",
                            "tag_prefix": "python-fixture-v",
                            "changelog": "fixture/main/CHANGELOG.md",
                            "artifact_name": "python-fixture",
                            "version_sources": [
                                {
                                    "type": "toml",
                                    "path": "fixture/main/pyproject.toml",
                                    "keys": ["project", "version"],
                                },
                                {
                                    "type": "release-manifest",
                                    "path": ".release-please-manifest.json",
                                    "key": "fixture/main",
                                },
                            ],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        (package_root / "pyproject.toml").write_text(
            f'[project]\nname = "fixture"\nversion = "{package_version}"\n',
            encoding="utf-8",
        )
        (package_root / "CHANGELOG.md").write_text(
            f"# Changelog\n\n## {manifest_version}\n\nFixture.\n", encoding="utf-8"
        )


if __name__ == "__main__":
    unittest.main()
