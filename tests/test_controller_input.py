from pathlib import Path

from lupa import LuaRuntime
import pytest


HELPER = Path(__file__).resolve().parents[1] / "profile/scripts/libs/crisol_controller_input.lua"


def runtime():
    assert HELPER.exists(), "Vive sector clicks still send movement/turn axes"
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute('''
        active = {}; logs = {}; ready = true; openxr = true; using = true
        uevr = {params = {vr = {
            is_runtime_ready = function() return ready end,
            is_openxr = function() return openxr end,
            is_using_controllers = function() return using end,
            get_lowest_xinput_index = function() return 0 end,
            get_left_joystick_source = function() return 10 end,
            get_right_joystick_source = function() return 20 end,
            -- VR.hpp::m_action_handles exposes only this fixed set, NOT
            -- TouchpadClick, despite OpenXR having that internal action.
            get_action_handle = function(name)
                local available = {
                    ['/actions/default/in/AButtonTouchLeft'] = true,
                    ['/actions/default/in/BButtonTouchRight'] = true,
                }
                return available[name] and name or 0
            end,
            is_action_active = function(action, hand) return active[action .. hand] == true end,
        }}}
        function set_active(action, hand, value)
            active['/actions/default/in/' .. action .. hand] = value
        end
        function state()
            return {Gamepad = {wButtons=4096, bLeftTrigger=12, bRightTrigger=34,
                sThumbLX=1000, sThumbLY=-2000, sThumbRX=-3000, sThumbRY=4000}}
        end
    ''')
    module = lua.execute(HELPER.read_text(encoding="utf-8"))
    return lua, module


@pytest.mark.parametrize("hand,cleared,kept", [(10, "L", "R"), (20, "R", "L")])
def test_vive_click_suppresses_only_clicked_hand(hand, cleared, kept):
    lua, module = runtime()
    lua.globals().set_active("BButtonTouchRight", hand, True)
    lua.globals().set_active("AButtonTouchLeft", hand, True)
    state = lua.globals().state()
    module.process(None, 0, state)
    assert state.Gamepad[f"sThumb{cleared}X"] == 0
    assert state.Gamepad[f"sThumb{cleared}Y"] == 0
    assert state.Gamepad[f"sThumb{kept}X"] != 0
    assert state.Gamepad.wButtons == 4096
    assert (state.Gamepad.bLeftTrigger, state.Gamepad.bRightTrigger) == (12, 34)
    lua.globals().set_active("BButtonTouchRight", hand, False)
    released = lua.globals().state()
    module.process(None, 0, released)
    assert released.Gamepad[f"sThumb{cleared}X"] != 0


def test_wmr_pad_click_preserves_real_thumbsticks():
    lua, module = runtime()
    lua.globals().set_active("TouchpadClick", 10, True)
    state = lua.globals().state()
    module.process(None, 0, state)
    assert (state.Gamepad.sThumbLX, state.Gamepad.sThumbLY) == (1000, -2000)


@pytest.mark.parametrize("flag", ["ready", "openxr", "using"])
def test_inactive_runtime_does_not_change_gamepad(flag):
    lua, module = runtime()
    lua.globals()[flag] = False
    lua.globals().set_active("BButtonTouchRight", 10, True)
    lua.globals().set_active("AButtonTouchLeft", 10, True)
    state = lua.globals().state()
    module.process(None, 0, state)
    assert state.Gamepad.sThumbLX == 1000


def test_other_gamepad_index_is_untouched():
    lua, module = runtime()
    lua.globals().set_active("BButtonTouchRight", 10, True)
    lua.globals().set_active("AButtonTouchLeft", 10, True)
    state = lua.globals().state()
    module.process(None, 1, state)
    assert state.Gamepad.sThumbLX == 1000


def test_touch_face_button_without_trackpad_click_preserves_sticks():
    lua, module = runtime()
    lua.globals().set_active("AButtonTouchLeft", 20, True)
    state = lua.globals().state()
    module.process(None, 0, state)
    assert (state.Gamepad.sThumbRX, state.Gamepad.sThumbRY) == (-3000, 4000)


def test_swapped_sources_follow_uevr_swapped_axes():
    lua, module = runtime()
    lua.execute('''
        uevr.params.vr.get_left_joystick_source = function() return 20 end
        uevr.params.vr.get_right_joystick_source = function() return 10 end
    ''')
    lua.globals().set_active("BButtonTouchRight", 20, True)
    lua.globals().set_active("AButtonTouchLeft", 20, True)
    state = lua.globals().state()
    module.process(None, 0, state)
    assert state.Gamepad.sThumbLX == 0
    assert state.Gamepad.sThumbRX == -3000


def test_unavailable_handle_does_not_change_axes():
    lua, module = runtime()
    lua.execute('uevr.params.vr.get_action_handle = function() return 0 end')
    state = lua.globals().state()
    module.process(None, 0, state)
    assert state.Gamepad.sThumbLX == 1000


def test_diagnostics_are_opt_in_deduplicated_and_bounded():
    lua, module = runtime()
    lua.execute('print = function(value) table.insert(logs, value) end')
    state = lua.globals().state()
    module.process(None, 0, state)
    assert len(lua.globals().logs) == 0
    module.start_diagnostics(3, 40)
    module.process(None, 0, state)
    module.process(None, 0, state)
    state.Gamepad.wButtons = 8192
    module.process(None, 0, state)
    state.Gamepad.wButtons = 16384
    module.process(None, 0, state)
    assert len(lua.globals().logs) == 2
    assert "buttons=1000" in lua.globals().logs[1]
    assert "buttons=2000" in lua.globals().logs[2]
