#!/usr/bin/env python3
"""Prepare an explicit SteamVR Sense binding from an exported native autosave.

Offline only. No HTTP, registry, driver, runtime or Steam configuration writes.
Activation remains an explicit SteamVR Binding UI operation. Python 3.10+.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


APP_KEY = "steam.app.1790930"
CONTROLLER = "playstation_vr2_sense"
ACTION_SET = "/actions/defaultopenxr"
INTERACTION_PROFILE = "/interaction_profiles/valve/index_controller"
TEMPLATE_NAME = "crisol_sense_openxr.json"
ACTION_TYPES = {
    "trigger": "boolean", "grip": "boolean", "joystickclick": "boolean",
    "systembutton": "boolean", "abuttonright": "boolean", "abuttonleft": "boolean",
    "bbuttonright": "boolean", "bbuttonleft": "boolean",
    "abuttontouchright": "boolean", "abuttontouchleft": "boolean",
    "bbuttontouchright": "boolean", "bbuttontouchleft": "boolean",
    "thumbresttouchleft": "boolean", "thumbresttouchright": "boolean",
    "joystick": "vector2", "pose": "pose", "grippose": "pose", "haptic": "vibration",
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def template_path() -> Path:
    # Source tree and the separate steamvr/ directory in the UEVR ZIP.
    beside = Path(__file__).resolve().with_name(TEMPLATE_NAME)
    return beside if beside.exists() else Path(__file__).resolve().parents[1] / "profile/steamvr" / TEMPLATE_NAME


def read_json(path: Path) -> dict:
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    data = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object)
    require(isinstance(data, dict), f"Expected JSON object: {path}")
    return data


def check_session(text: str) -> None:
    starts = list(re.finditer(r"CRToiPrototype-Win64-Shipping[^\r\n]*startup with PID=", text))
    require(bool(starts), "Expected Crisol xrclient log with startup marker")
    session = text[starts[-1].start():]
    require("vrclient type=VRApplication_OpenXRInstance" in session, "Latest Crisol run is not proven OpenXR")
    keys = re.findall(r"xrCreateSession: Creating session for ([^\s]+)", session)
    require(bool(keys) and keys[-1] == APP_KEY, f"Latest Crisol OpenXR session must be {APP_KEY}")


def validate_template(binding: dict) -> None:
    """Check the shipped native artifact without trusting its file name."""
    for field, value in (("app_key", APP_KEY), ("category", "openxr"),
                         ("controller_type", CONTROLLER), ("interaction_profile", INTERACTION_PROFILE)):
        require(binding.get(field) == value, f"Native template has wrong {field}")
    require(binding.get("options") == {}, "Native template must not enable controller/HMD emulation")
    require(set(binding.get("bindings", {})) == {ACTION_SET}, "Unexpected template action set")
    section = binding["bindings"][ACTION_SET]
    require(not section.get("chords") and not section.get("eyetracking"), "Unexpected template chord/eye bindings")
    expected = {}
    for side, trigger, grip, stick in (("left", "l2", "l1", "left_stick"),
                                       ("right", "r2", "r1", "right_stick")):
        for physical, channel, action in ((trigger, "click", "trigger"), (grip, "click", "grip"),
                                           (stick, "position", "joystick"), (stick, "click", "joystickclick")):
            expected[(f"/user/hand/{side}/input/{physical}", channel)] = action
    for side, physical, click, touch in (("right", "cross", "abuttonright", "abuttontouchright"),
                                        ("right", "circle", "abuttonleft", "abuttontouchleft"),
                                        ("left", "square", "bbuttonright", "bbuttontouchright"),
                                        ("left", "triangle", "bbuttonleft", "bbuttontouchleft")):
        expected[(f"/user/hand/{side}/input/{physical}", "click")] = click
        expected[(f"/user/hand/{side}/input/{physical}", "touch")] = touch
    expected[("/user/hand/right/input/options", "click")] = "systembutton"
    expected[("/user/hand/left/input/create", "click")] = "abuttontouchright"
    expected[("/user/hand/left/input/l2", "touch")] = "thumbresttouchleft"
    expected[("/user/hand/left/input/left_stick", "touch")] = "thumbresttouchright"
    seen = {}
    for source in section.get("sources", []):
        for channel, target in source["inputs"].items():
            pair = (source["path"], channel)
            require(pair in expected and pair not in seen, "Unknown/duplicate native physical input")
            require(source["mode"] == ("joystick" if channel == "position" else "button"),
                    "Expected direct button/joystick, never complex_button/single")
            require(target["output"] == f"{ACTION_SET}/in/{expected[pair]}", "Incorrect native output action")
            # No inherited click timing, toggles, chords or thresholds.
            require(source.get("parameters", {}) in ({}, {"haptic_amplitude": 0},
                    {"force_input": "click", "haptic_amplitude": 0}), "Unexpected button parameters")
            if source["path"].rsplit("/", 1)[-1] in {"l1", "r1", "l2", "r2"}:
                require("force_input" not in source.get("parameters", {}),
                        "Sony L1/R1/L2/R2 expose value, not hardware click; let SteamVR synthesize click")
            seen[pair] = target["output"]
    require(set(seen) == set(expected), "Native template is missing physical controls")
    for category, expected_pairs in (
        ("poses", {(f"/user/hand/{side}/pose/{pose}", f"{ACTION_SET}/in/{action}")
                   for side in ("left", "right") for pose, action in (("openxr_aim", "pose"), ("handgrip", "grippose"))}),
        ("haptics", {(f"/user/hand/{side}/output/haptic", f"{ACTION_SET}/out/haptic") for side in ("left", "right")}),
    ):
        entries = section.get(category, [])
        require(len(entries) == len(expected_pairs) and
                {(entry["path"], entry["output"]) for entry in entries} == expected_pairs,
                f"Missing/incorrect native {category}")


def prepare_binding(export: dict, actions: dict, xr_log: str) -> dict:
    """Validate same-app native export + getactions registry, return repaired copy."""
    check_session(xr_log)
    # Accept the actual loadbindingfromurl response as well as its exported file.
    if "binding_config" in export:
        require(export.get("success") is True and export.get("app_key") == APP_KEY,
                "Binding response is unsuccessful or belongs to a different app")
        inner = copy.deepcopy(export["binding_config"])
        require(isinstance(inner, dict), "Expected binding_config object")
        require(inner.get("app_key", APP_KEY) == APP_KEY, "Conflicting binding app_key")
        inner["app_key"] = APP_KEY
        export = inner
    for field, value in (("app_key", APP_KEY), ("category", "openxr"), ("controller_type", CONTROLLER)):
        require(export.get(field) == value, f"Export must have {field}={value}; do not rename a compatibility binding")
    require(isinstance(export.get("bindings"), dict) and ACTION_SET in export["bindings"],
            "Export has no UEVR defaultopenxr action set")
    require(set(export["bindings"]) == {ACTION_SET}, "Unexpected action sets: export the Sense hand binding only")
    require(not export.get("simulated_actions"), "Simulated actions require manual review")
    require(actions.get("category") == "openxr", "Action registry is not OpenXR")
    require(actions.get("app_key", APP_KEY) == APP_KEY, "Registry belongs to another app")
    require(CONTROLLER in actions.get("current_binding_url", {}), "Registry has no native Sense binding URL")
    require(INTERACTION_PROFILE in actions.get("interaction_profiles", []),
            "Running app does not accept the required Valve Index interaction profile")

    registry = {}
    sets = actions.get("action_sets")
    require(isinstance(sets, list), "Expected getactions.json action_sets array")
    for action_set in sets:
        for action in action_set.get("actions", []):
            name = action.get("name")
            require(isinstance(name, str) and name not in registry, "Missing/duplicate registered action")
            require(name.startswith(action_set["name"] + "/"), "Action is outside its registered set")
            registry[name] = action.get("type")

    result = read_json(template_path())
    validate_template(result)
    for name, kind in ACTION_TYPES.items():
        direction = "out" if kind == "vibration" else "in"
        path = f"{ACTION_SET}/{direction}/{name}"
        require(registry.get(path) == kind, f"Missing or incompatible registered action: {path} ({kind})")
    if "version" in actions:
        result["action_manifest_version"] = actions["version"]
    return result


def check_offline_path(path: Path) -> None:
    resolved = path.resolve()
    lowered = [part.casefold() for part in resolved.parts]
    # Steam/config and Documents/steamvr/input are active runtime storage.
    require(not any(lowered[i:i + 2] == ["steam", "config"] or
                    lowered[i:i + 2] == ["steamvr", "input"] for i in range(len(lowered) - 1)),
            "Output must be an offline export outside Steam/config and steamvr/input")
    for parent in (resolved.parent, *resolved.parents):
        require(not (parent / "steam.exe").exists() and not (parent / "vrserver.exe").exists(),
                "Output cannot be inside a Steam/SteamVR installation")


def write_offline(output: Path, data: dict, protected: tuple[Path, ...]) -> str:
    check_offline_path(output)
    require(output.resolve() not in {path.resolve() for path in protected},
            "Output must differ from the evidence files and shipped template")
    payload = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    old = output.read_bytes() if output.exists() else None
    if old == payload:
        return "unchanged"
    require(output.parent.is_dir(), "Output directory must already exist")
    if old is not None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = output.with_name(f"{output.name}.{stamp}.bak")
        with backup.open("xb") as handle:
            handle.write(old)
    pending = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=output.name + ".", suffix=".tmp", delete=False) as handle:
            pending = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        require((output.read_bytes() if output.exists() else None) == old, "Output changed during preparation; retry")
        os.replace(pending, output)
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)
    return "written"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", required=True, type=Path, help="Exported native Sense binding or loadbindingfromurl response")
    parser.add_argument("--actions", required=True, type=Path, help="getactions.json response for running Crisol")
    parser.add_argument("--xr-log", required=True, type=Path, help="Crisol xrclient log from the same run")
    parser.add_argument("--output", required=True, type=Path, help="Separate offline JSON; never Steam's config/autosave")
    parser.add_argument("--write", action="store_true", help="Write offline JSON after validation (default: preview)")
    args = parser.parse_args(argv)
    try:
        check_offline_path(args.output)
        protected = (args.binding, args.actions, args.xr_log, template_path())
        require(args.output.resolve() not in {p.resolve() for p in protected}, "Output must differ from evidence/template")
        data = prepare_binding(read_json(args.binding), read_json(args.actions), args.xr_log.read_text(encoding="utf-8-sig"))
        digest = hashlib.sha256((json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode()).hexdigest()
        status = write_offline(args.output, data, protected) if args.write else "preview; add --write to create offline JSON"
        print(f"{APP_KEY}: {CONTROLLER}, OpenXR; Options=direct click; {status}")
        print(f"Output: {args.output}\nSHA256: {digest}")
        print("Not activated. Select the prepared file explicitly in SteamVR; verify in headset.")
        return 0
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        print(f"Refused: {exc}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
