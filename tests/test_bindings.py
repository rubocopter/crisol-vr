import importlib.util
import json
from pathlib import Path
import shutil
from zipfile import ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_bindings", ROOT / "tools/build_release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.fixture
def profile(tmp_path, monkeypatch):
    target = tmp_path / "profile"
    shutil.copytree(ROOT / "profile", target)
    monkeypatch.setattr(release, "PROFILE", target)
    return target


def edit(profile, name, change):
    path = profile / f"_interaction_profiles_{name}_controller.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_all_runtime_bindings_are_valid():
    release.validate_bindings()


@pytest.mark.parametrize("field,value", [
    ("activator", "nonexistent"), ("activator", "touchpad"),
    ("activator", "systembutton"),  # exists globally but not bound on right hand
    ("modifier", "nonexistent"), ("modifier", "trigger"),
    ("path", "/user/head"),
])
def test_rejects_unusable_association_inputs(profile, field, value):
    edit(profile, "htc_vive", lambda d: d["vector2_associations"][1].update({field: value}))
    with pytest.raises(RuntimeError):
        release.validate_bindings()


@pytest.mark.parametrize("value", [99, -2, True, "1", None, float("nan"), float("inf")])
def test_rejects_invalid_sector_coordinates(profile, value):
    edit(profile, "htc_vive", lambda d: d["vector2_associations"][0]["outputs"][0]["value"].update(x=value))
    with pytest.raises(RuntimeError):
        release.validate_bindings()


@pytest.mark.parametrize("action", ["nonexistent", "joystick", "pose", "haptic"])
def test_rejects_non_boolean_sector_output(profile, action):
    edit(profile, "htc_vive", lambda d: d["vector2_associations"][0]["outputs"][0].update(action=action))
    with pytest.raises(RuntimeError):
        release.validate_bindings()


@pytest.mark.parametrize("action,path", [
    ("nonexistent", "/user/hand/left/input/trigger/value"),
    ("joystick", "/user/hand/left/input/trigger/value"),
    ("trigger", "/user/hand/left/input/not_a_button/click"),
    ("trigger", "/user/hand/left/output/haptic"),
])
def test_rejects_invalid_direct_action_or_component(profile, action, path):
    edit(profile, "oculus_touch", lambda d: d["bindings"].append({"action": action, "path": path}))
    with pytest.raises(RuntimeError):
        release.validate_bindings()


def test_rejects_missing_pause_route(profile):
    edit(profile, "oculus_touch", lambda d: d.update(bindings=[b for b in d["bindings"] if b["action"] != "systembutton"]))
    with pytest.raises(RuntimeError):
        release.validate_bindings()


def test_rejects_native_create_marker_on_compatibility_controller(profile):
    edit(profile, "oculus_touch", lambda d: d["bindings"].append({
        "path": "/user/hand/left/input/x/touch", "action": "abuttontouchright"}))
    with pytest.raises(RuntimeError):
        release.validate_bindings()


def test_index_has_pause_without_reserved_system_button():
    data = json.loads((ROOT / "profile/_interaction_profiles_valve_index_controller.json").read_text())
    assert {"path": "/user/hand/left/input/trackpad/force", "action": "systembutton"} in data["bindings"]
    assert not any("/system/" in b["path"] for b in data["bindings"])


def test_rejects_touch_thumbrest_modifier_on_movement_stick(profile):
    def move_modifier(data):
        for binding in data["bindings"]:
            if binding["action"] == "thumbresttouchright":
                binding["path"] = "/user/hand/left/input/thumbstick/touch"
    edit(profile, "oculus_touch", move_modifier)
    with pytest.raises(RuntimeError):
        release.validate_bindings()


@pytest.mark.parametrize("name", ["valve_index", "microsoft_motion"])
def test_rejects_trackpad_replacing_a_real_movement_thumbstick(profile, name):
    def move_axis(data):
        for binding in data["bindings"]:
            if binding["action"] == "joystick" and "/left/" in binding["path"]:
                binding["path"] = "/user/hand/left/input/trackpad"
    edit(profile, name, move_axis)
    with pytest.raises(RuntimeError):
        release.validate_bindings()


def test_sense_physical_pairs_match_xbox_actions():
    data = json.loads((ROOT / "profile/_interaction_profiles_oculus_touch_controller.json").read_text())
    actual = {b["path"]: b["action"] for b in data["bindings"]}
    for component, action in [
        ("left/x", "bbuttonright"), ("left/y", "bbuttonleft"),
        ("right/a", "abuttonright"), ("right/b", "abuttonleft"),
        ("left/menu", "systembutton"),
    ]:
        side, button = component.split("/")
        assert actual[f"/user/hand/{side}/input/{button}/click"] == action


def test_only_vive_binds_the_click_marker_pair():
    for name in ("oculus_touch", "valve_index", "htc_vive", "microsoft_motion", "khr_simple"):
        data = json.loads((ROOT / f"profile/_interaction_profiles_{name}_controller.json").read_text())
        for side in ("left", "right"):
            mapping = {b["action"]: b["path"] for b in data["bindings"] if f"/hand/{side}/" in b["path"]}
            if name == "htc_vive":
                assert mapping["touchpadclick"] == mapping["abuttontouchleft"] == mapping["bbuttontouchright"] == f"/user/hand/{side}/input/trackpad/click"
            else:
                assert not {"bbuttontouchright", "abuttontouchleft"} <= mapping.keys()


def test_build_is_deterministic_and_excludes_dormant_templates(profile, tmp_path, monkeypatch):
    for notice in ("LICENSE", "UEVRLIB_LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copyfile(ROOT / notice, tmp_path / notice)
    monkeypatch.setattr(release, "ROOT", tmp_path)
    monkeypatch.setattr(release, "DIST", tmp_path / "output")
    path, digest, count = release.build()
    first = path.read_bytes()
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(set(archive.namelist())) == count + 3
        bindings = {n for n in archive.namelist() if n.startswith("_interaction_profiles_")}
        assert bindings == {f"_interaction_profiles_{name}_controller.json" for name in (
            "oculus_touch", "valve_index", "htc_vive", "microsoft_motion", "khr_simple")}
        for name in archive.namelist():
            source = tmp_path / name if name in {"LICENSE", "UEVRLIB_LICENSE", "THIRD_PARTY_NOTICES.md"} else profile / name
            assert archive.read(name) == source.read_bytes()
    assert release.build()[1] == digest
    assert path.read_bytes() == first
    # Templates are retained in the working tree, not installed as fake support.
    assert (profile / "_interaction_profiles_hp_mixed_reality_controller.json").exists()
