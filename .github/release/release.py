#!/usr/bin/env python3
"""Validate Limitful release metadata and extract package release notes."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
CATALOG_PATH = Path(".github/release/packages.json")


class ReleaseError(ValueError):
    """Raised when release metadata is unsafe or inconsistent."""


@dataclass(frozen=True)
class Package:
    package_id: str
    display_name: str
    ecosystem: str
    package_name: str
    path: str
    tag_prefix: str
    changelog: str
    artifact_name: str
    version_sources: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class Catalog:
    repository: str
    owner: str
    default_branch: str
    packages: dict[str, Package]


@dataclass(frozen=True)
class Metadata:
    package_id: str
    display_name: str
    ecosystem: str
    package_name: str
    path: str
    version: str
    tag: str
    changelog: str
    artifact_name: str
    repository: str
    owner: str
    default_branch: str

    def as_dict(self) -> dict[str, str]:
        return {
            "package_id": self.package_id,
            "display_name": self.display_name,
            "ecosystem": self.ecosystem,
            "package_name": self.package_name,
            "path": self.path,
            "version": self.version,
            "tag": self.tag,
            "changelog": self.changelog,
            "artifact_name": self.artifact_name,
            "repository": self.repository,
            "owner": self.owner,
            "default_branch": self.default_branch,
        }


def _safe_path(root: Path, relative: str) -> Path:
    root = root.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ReleaseError(f"Path escapes repository root: {relative}") from error
    return candidate


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseError(f"Cannot read valid JSON from {path}: {error}") from error


def load_catalog(root: Path) -> Catalog:
    data = _read_json(_safe_path(root, str(CATALOG_PATH)))
    try:
        raw_packages = data["packages"]
        packages = {
            package_id: Package(
                package_id=package_id,
                display_name=value["display_name"],
                ecosystem=value["ecosystem"],
                package_name=value["package_name"],
                path=value["path"],
                tag_prefix=value["tag_prefix"],
                changelog=value["changelog"],
                artifact_name=value["artifact_name"],
                version_sources=tuple(value["version_sources"]),
            )
            for package_id, value in raw_packages.items()
        }
        catalog = Catalog(
            repository=data["repository"],
            owner=data["owner"],
            default_branch=data["default_branch"],
            packages=packages,
        )
    except (KeyError, TypeError, AttributeError) as error:
        raise ReleaseError(f"Malformed release catalog: {error}") from error

    if not packages:
        raise ReleaseError("Release catalog contains no packages")
    if len({package.artifact_name for package in packages.values()}) != len(packages):
        raise ReleaseError("Release artifact names must be unique")
    return catalog


def _nested_value(data: Any, keys: list[str], source_path: Path) -> Any:
    value = data
    try:
        for key in keys:
            value = value[key]
    except (KeyError, TypeError) as error:
        joined = ".".join(keys)
        raise ReleaseError(f"Missing {joined} in {source_path}") from error
    return value


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as source:
            return tomllib.load(source)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ReleaseError(f"Cannot read valid TOML from {path}: {error}") from error


def _read_version(root: Path, source: dict[str, Any]) -> str:
    try:
        source_type = source["type"]
        path = _safe_path(root, source["path"])
    except KeyError as error:
        raise ReleaseError(f"Malformed version source: missing {error}") from error

    try:
        if source_type == "text":
            value = path.read_text(encoding="utf-8").strip()
        elif source_type == "json":
            value = _nested_value(_read_json(path), source["keys"], path)
        elif source_type == "toml":
            value = _nested_value(_read_toml(path), source["keys"], path)
        elif source_type == "xml":
            tree = ET.parse(path)
            value = tree.findtext(source["xpath"])
            if value is None:
                raise ReleaseError(f"Missing {source['xpath']} in {path}")
        elif source_type == "toml-array":
            data = _read_toml(path)
            entries = data.get(source["array"], [])
            matches = [entry for entry in entries if entry.get("name") == source["name"]]
            if len(matches) != 1:
                raise ReleaseError(
                    f"Expected exactly one {source['name']} entry in {path}; found {len(matches)}"
                )
            value = matches[0][source["field"]]
        elif source_type == "release-manifest":
            value = _read_json(path)[source["key"]]
        else:
            raise ReleaseError(f"Unsupported version source type: {source_type}")
    except ReleaseError:
        raise
    except (OSError, KeyError, TypeError, ET.ParseError) as error:
        raise ReleaseError(f"Cannot read version from {path}: {error}") from error

    if not isinstance(value, str) or not SEMVER.fullmatch(value):
        raise ReleaseError(f"Invalid stable semantic version in {path}: {value!r}")
    return value


def validate_package(
    root: Path,
    catalog: Catalog,
    package_id: str,
    *,
    release_ready: bool = False,
) -> Metadata:
    try:
        package = catalog.packages[package_id]
    except KeyError as error:
        raise ReleaseError(f"Unknown package: {package_id}") from error

    versions = [_read_version(root, source) for source in package.version_sources]
    if len(set(versions)) != 1:
        raise ReleaseError(
            f"{package_id} version mismatch across configured sources: {', '.join(versions)}"
        )
    version = versions[0]
    if release_ready and version == "0.0.0":
        raise ReleaseError(f"{package_id} cannot release placeholder version 0.0.0")

    package_root = _safe_path(root, package.path)
    changelog = _safe_path(root, package.changelog)
    if not package_root.is_dir():
        raise ReleaseError(f"Package path is not a directory: {package.path}")
    if not changelog.is_file():
        raise ReleaseError(f"Package changelog does not exist: {package.changelog}")

    return Metadata(
        package_id=package_id,
        display_name=package.display_name,
        ecosystem=package.ecosystem,
        package_name=package.package_name,
        path=package.path,
        version=version,
        tag=f"{package.tag_prefix}{version}",
        changelog=package.changelog,
        artifact_name=package.artifact_name,
        repository=catalog.repository,
        owner=catalog.owner,
        default_branch=catalog.default_branch,
    )


def release_notes(root: Path, catalog: Catalog, package_id: str) -> str:
    metadata = validate_package(root, catalog, package_id, release_ready=True)
    changelog_path = _safe_path(root, metadata.changelog)
    lines = changelog_path.read_text(encoding="utf-8").splitlines()
    version_pattern = re.compile(rf"(?<![0-9]){re.escape(metadata.version)}(?![0-9])")
    start: int | None = None
    for index, line in enumerate(lines):
        if line.startswith("## ") and version_pattern.search(line[3:]):
            start = index
            break
    if start is None:
        raise ReleaseError(
            f"No changelog section for {metadata.version} in {metadata.changelog}"
        )

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    notes = "\n".join(lines[start:end]).strip() + "\n"
    return notes


def _write_github_output(path: Path, metadata: Metadata) -> None:
    values = metadata.as_dict()
    with path.open("a", encoding="utf-8") as output:
        for key, value in values.items():
            if "\n" in value or "\r" in value:
                raise ReleaseError(f"Unsafe multiline GitHub output for {key}")
            output.write(f"{key}={value}\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repository root (defaults to the script's repository)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate one package")
    validate.add_argument("package")
    validate.add_argument("--release-ready", action="store_true")

    validate_all = subparsers.add_parser("validate-all", help="validate every package")
    validate_all.add_argument("--release-ready", action="store_true")

    metadata = subparsers.add_parser("metadata", help="emit validated package metadata")
    metadata.add_argument("package")
    metadata.add_argument("--release-ready", action="store_true")
    metadata.add_argument("--github-output", type=Path)

    notes = subparsers.add_parser("notes", help="write current-version changelog notes")
    notes.add_argument("package")
    notes.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        root = args.root.resolve()
        catalog = load_catalog(root)
        if args.command == "validate":
            metadata = validate_package(
                root, catalog, args.package, release_ready=args.release_ready
            )
            print(json.dumps(metadata.as_dict(), sort_keys=True))
        elif args.command == "validate-all":
            result = {
                package_id: validate_package(
                    root, catalog, package_id, release_ready=args.release_ready
                ).as_dict()
                for package_id in catalog.packages
            }
            print(json.dumps(result, indent=2, sort_keys=True))
        elif args.command == "metadata":
            metadata = validate_package(
                root, catalog, args.package, release_ready=args.release_ready
            )
            if args.github_output:
                _write_github_output(args.github_output, metadata)
            else:
                print(json.dumps(metadata.as_dict(), sort_keys=True))
        elif args.command == "notes":
            notes = release_notes(root, catalog, args.package)
            args.output.write_text(notes, encoding="utf-8")
        else:  # pragma: no cover - argparse prevents this branch.
            raise ReleaseError(f"Unsupported command: {args.command}")
    except ReleaseError as error:
        print(f"release metadata error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
