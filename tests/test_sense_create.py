"""Native Create uses a left-hand marker absent from the five XR presets."""
from pathlib import Path
import json

import pytest
from lupa import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("swapped", [False, True])
def test_native_create_sends_view_but_right_cross_touch_does_not(swapped):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("""
        active={}; swapped=false
        uevr={params={vr={
            is_runtime_ready=function() return true end,
            is_openxr=function() return true end,
            is_using_controllers=function() return true end,
            get_lowest_xinput_index=function() return 0 end,
            get_left_joystick_source=function() return swapped and 20 or 10 end,
            get_right_joystick_source=function() return swapped and 10 or 20 end,
            get_mod_value=function() return swapped and 'true' or 'false' end,
            get_action_handle=function(name) return name end,
            is_action_active=function(action,source) return active[action..source]==true end,
        }}}
        function pad() return {Gamepad={wButtons=4096,bLeftTrigger=0,bRightTrigger=0,
            sThumbLX=123,sThumbLY=456,sThumbRX=789,sThumbRY=321}} end
    """)
    lua.globals().swapped = swapped
    lua.globals().helper = lua.execute((ROOT / "profile/scripts/libs/crisol_controller_input.lua").read_text())
    lua.execute("""
        active['/actions/default/in/AButtonTouchRight20']=true
        local face=pad(); helper.process(nil,0,face)
        assert(face.Gamepad.wButtons==4096, 'Right Cross touch must not send View')
        active['/actions/default/in/AButtonTouchRight10']=true
        local create=pad(); helper.process(nil,0,create)
        assert(create.Gamepad.wButtons==4128, 'Native left Create marker must send Xbox View')
        assert(create.Gamepad.sThumbLX==123 and create.Gamepad.sThumbRX==789)
        active['/actions/default/in/AButtonTouchRight10']=false
        local release=pad(); helper.process(nil,0,release)
        assert(release.Gamepad.wButtons==4096)
    """)


def test_core_presets_do_not_emit_native_create_marker():
    for name in ("oculus_touch", "valve_index", "htc_vive", "microsoft_motion", "khr_simple"):
        data = json.loads((ROOT / f"profile/_interaction_profiles_{name}_controller.json").read_text())
        assert not any(b["path"].startswith("/user/hand/left/") and b["action"] == "abuttontouchright"
                       for b in data["bindings"]), name


def test_native_template_maps_create_direct_click_to_reserved_left_action():
    data = json.loads((ROOT / "profile/steamvr/crisol_sense_openxr.json").read_text())
    entries = [s for s in data["bindings"]["/actions/defaultopenxr"]["sources"]
               if s["path"] == "/user/hand/left/input/create"]
    assert len(entries) == 1
    assert entries[0]["mode"] == "button"
    assert entries[0]["inputs"]["click"]["output"] == "/actions/defaultopenxr/in/abuttontouchright"
