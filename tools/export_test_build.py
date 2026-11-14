#!/usr/bin/env python3
"""Publish only the named Crisol build artifacts; never synchronize a workspace.

Build separately with build_release.py. This exporter does not install profiles,
connect to FRACTAL, create shares, or change Windows settings. Python 3.10+.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import uuid
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
ZIP_NAME = "CRToiPrototype-Win64-Shipping.zip"
TESTKIT_NAME = "Crisol-Fractal-Testkit.zip"
ARTIFACTS = (f"dist/{ZIP_NAME}", "dist/SHA256SUMS.txt", "profile/PRUEBA_OTRO_PC.txt")
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        return digest.hexdigest()


def checked_path(path: Path) -> Path:
    """Reject links/junctions rather than following them across boundaries."""
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Absolute path without traversal required: {path}")
    for part in (path, *path.parents):
        try:
            reparse = getattr(part.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        except FileNotFoundError:
            reparse = False
        if part.is_symlink() or reparse:
            raise ValueError(f"Links/junctions are not allowed: {part}")
    return path.resolve()


def validate_zip(path: Path | BytesIO, package: str = "profile") -> None:
    with ZipFile(path) as archive:
        entries = archive.infolist()
        if not entries or len(entries) > 512 or sum(e.file_size for e in entries) > MAX_ARTIFACT_BYTES:
            raise ValueError("ZIP exceeds bounded profile limits")
        seen = set()
        for entry in entries:
            name = entry.filename
            member = PurePosixPath(name)
            if (member.is_absolute() or ".." in member.parts or "\\" in name or ":" in name
                    or name.casefold() in seen or entry.is_dir()
                    or any(p.startswith(".") or p.casefold() in {"saves", "games", "game"} for p in member.parts)
                    or re.search(r"credential|password|secret|token|login|cookie", name, re.I)):
                raise ValueError(f"Unsafe ZIP member: {name}")
            seen.add(name.casefold())
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f"ZIP symlink: {name}")
            if package == "testkit":
                allowed = {
                    ZIP_NAME, "tools/Collect-FractalLogs.ps1", "tools/Install-SenseBindings.ps1",
                    "profile/steamvr/crisol_sense_openxr.json", "steamvr/crisol_sense_openxr.json",
                    "README.md", "README.txt", "LEEME.txt", "PRUEBA_OTRO_PC.txt",
                    "docs/CORSARIO_FRACTAL.md", "CORSARIO_FRACTAL.md",
                    "LICENSE", "UEVRLIB_LICENSE", "THIRD_PARTY_NOTICES.md",
                }
                if name not in allowed:
                    raise ValueError(f"Unexpected testkit member: {name}")
                continue
            if name not in {"LICENSE", "UEVRLIB_LICENSE", "THIRD_PARTY_NOTICES.md"}:
                if member.suffix.lower() not in {".txt", ".json", ".lua"}:
                    raise ValueError(f"Unexpected ZIP artifact: {name}")
                if len(member.parts) > 1 and member.parts[0] not in {"scripts", "data", "uobjecthook", "steamvr"}:
                    raise ValueError(f"Unexpected ZIP directory: {name}")
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC validation failed")
        if package == "testkit":
            if (ZIP_NAME.casefold() not in seen or "tools/collect-fractallogs.ps1" not in seen
                    or not seen.intersection({"profile/steamvr/crisol_sense_openxr.json", "steamvr/crisol_sense_openxr.json"})
                    or not seen.intersection({"readme.md", "readme.txt", "leeme.txt", "prueba_otro_pc.txt", "docs/corsario_fractal.md", "corsario_fractal.md"})):
                raise ValueError("Testkit lacks profile ZIP, collector, native binding or instructions")
            validate_zip(BytesIO(archive.read(ZIP_NAME)))
        elif "config.txt" not in seen:
            raise ValueError("ZIP is corrupt or lacks config.txt")


def export_build(workspace: Path, destination: Path, project: str = "Crisol", *,
                 package: str = "profile", checksum_name: str = "SHA256SUMS.txt") -> Path:
    """Commit a validated release directory, then atomically replace latest.json.

    The last manifest remains usable through copy/hash/source/commit failures.
    Older releases are retained. No recursive source selection is supported.
    """
    if (not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,47}", project)
            or project.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))}):
        raise ValueError("Use a stable project name such as Crisol (letters, digits, _ or -)")
    workspace, destination = checked_path(Path(workspace)), checked_path(Path(destination))
    if (destination == destination.parent or destination.name.casefold() != "builds"
            or destination.is_relative_to(workspace) or workspace.is_relative_to(destination)):
        raise ValueError("Destination must be a dedicated absolute Builds directory outside the workspace")
    project_dir = checked_path(destination / project)
    if package not in {"profile", "testkit"} or checksum_name not in {"SHA256SUMS.txt", "Crisol-Fractal-Testkit.sha256"}:
        raise ValueError("Only the explicitly named profile/testkit and checksum artifacts are supported")
    zip_name = ZIP_NAME if package == "profile" else TESTKIT_NAME
    selected = (f"dist/{zip_name}", f"dist/{checksum_name}", ARTIFACTS[2])
    sources = [checked_path(workspace / name) for name in selected]
    for source in sources:
        if not source.is_relative_to(workspace) or not source.is_file():
            raise ValueError(f"Missing or out-of-workspace artifact: {source}")
        if source.stat().st_size > MAX_ARTIFACT_BYTES:
            raise ValueError(f"Artifact too large: {source.name}")
    hashes = {p.name: sha256(p) for p in sources}
    lines = sources[1].read_text(encoding="utf-8-sig").splitlines()
    matches = []
    for line in lines:
        match = re.fullmatch(r"([a-fA-F0-9]{64}) [ *]([^/\\]+)", line)
        if not match:
            raise ValueError("Malformed SHA256 checksum file")
        if match[2] == zip_name:
            matches.append(match[1].lower())
    if matches != [hashes[zip_name]]:
        raise ValueError("SHA256SUMS.txt does not match the named ZIP; rebuild first")
    validate_zip(sources[0], package)

    project_dir.mkdir(parents=True, exist_ok=True)
    release_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ-") + uuid.uuid4().hex[:8]
    release = project_dir / release_name
    staging = Path(tempfile.mkdtemp(prefix=".pending-", dir=project_dir))
    pending_manifest = project_dir / (".pending-" + uuid.uuid4().hex + ".json")
    published = False
    try:
        files = {}
        for source in sources:
            target = staging / source.name
            shutil.copyfile(source, target)
            if sha256(target) != hashes[source.name]:
                raise ValueError(f"SHA256 copy validation failed: {source.name}")
            files[source.name] = {"sha256": hashes[source.name], "bytes": target.stat().st_size}
        # Includes the sidecar and instructions; a build worker may be editing.
        if any(checked_path(p) != p or sha256(p) != hashes[p.name] for p in sources):
            raise RuntimeError("Sources changed during export; retry after the builder finishes")
        manifest = {"schema_version": 1, "project": project, "package": package, "release": release_name,
                    "exported_utc": datetime.now(timezone.utc).isoformat(), "files": files}
        with pending_manifest.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staging, release)
        os.replace(pending_manifest, project_dir / "latest.json")
        published = True
        return project_dir / "latest.json"
    finally:
        # All cleanup targets are unique children created by this call.
        if staging.exists():
            shutil.rmtree(staging)
        pending_manifest.unlink(missing_ok=True)
        if not published and release.exists():
            shutil.rmtree(release)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=ROOT)
    parser.add_argument("--destination", type=Path, default=Path("E:/Builds"))
    parser.add_argument("--project", default="Crisol", help="Stable project directory, never a version")
    parser.add_argument("--package", choices=("profile", "testkit"), default="profile")
    parser.add_argument("--checksum-name", choices=("SHA256SUMS.txt", "Crisol-Fractal-Testkit.sha256"), default="SHA256SUMS.txt")
    args = parser.parse_args()
    try:
        latest = export_build(args.workspace, args.destination, args.project, package=args.package, checksum_name=args.checksum_name)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Export failed; previous latest retained: {exc}\n")
    print(f"Verified local export: {latest}")
    print(latest.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
