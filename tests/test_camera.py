"""Exercise the shipped camera policy without a game or a pawn."""
from pathlib import Path

from lupa import LuaRuntime

SCRIPT = Path(__file__).resolve().parents[1] / "profile/scripts/crisol_sense.lua"


def camera():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().script_root = SCRIPT.parent.as_posix()
    lua.execute("package.path=script_root..'/?.lua;'..package.path")
    lua.execute("""
        settings = {}; writes = 0; aim = 2; warnings = {}; pre_tick = nil
        uevr = {api={get_local_pawn=function() return nil end}, params = {vr = {
            set_mod_value = function(k, v) settings[k] = v; writes = writes + 1 end,
            get_mod_value = function(self, k) return settings[k] end,
            get_aim_method = function() return aim end,
            set_aim_method = function(v) aim = v; settings.VR_AimMethod = tostring(v); writes = writes + 1 end,
        }, functions = {
            log_info = function() end,
            log_warn = function(s) warnings[#warnings+1] = s end,
        }, sdk={callbacks={on_script_reset=function(fn) script_reset=fn end}}}, sdk = {callbacks = {
            on_pre_engine_tick = function(fn) pre_tick = fn end,
            on_post_engine_tick = function(fn) post_tick = fn end,
            on_xinput_get_state = function(fn) input_tick = fn end,
        }}}
        -- The old policy depends on this timer. Tests deliberately do not
        -- advance it: a menu frame must not wait a second for safe aiming.
        package.preload['libs/uevr_utils'] = function() return {
            setInterval = function() end,
            getValid = function(o) return o end,
            find_all_of = function() return {} end,
        } end
        package.preload['libs/crisol_controller_input'] = function() return {
            process = function() end,
        } end
        package.preload['libs/crisol_aim'] = function() return {
            set_enabled = function() end,
            get_ray = function() return nil end,
            apply_controller_rotation = function() return false end,
        } end
    """)
    lua.execute(SCRIPT.read_text(encoding="utf-8"))
    return lua


def test_menu_without_pawn_uses_head_camera_immediately():
    lua = camera()
    lua.execute("""
        assert(settings.VR_AimMethod == '1')
        assert(settings.VR_AimModifyPlayerControlRotation == 'false')
        assert(settings.VR_AimUsePawnControlRotation == 'false')
        assert(settings.UI_FollowView == 'true')
    """)


def test_inspection_restores_head_camera_on_next_frame():
    lua = camera()
    lua.execute("""
        aim = 2
        settings.VR_AimModifyPlayerControlRotation = 'true'
        settings.VR_AimUsePawnControlRotation = 'true'
        assert(pre_tick, 'Camera drift must be corrected before the next engine frame')
        pre_tick(nil, 1/90)
        assert(aim == 1)
        assert(settings.VR_AimModifyPlayerControlRotation == 'false')
        assert(settings.VR_AimUsePawnControlRotation == 'false')
    """)


def test_stable_camera_does_not_rewrite_settings_each_frame():
    lua = camera()
    lua.execute("""
        assert(pre_tick)
        pre_tick(nil, 1/90)
        local before = writes
        for i = 1, 180 do pre_tick(nil, 1/90) end
        assert(writes == before, 'Stable settings should not be written every frame')
    """)


def test_camera_recovers_after_transient_api_failure():
    lua = camera()
    lua.execute("""
        assert(pre_tick)
        local read = uevr.params.vr.get_aim_method
        uevr.params.vr.get_aim_method = function() error('runtime not ready') end
        pre_tick(nil, 1/90)
        pre_tick(nil, 1/90)
        assert(#warnings == 1)
        uevr.params.vr.get_aim_method = read
        aim = 2
        pre_tick(nil, 1/90)
        assert(aim == 1)
    """)
