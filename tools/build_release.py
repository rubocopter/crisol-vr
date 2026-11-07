#!/usr/bin/env python3
"""Build and validate a UEVR-importable Crisol profile ZIP.

Run from any directory with: python tools/build_release.py
The profile itself is intentionally committed under profile/; files are placed at
archive root because UEVR Import Config expects config.txt at the ZIP root.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile"
DIST = ROOT / "dist"
NAME = "CRToiPrototype-Win64-Shipping.zip"

REQUIRED_FILES = {
    "config.txt",
    "cameras.txt",
    "cvars_data.txt",
    "cvars_standard.txt",
    "user_script.txt",
    "_interaction_profiles_oculus_touch_controller.json",
    "scripts/hands.lua",
    "scripts/crisol_sense.lua",
    "scripts/crisol_vr_ui.lua",
    "scripts/libs/crisol_hand_pose.lua",
    "scripts/libs/uevr_utils.lua",
    "scripts/libs/controllers.lua",
    "scripts/libs/hands.lua",
    "data/hands_parameters.json",
    "data/pawn_parameters.json",
    "data/crisol_weapon_tracking.json",
    "data/crisol_trigger_pose.json",
}
VALID_SUFFIXES = {".txt", ".json", ".lua"}


def build() -> tuple[Path, str, int]:
    files = sorted(
        (file for file in PROFILE.rglob("*") if file.is_file()),
        key=lambda file: file.relative_to(PROFILE).as_posix(),
    )
    names = {file.relative_to(PROFILE).as_posix() for file in files}
    missing = REQUIRED_FILES - names
    if missing:
        raise RuntimeError(f"Required UEVR profile files missing: {sorted(missing)}")

    for file in files:
        relative = file.relative_to(PROFILE)
        if file.suffix.lower() not in VALID_SUFFIXES:
            raise RuntimeError(f"Unexpected file type in profile: {relative}")
        content = file.read_bytes()
        if re.search(rb"C:[\\/]Users[\\/]Oni[\\/]", content, re.I):
            raise RuntimeError(f"Personal Windows path in public profile: {relative}")
        if file.suffix.lower() == ".json":
            json.loads(content.decode("utf-8-sig"))

    settings = dict(
        line.split("=", 1)
        for line in (PROFILE / "config.txt").read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    expected = {
        "VR_NativeStereoFix": "false",
        "VR_RenderingMethod": "0",
        "VR_AimMethod": "2",
        "VR_MovementOrientation": "1",
        "UI_FollowView": "true",
    }
    for key, value in expected.items():
        if settings.get(key) != value:
            raise RuntimeError(f"Unexpected {key}={settings.get(key)!r}, expected {value!r}")

    bindings = json.loads(
        (PROFILE / "_interaction_profiles_oculus_touch_controller.json").read_text(encoding="utf-8")
    )
    actions = {item["action"].lower() for item in bindings["bindings"]}
    if not {"pose", "trigger", "grip", "joystick"}.issubset(actions):
        raise RuntimeError("The controller binding profile lacks required tracked actions")

    DIST.mkdir(exist_ok=True)
    output = DIST / NAME
    notices = ["LICENSE", "UEVRLIB_LICENSE", "THIRD_PARTY_NOTICES.md"]
    archive_entries = [(file, file.relative_to(PROFILE).as_posix()) for file in files]
    archive_entries.extend((ROOT / notice, notice) for notice in notices)

    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for file, name in archive_entries:
            entry = ZipInfo(name, date_time=(2026, 11, 7, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, file.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)

    # Independently reopen and check actual archive contents and checksums.
    with ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC validation failed")
        stored = set(archive.namelist())
        if stored != {name for _, name in archive_entries}:
            raise RuntimeError("Unexpected files in the finished ZIP")
        for file, name in archive_entries:
            if archive.read(name) != file.read_bytes():
                raise RuntimeError(f"ZIP content differs from source: {name}")

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    (DIST / "SHA256SUMS.txt").write_text(f"{digest}  {NAME}\n", encoding="utf-8")
    return output, digest, len(files)


if __name__ == "__main__":
    path, checksum, file_count = build()
    print(f"Validated {file_count} profile files plus license notices")
    print(f"UEVR ZIP: {path} ({path.stat().st_size:,} bytes)")
    print(f"SHA256: {checksum}")
