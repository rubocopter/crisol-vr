#!/usr/bin/env python3
"""Build and validate a UEVR-importable Crisol profile ZIP.

Run from any directory with: python tools/build_release.py
The profile itself is intentionally committed under profile/; files are placed at
archive root because UEVR Import Config expects config.txt at the ZIP root.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile"
DIST = ROOT / "dist"
NAME = "CRToiPrototype-Win64-Shipping.zip"

REQUIRED_FILES = {
    "config.txt",
    "VERSION.txt",
    "PSVR2_SENSE.txt",
    "steamvr/crisol_sense_openxr.json",
    "steamvr/README.txt",
    "cameras.txt",
    "cvars_data.txt",
    "cvars_standard.txt",
    "user_script.txt",
    "_interaction_profiles_oculus_touch_controller.json",
    "_interaction_profiles_valve_index_controller.json",
    "_interaction_profiles_htc_vive_controller.json",
    "_interaction_profiles_microsoft_motion_controller.json",
    "_interaction_profiles_khr_simple_controller.json",
    "scripts/hands.lua",
    "scripts/crisol_sense.lua",
    "scripts/libs/crisol_context.lua",
    "scripts/crisol_vr_ui.lua",
    "scripts/libs/crisol_hand_pose.lua",
    "scripts/libs/uevr_utils.lua",
    "scripts/libs/controllers.lua",
    "scripts/libs/crisol_controller_input.lua",
    "scripts/libs/hands.lua",
    "data/hands_parameters.json",
    "data/pawn_parameters.json",
    "data/crisol_weapon_tracking.json",
    "data/crisol_trigger_pose.json",
}
VALID_SUFFIXES = {".txt", ".json", ".lua"}
# UEVR 4ee5c6b6 OpenXR.hpp enumerates these five plus Oculus Go.
# Go is a limited controller and uses UEVR defaults; no override is shipped.
CONTROLLER_PROFILES = {
    "oculus_touch_controller": "joystick",
    "valve_index_controller": "joystick",
    "htc_vive_controller": "touchpad",
    "microsoft_motion_controller": "joystick",
    "khr_simple_controller": "simple",
}
# Preserve prior work in the shared tree. These names are not loaded by UEVR's
# supported-controller loop and MUST NOT be shipped as claimed hardware support.
DORMANT_PROFILES = {
    "bytedance_pico4_controller", "facebook_touch_controller_pro",
    "hp_mixed_reality_controller", "htc_vive_cosmos_controller",
    "meta_touch_controller_plus", "meta_touch_plus_controller",
    "meta_touch_pro_controller", "samsung_odyssey_controller",
    "meta_touch_controller_rift_cv1", "meta_touch_controller_quest_1_rift_s",
    "meta_touch_controller_quest_2", "bytedance_pico_neo3_controller",
    "bytedance_pico_ultra_controller_bd", "htc_vive_focus3_controller",
    "varjo_xr-4_controller", "khr_generic_controller",
}
RUNTIME_BINDINGS = {f"_interaction_profiles_{name}.json" for name in CONTROLLER_PROFILES}
DORMANT_BINDINGS = {f"_interaction_profiles_{name}.json" for name in DORMANT_PROFILES}
BOOLEAN_ACTIONS = {
    "trigger", "grip", "joystickclick", "touchpadclick", "systembutton",
    "abuttonleft", "abuttonright", "bbuttonleft", "bbuttonright",
    "abuttontouchleft", "abuttontouchright", "bbuttontouchleft", "bbuttontouchright",
    "thumbresttouchleft", "thumbresttouchright",
    "dpad_up", "dpad_down", "dpad_left", "dpad_right",
}
ACTION_TYPES = {action: "boolean" for action in BOOLEAN_ACTIONS}
ACTION_TYPES.update(pose="pose", grippose="pose", joystick="vector2",
                    touchpad="vector2", haptic="haptic")


def component_types(profile: str, side: str) -> dict[str, str]:
    """Allowed component paths for the five core OpenXR profiles.

    Scalar value/force components can drive boolean actions via OpenXR's
    scalar-to-boolean conversion (including Index's trackpad force).
    """
    components = {"input/aim/pose": "pose", "input/grip/pose": "pose",
                  "output/haptic": "haptic"}
    if profile == "khr_simple_controller":
        components.update({"input/select/click": "boolean", "input/menu/click": "boolean"})
        return components
    components["input/trigger/value"] = "boolean"
    components["input/squeeze/value" if profile in {"oculus_touch_controller", "valve_index_controller"}
               else "input/squeeze/click"] = "boolean"
    if profile != "htc_vive_controller":
        components.update({"input/thumbstick": "vector2", "input/thumbstick/click": "boolean"})
    if profile != "oculus_touch_controller":
        components["input/trackpad"] = "vector2"
        components["input/trackpad/touch"] = "boolean"
        components["input/trackpad/force" if profile == "valve_index_controller"
                   else "input/trackpad/click"] = "boolean"
    if profile != "valve_index_controller" and (profile != "oculus_touch_controller" or side == "left"):
        components["input/menu/click"] = "boolean"
    if profile in {"oculus_touch_controller", "valve_index_controller"}:
        buttons = ("x", "y") if profile == "oculus_touch_controller" and side == "left" else ("a", "b")
        for button in buttons:
            for kind in ("click", "touch"):
                components[f"input/{button}/{kind}"] = "boolean"
        components.update({"input/trigger/touch": "boolean", "input/thumbstick/touch": "boolean"})
    if profile == "oculus_touch_controller":
        components["input/thumbrest/touch"] = "boolean"
    return components


def validate_bindings() -> None:
    filenames = {path.name for path in PROFILE.glob("_interaction_profiles_*.json")}
    missing = RUNTIME_BINDINGS - filenames
    unexpected = filenames - RUNTIME_BINDINGS - DORMANT_BINDINGS
    if missing or unexpected:
        raise RuntimeError(f"Controller profile set: missing={sorted(missing)}, unexpected={sorted(unexpected)}")
    for profile, input_type in CONTROLLER_PROFILES.items():
        path = PROFILE / f"_interaction_profiles_{profile}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            validate_profile(profile, input_type, data)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise RuntimeError(f"Invalid controller profile {path.name}: {exc}") from exc


def validate_profile(profile: str, input_type: str, data: dict) -> None:
    def require(condition, reason):
        if not condition:
            raise ValueError(reason)

    require(isinstance(data, dict), "Expected profile object")
    bindings, associations = data["bindings"], data["vector2_associations"]
    require(isinstance(bindings, list) and isinstance(associations, list), "Expected binding/association lists")
    direct = {side: {} for side in ("left", "right")}
    effective = {side: set() for side in direct}
    for binding in bindings:
        action, component = binding["action"], binding["path"]
        require(isinstance(action, str) and action in ACTION_TYPES, "Unknown binding action")
        require(isinstance(component, str), "Expected component path string")
        match = re.fullmatch(r"/user/hand/(left|right)/(.+)", component)
        require(match is not None, "Invalid binding hand/path")
        side, suffix = match.groups()
        require(component_types(profile, side).get(suffix) == ACTION_TYPES[action], "Invalid component or action type")
        # UEVR stores only one path per action per hand; a second would silently
        # overwrite path_map even when its (path, action) pair is different.
        require(action not in direct[side], "Duplicate action on the same hand")
        direct[side][action] = component
        effective[side].add(action)

    seen = set()
    for association in associations:
        hand = association["path"]
        require(hand in {"/user/hand/left", "/user/hand/right"}, "Invalid association hand")
        side = hand.rsplit("/", 1)[1]
        activator, modifier = association["activator"], association["modifier"]
        require(isinstance(activator, str) and activator in BOOLEAN_ACTIONS, "Activator must be boolean")
        require(isinstance(modifier, str) and ACTION_TYPES.get(modifier) == "vector2", "Modifier must be vector2")
        require(activator in direct[side] and modifier in direct[side], "Association input not bound on this hand")
        require((side, activator) not in seen, "Duplicate/conflicting association activator")
        seen.add((side, activator))
        outputs = association["outputs"]
        require(isinstance(outputs, list) and outputs, "Expected nonempty association outputs")
        output_actions, vectors = set(), []
        for output in outputs:
            action, value = output["action"], output["value"]
            require(isinstance(action, str) and action in BOOLEAN_ACTIONS, "Output must be boolean")
            require(action not in output_actions and action != activator, "Duplicate or recursive output")
            require(isinstance(value, dict) and set(value) == {"x", "y"}, "Expected x/y vector")
            vector = (value["x"], value["y"])
            require(all(type(v) in (int, float) and math.isfinite(v) and -1 <= v <= 1 for v in vector),
                    "Sector coordinates must be finite numbers within [-1, 1]")
            # UEVR activates outputs within Euclidean distance < 0.7. Overlapping
            # disks cause multiple buttons from one click; reject those presets.
            require(all(math.dist(vector, old) >= 1.4 for old in vectors), "Overlapping sector outputs")
            vectors.append(vector)
            output_actions.add(action)
            effective[side].add(action)

    for side in direct:
        required = {"pose", "grippose", "trigger"}
        if input_type != "simple":
            required |= {"grip", "joystick", "joystickclick", "haptic"}
            required |= {"bbuttonright", "bbuttonleft"} if side == "left" else {"abuttonright", "abuttonleft"}
        require(not required - effective[side], f"Missing {side} gameplay actions: {sorted(required - effective[side])}")
        if input_type != "simple":
            axis = "trackpad" if input_type == "touchpad" else "thumbstick"
            require(direct[side].get("joystick") == f"/user/hand/{side}/input/{axis}",
                    f"Movement must use the {side} native {axis}")
        if side == "left":
            require("abuttontouchright" not in effective[side], "Left AButtonTouchRight is reserved for native Sense Create")
        if profile in {"oculus_touch_controller", "valve_index_controller"}:
            buttons = ("x", "y") if profile == "oculus_touch_controller" and side == "left" else ("a", "b")
            actions = ("bbuttonright", "bbuttonleft") if side == "left" else ("abuttonright", "abuttonleft")
            for button, action in zip(buttons, actions):
                require(direct[side].get(action) == f"/user/hand/{side}/input/{button}/click", "Incorrect Xbox face mapping")
        if profile == "htc_vive_controller":
            # Paired click marker is the helper's ONLY reason to suppress axes.
            click = f"/user/hand/{side}/input/trackpad/click"
            require(direct[side].get("touchpadclick") == direct[side].get("abuttontouchleft") == direct[side].get("bbuttontouchright") == click,
                    "Vive sector click requires its input-helper marker")
        else:
            require(not {"bbuttontouchright", "abuttontouchleft"} <= effective[side], "Vive marker pair reserved for trackpad locomotion")
    require(any("systembutton" in actions for actions in effective.values()), "Missing pause/View route")
    if profile == "oculus_touch_controller":
        require(direct["left"].get("systembutton") == "/user/hand/left/input/menu/click", "Missing Touch menu route")
        for side in direct:
            require(direct[side].get(f"thumbresttouch{side}") == f"/user/hand/{side}/input/thumbrest/touch",
                    "Touch D-pad modifiers must use the matching physical thumbrest")


def profile_files() -> list[Path]:
    return sorted(
        (file for file in PROFILE.rglob("*") if file.is_file() and file.name not in DORMANT_BINDINGS),
        key=lambda file: file.relative_to(PROFILE).as_posix(),
    )


def validate_native_sense() -> None:
    """SteamVR's native OpenXR format is separate from UEVR's five overrides."""
    spec = importlib.util.spec_from_file_location("native_sense_release", Path(__file__).with_name("install_sense_bindings.py"))
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    try:
        native.validate_template(native.read_json(PROFILE / "steamvr/crisol_sense_openxr.json"))
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        raise RuntimeError(f"Invalid native Sense SteamVR binding: {exc}") from exc


def build() -> tuple[Path, str, int]:
    files = profile_files()
    names = {file.relative_to(PROFILE).as_posix() for file in files}
    missing = REQUIRED_FILES - names
    if missing:
        raise RuntimeError(f"Required UEVR profile files missing: {sorted(missing)}")

    snapshot = {file: file.read_bytes() for file in files}
    for file in files:
        relative = file.relative_to(PROFILE)
        if file.suffix.lower() not in VALID_SUFFIXES:
            raise RuntimeError(f"Unexpected file type in profile: {relative}")
        content = snapshot[file]
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
        "VR_AimMethod": "1",
        "VR_AimModifyPlayerControlRotation": "false",
        "VR_AimUsePawnControlRotation": "false",
        "VR_MovementOrientation": "1",
        "UI_FollowView": "true",
    }
    for key, value in expected.items():
        if settings.get(key) != value:
            raise RuntimeError(f"Unexpected {key}={settings.get(key)!r}, expected {value!r}")

    validate_bindings()
    validate_native_sense()

    DIST.mkdir(exist_ok=True)
    output = DIST / NAME
    notices = ["LICENSE", "UEVRLIB_LICENSE", "THIRD_PARTY_NOTICES.md"]
    archive_entries = [(file, file.relative_to(PROFILE).as_posix()) for file in files]
    archive_entries.extend((ROOT / notice, notice) for notice in notices)

    archive_entries.sort(key=lambda entry: entry[1])
    for file, _ in archive_entries:
        if file not in snapshot:
            snapshot[file] = file.read_bytes()
    if len({name.casefold() for _, name in archive_entries}) != len(archive_entries):
        raise RuntimeError("Duplicate ZIP member names")
    pending = DIST / (NAME + ".tmp")
    with ZipFile(pending, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for file, name in archive_entries:
            entry = ZipInfo(name, date_time=(2026, 11, 7, 0, 0, 0))
            entry.create_system = 3
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, snapshot[file], compress_type=ZIP_DEFLATED, compresslevel=9)

    # Independently reopen and check actual archive contents and checksums.
    with ZipFile(pending) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC validation failed")
        stored = archive.namelist()
        if stored != [name for _, name in archive_entries]:
            raise RuntimeError("Unexpected files in the finished ZIP")
        for file, name in archive_entries:
            if archive.read(name) != snapshot[file]:
                raise RuntimeError(f"ZIP content differs from source: {name}")

    # Refuse to publish a mixed snapshot if another editor changes sources.
    if files != profile_files() or any(file.read_bytes() != content for file, content in snapshot.items()):
        raise RuntimeError("Sources changed during build; retry after integration is finished")
    pending.replace(output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    (DIST / "SHA256SUMS.txt").write_text(f"{digest}  {NAME}\n", encoding="utf-8")
    return output, digest, len(files)


if __name__ == "__main__":
    path, checksum, file_count = build()
    print(f"Validated {file_count} profile files plus license notices")
    print(f"UEVR ZIP: {path} ({path.stat().st_size:,} bytes)")
    print(f"SHA256: {checksum}")
