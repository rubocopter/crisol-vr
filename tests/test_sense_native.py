"""Offline behavior only: never connect to SteamVR or change its configuration."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import shutil

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/install_sense_bindings.py"
TEMPLATE = ROOT / "profile/steamvr/crisol_sense_openxr.json"
APP = "steam.app.1790930"
SET = "/actions/defaultopenxr"


def load_tool():
    assert SCRIPT.exists(), "Native Sense offline installer is missing"
    spec = importlib.util.spec_from_file_location("sense_native", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def exports(tmp_path):
    # Structure read by SteamVR 2.19.2 controllerbindingui.js/getactions.json.
    # Names also occur in the actual Crisol OpenXR generated binding export.
    types = {
        "trigger": "boolean", "grip": "boolean", "joystickclick": "boolean",
        "systembutton": "boolean", "abuttonright": "boolean", "abuttonleft": "boolean",
        "bbuttonright": "boolean", "bbuttonleft": "boolean",
        "abuttontouchright": "boolean", "abuttontouchleft": "boolean",
        "bbuttontouchright": "boolean", "bbuttontouchleft": "boolean",
        "thumbresttouchleft": "boolean", "thumbresttouchright": "boolean",
        "joystick": "vector2", "pose": "pose", "grippose": "pose", "haptic": "vibration",
    }
    actions = {
        "category": "openxr", "version": 0,
        "interaction_profiles": ["/interaction_profiles/valve/index_controller"],
        "current_binding_url": {"playstation_vr2_sense": "file:///export/autosave.json"},
        "action_sets": [{"name": SET, "usage": "single", "actions": [
            {"name": f"{SET}/{'out' if kind == 'vibration' else 'in'}/{name}", "type": kind}
            for name, kind in types.items()
        ]}],
    }
    binding = {
        "app_key": APP, "category": "openxr", "controller_type": "playstation_vr2_sense",
        "interaction_profile": "/interaction_profiles/oculus/touch_controller",
        "name": "User autosave", "description": "original",
        "options": {"simulated_controller_type": "oculus_touch", "compatibility_mode": True},
        "bindings": {SET: {"sources": [{
            "path": "/user/hand/right/input/options", "mode": "complex_button",
            "inputs": {"single": {"output": SET + "/in/systembutton"}},
        }], "poses": [], "haptics": [], "chords": [], "eyetracking": []}},
    }
    log = tmp_path / "xrclient_CRToiPrototype-Win64-Shipping.txt"
    log.write_text("CRToiPrototype-Win64-Shipping 2.19.2 startup with PID=42\n"
                   "vrclient type=VRApplication_OpenXRInstance\n"
                   f"xrCreateSession: Creating session for {APP}\n", encoding="utf-8")
    return binding, actions, log


def source_map(binding):
    return {(s["path"], key): value["output"]
            for s in binding["bindings"][SET]["sources"] for key, value in s["inputs"].items()}


def test_repairs_native_controls_without_oculus_conversion(exports):
    tool = load_tool()
    binding, actions, log = exports
    original = copy.deepcopy(binding)
    result = tool.prepare_binding(binding, actions, log.read_text())
    assert binding == original  # preview must not alter the export
    assert result["controller_type"] == "playstation_vr2_sense"
    assert result["category"] == "openxr"
    assert result["app_key"] == APP
    assert result["interaction_profile"] == "/interaction_profiles/valve/index_controller"
    assert result["options"] == {}
    mapping = source_map(result)
    for physical, channel, action in [
        ("left/l1", "click", "grip"), ("right/r1", "click", "grip"),
        ("left/l2", "click", "trigger"), ("right/r2", "click", "trigger"),
        ("left/left_stick", "position", "joystick"),
        ("right/right_stick", "position", "joystick"),
        ("left/left_stick", "click", "joystickclick"),
        ("right/right_stick", "click", "joystickclick"),
        ("right/options", "click", "systembutton"),
        ("left/create", "click", "abuttontouchright"),
        ("right/cross", "click", "abuttonright"), ("right/circle", "click", "abuttonleft"),
        ("left/square", "click", "bbuttonright"), ("left/triangle", "click", "bbuttonleft"),
    ]:
        side, name = physical.split("/")
        assert mapping[(f"/user/hand/{side}/input/{name}", channel)] == f"{SET}/in/{action}"
    options = [s for s in result["bindings"][SET]["sources"] if s["path"].endswith("/options")]
    assert len(options) == 1 and options[0]["mode"] == "button"
    assert set(options[0]["inputs"]) == {"click"}
    assert all("_ps" not in s["path"]
               for s in result["bindings"][SET]["sources"])
    for side in ("left", "right"):
        poses = result["bindings"][SET]["poses"]
        assert {"path": f"/user/hand/{side}/pose/handgrip", "output": SET + "/in/grippose"} in poses
        assert {"path": f"/user/hand/{side}/pose/openxr_aim", "output": SET + "/in/pose"} in poses
        assert {"path": f"/user/hand/{side}/output/haptic", "output": SET + "/out/haptic"} in result["bindings"][SET]["haptics"]
    assert tool.prepare_binding(result, actions, log.read_text()) == result


@pytest.mark.parametrize("field,value", [
    ("app_key", "steam.app.123"), ("app_key", None),
    ("controller_type", "oculus_touch"), ("controller_type", "knuckles"),
    ("category", "steamvr_input"), ("category", "legacy"),
])
def test_wrong_export_fails_closed(exports, field, value):
    tool = load_tool()
    binding, actions, log = exports
    binding[field] = value
    with pytest.raises(ValueError):
        tool.prepare_binding(binding, actions, log.read_text())


@pytest.mark.parametrize("fault", ["missing", "wrong_type", "duplicate", "wrong_set", "wrong_direction",
                                         "wrong_api", "unsupported_profile", "no_sense", "wrong_app"])
def test_registry_must_prove_actions_and_supported_profile(exports, fault):
    tool = load_tool()
    binding, actions, log = exports
    entries = actions["action_sets"][0]["actions"]
    if fault == "missing":
        entries.pop(0)
    elif fault == "wrong_type":
        entries[0]["type"] = "vector2"
    elif fault == "duplicate":
        entries.append(copy.deepcopy(entries[0]))
    elif fault == "wrong_set":
        entries[0]["name"] = "/actions/other/in/trigger"
    elif fault == "wrong_direction":
        entries[0]["name"] = SET + "/out/trigger"
    elif fault == "wrong_api":
        actions["category"] = "legacy"
    elif fault == "unsupported_profile":
        actions["interaction_profiles"] = ["/interaction_profiles/oculus/touch_controller"]
    elif fault == "no_sense":
        actions["current_binding_url"] = {"oculus_touch": "file:///wrong.json"}
    else:
        actions["app_key"] = "steam.app.123"
    with pytest.raises(ValueError):
        tool.prepare_binding(binding, actions, log.read_text())


@pytest.mark.parametrize("tail", ["", "xrCreateSession: Creating session for steam.app.123\n",
                                       "CRToiPrototype-Win64-Shipping startup with PID=43\n"])
def test_only_latest_crisol_openxr_session_is_accepted(exports, tail):
    tool = load_tool()
    binding, actions, log = exports
    text = "" if not tail else log.read_text() + tail
    with pytest.raises(ValueError):
        tool.prepare_binding(binding, actions, text)


def test_cli_is_preview_first_and_backup_is_exact(exports, tmp_path):
    load_tool()
    binding, actions, log = exports
    export = tmp_path / "native-autosave.json"
    registry = tmp_path / "actions.json"
    output = tmp_path / "prepared.json"
    original = json.dumps(binding, indent=3).encode()
    export.write_bytes(original)
    registry.write_text(json.dumps(actions))
    args = [sys.executable, str(SCRIPT), "--binding", str(export), "--actions", str(registry),
            "--xr-log", str(log), "--output", str(output)]
    preview = subprocess.run(args, capture_output=True, text=True)
    assert preview.returncode == 0, preview.stderr
    assert not output.exists() and export.read_bytes() == original
    applied = subprocess.run(args + ["--write"], capture_output=True, text=True)
    assert applied.returncode == 0, applied.stderr
    assert output.exists() and export.read_bytes() == original
    # Replacing a previous output preserves exact bytes; another run is a no-op.
    output.write_bytes(original)
    subprocess.run(args + ["--write"], check=True, capture_output=True)
    backups = list(tmp_path.glob("prepared.json.*.bak"))
    assert len(backups) == 1 and backups[0].read_bytes() == original
    result = output.read_bytes()
    subprocess.run(args + ["--write"], check=True, capture_output=True)
    assert output.read_bytes() == result
    assert len(list(tmp_path.glob("prepared.json.*.bak"))) == 1


def test_cli_rejects_invalid_input_before_any_write(exports, tmp_path):
    load_tool()
    binding, actions, log = exports
    binding["app_key"] = "steam.app.123"
    export, registry, output = [tmp_path / name for name in ("export.json", "actions.json", "out.json")]
    export.write_text(json.dumps(binding))
    registry.write_text(json.dumps(actions))
    output.write_bytes(b"keep me")
    result = subprocess.run([sys.executable, str(SCRIPT), "--binding", str(export), "--actions", str(registry),
                             "--xr-log", str(log), "--output", str(output), "--write"], capture_output=True)
    assert result.returncode != 0
    assert output.read_bytes() == b"keep me" and not list(tmp_path.glob("*.bak"))


def test_cli_refuses_steam_config_even_if_caller_requests_write(exports, tmp_path):
    tool = load_tool()
    steam = tmp_path / "Steam"
    target = steam / "config/input/export.json"
    target.parent.mkdir(parents=True)
    with pytest.raises(ValueError):
        tool.check_offline_path(target)


def test_template_uses_only_actions_seen_in_actual_crisol_export(exports):
    tool = load_tool()
    binding, actions, log = exports
    result = tool.prepare_binding(binding, actions, log.read_text())
    template = json.loads(TEMPLATE.read_text())
    assert result["bindings"] == template["bindings"]
    assert "oculus" not in json.dumps(template).lower()


def test_value_only_sony_triggers_use_synthesized_click_not_nonexistent_hardware_click(exports):
    tool = load_tool()
    binding, actions, log = exports
    result = tool.prepare_binding(binding, actions, log.read_text())
    for source in result["bindings"][SET]["sources"]:
        if source["path"].rsplit("/", 1)[-1] in {"l1", "r1", "l2", "r2"}:
            assert "force_input" not in source.get("parameters", {})
    broken = copy.deepcopy(result)
    broken["bindings"][SET]["sources"][0].setdefault("parameters", {})["force_input"] = "click"
    with pytest.raises(ValueError):
        tool.validate_template(broken)


def test_loadbinding_response_is_accepted_without_fabricating_controller_type(exports):
    tool = load_tool()
    binding, actions, log = exports
    binding.pop("app_key")
    response = {"success": True, "app_key": APP, "uri": "file:///export/autosave.json", "binding_config": binding}
    assert tool.prepare_binding(response, actions, log.read_text())["app_key"] == APP
    response["binding_config"]["controller_type"] = "oculus_touch"
    with pytest.raises(ValueError):
        tool.prepare_binding(response, actions, log.read_text())


def test_duplicate_json_keys_are_rejected(tmp_path):
    tool = load_tool()
    path = tmp_path / "ambiguous.json"
    path.write_text('{"category":"openxr", "category":"legacy"}')
    with pytest.raises(ValueError):
        tool.read_json(path)


def test_release_rejects_compatibility_file_mislabeled_as_native(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("release_sense", ROOT / "tools/build_release.py")
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    native_dir = tmp_path / "steamvr"
    native_dir.mkdir()
    broken = json.loads(TEMPLATE.read_text())
    broken["controller_type"] = "oculus_touch"
    (native_dir / TEMPLATE.name).write_text(json.dumps(broken))
    monkeypatch.setattr(release, "PROFILE", tmp_path)
    assert hasattr(release, "validate_native_sense"), "Release must validate the separate native SteamVR artifact"
    with pytest.raises(RuntimeError):
        release.validate_native_sense()


@pytest.mark.skipif(not shutil.which("powershell.exe"), reason="Windows PowerShell target wrapper")
@pytest.mark.parametrize("wrong_app", [False, True])
@pytest.mark.parametrize("native_save", [False, True])
def test_powershell_testkit_needs_no_python_and_is_offline(exports, tmp_path, wrong_app, native_save):
    script = ROOT / "tools/Install-SenseBindings.ps1"
    assert script.exists(), "Fractal needs a self-contained PowerShell installer"
    binding, actions, log = exports
    if wrong_app:
        binding["app_key"] = "steam.app.123"
    export, registry, output = [tmp_path / name for name in ("export.json", "actions.json", "prepared.json")]
    export.write_text(json.dumps(binding))
    registry.write_text(json.dumps(actions))
    template = tmp_path / "native-template.json"
    saved = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    section = saved["bindings"][SET]
    if native_save:
        # SteamVR's Save Personal omits empty eyetracking and adds skeleton.
        # Its saved layout must prepare without restoring/changing any sources.
        section.pop("eyetracking", None)
        section["skeleton"] = []
        saved["alias_info"] = {}
        saved["simulated_actions"] = []
    else:
        section["eyetracking"] = []  # Also keep accepting the prior authoring form.
        section.pop("skeleton", None)
    template.write_text(json.dumps(saved), encoding="utf-8")
    args = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script),
            "-Binding", str(export), "-Actions", str(registry), "-XrLog", str(log), "-Output", str(output),
            "-Template", str(template)]
    preview = subprocess.run(args, capture_output=True, text=True)
    assert preview.returncode == (2 if wrong_app else 0), preview.stderr
    assert not output.exists()
    written = subprocess.run(args + ["-Write"], capture_output=True, text=True)
    assert written.returncode == (2 if wrong_app else 0), written.stderr
    if wrong_app:
        assert not output.exists()
    else:
        actual = json.loads(output.read_text(encoding="utf-8-sig"))
        expected = json.loads(template.read_text(encoding="utf-8"))
        assert actual["bindings"] == expected["bindings"]
        assert actual["controller_type"] == "playstation_vr2_sense"
        assert actual["interaction_profile"] == "/interaction_profiles/valve/index_controller"
        assert source_map(actual)[("/user/hand/right/input/options", "click")] == SET + "/in/systembutton"
        output.write_bytes(b"previous exact bytes")
        subprocess.run(args + ["-Write"], check=True, capture_output=True)
        backups = list(tmp_path.glob("prepared.json.*.bak"))
        assert len(backups) == 1 and backups[0].read_bytes() == b"previous exact bytes"
        subprocess.run(args + ["-Write"], check=True, capture_output=True)
        assert len(list(tmp_path.glob("prepared.json.*.bak"))) == 1
