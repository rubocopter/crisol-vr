-- Parent registers process once with uevr.sdk.callbacks.on_xinput_get_state.
-- Vive alone binds BOTH AButtonTouchLeft and BButtonTouchRight to the same
-- trackpad/click on each hand. These touch markers emit no Xbox buttons.
-- VR.hpp exposes these handles to Lua but NOT its internal TouchpadClick.
-- WMR has real thumbsticks and never binds the marker pair; Touch/Index map
-- these two touches to opposite hands, so neither can trigger this guard.
local M = {}
local diagnostic = nil

function M.start_diagnostics(polls, changes)
    diagnostic = {polls = math.min(math.max(polls or 600, 1), 600),
                  changes = math.min(math.max(changes or 40, 1), 40)}
end

function M.process(retval, user_index, state)
    local vr = uevr.params.vr
    if state == nil or not vr.is_runtime_ready() or not vr.is_openxr()
        or not vr.is_using_controllers()
        or user_index ~= vr.get_lowest_xinput_index() then return end

    -- Sources follow UEVR's controller swapping, just as its Xbox axes do.
    -- Resolve handles each time so an OpenXR session restart cannot stale them.
    local ok, left, right = pcall(function()
        local click = vr.get_action_handle('/actions/default/in/BButtonTouchRight')
        local marker = vr.get_action_handle('/actions/default/in/AButtonTouchLeft')
        if click == nil or marker == nil or click == 0 or marker == 0 then
            return false, false
        end
        local function sector_click(source)
            return vr.is_action_active(click, source) and vr.is_action_active(marker, source)
        end
        return sector_click(vr.get_left_joystick_source()),
               sector_click(vr.get_right_joystick_source())
    end)
    if not ok then return end
    local pad = state.Gamepad
    if left then pad.sThumbLX = 0; pad.sThumbLY = 0 end
    if right then pad.sThumbRX = 0; pad.sThumbRY = 0 end

    -- Native Sense Create uses this otherwise right-hand-only touch action on
    -- the PHYSICAL left hand. Core XR presets reserve it there, so Cross touch
    -- on the right and Vive pad markers cannot produce View accidentally.
    local create_ok, create = pcall(function()
        local handle = vr.get_action_handle('/actions/default/in/AButtonTouchRight')
        if handle == nil or handle == 0 then return false end
        local source = vr.get_left_joystick_source()
        if vr.get_mod_value and vr:get_mod_value('VR_SwapControllerInputs') == 'true' then
            source = vr.get_right_joystick_source()
        end
        return vr.is_action_active(handle, source)
    end)
    if create_ok and create then pad.wButtons = pad.wButtons | 0x0020 end

    -- Opt-in and capped by both polls and changes. No file writes, per-frame
    -- logging, or profile guesses. Inspect the active profile in UEVR's editor.
    if diagnostic then
        local value = string.format('buttons=%04x LT=%d RT=%d LX=%d LY=%d RX=%d RY=%d ViveClick=%s/%s',
            pad.wButtons, pad.bLeftTrigger, pad.bRightTrigger,
            pad.sThumbLX, pad.sThumbLY, pad.sThumbRX, pad.sThumbRY,
            tostring(left), tostring(right))
        if value ~= diagnostic.last then
            print('[Crisol input] ' .. value)
            diagnostic.last = value
            diagnostic.changes = diagnostic.changes - 1
        end
        diagnostic.polls = diagnostic.polls - 1
        if diagnostic.polls <= 0 or diagnostic.changes <= 0 then diagnostic = nil end
    end
end

return M
