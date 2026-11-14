-- Keep head camera in menus/inspection, and restore controller-driven game
-- traces outside them. A tracked gun mesh does not redirect Crisol's own
-- interaction/shooting logic when Head/HMD is forced for all gameplay.
local context = require('libs/crisol_context')
local policy = {
    VR_AimUsePawnControlRotation = 'false',
    VR_MovementOrientation = '1',
    UI_FollowView = 'true',
}
local last_error, context_error
local function apply_camera_policy(delta)
    local vr = uevr.params.vr
    local ok, mode = pcall(context.camera_mode, delta)
    if not ok then
        if tostring(mode) ~= context_error then
            context_error = tostring(mode)
            uevr.params.functions.log_warn('[Crisol camera context] ' .. context_error)
        end
        mode = 1
    end
    if vr.get_aim_method() ~= mode then vr.set_aim_method(mode) end
    local modify = mode == 2 and 'true' or 'false'
    if vr:get_mod_value('VR_AimModifyPlayerControlRotation') ~= modify then
        vr.set_mod_value('VR_AimModifyPlayerControlRotation', modify)
    end
    for key, value in pairs(policy) do
        if vr:get_mod_value(key) ~= value then vr.set_mod_value(key, value) end
    end
end
local function maintain_camera_policy(_, delta)
    local ok, err = pcall(apply_camera_policy, delta)
    if not ok and tostring(err) ~= last_error then
        last_error = tostring(err)
        uevr.params.functions.log_warn('[Crisol camera] ' .. last_error)
    end
end

-- UEVR's inactivity clock counts actions, not tracked controller movement.
uevr.params.vr.set_mod_value('VR_MotionControlsInactivityTimer', '86400.0')
uevr.params.vr.set_mod_value('VR_AimMethod', '1')
maintain_camera_policy()
uevr.sdk.callbacks.on_pre_engine_tick(maintain_camera_policy)
-- Interactions can start during the engine tick. Apply their safe camera
-- before stereo rendering instead of waiting for the next engine frame.
uevr.sdk.callbacks.on_post_engine_tick(function() maintain_camera_policy(nil, 0) end)
uevr.params.functions.log_info('[Crisol Sense] Head camera in UI; right-controller traces in gameplay')

-- Sector buttons on Vive must not also move/turn the player. Other controller
-- families retain their original axes; the helper checks a Vive-only marker.
local controller_input = require('libs/crisol_controller_input')
local input_error
uevr.sdk.callbacks.on_xinput_get_state(function(...)
    local ok, err = pcall(controller_input.process, ...)
    if not ok and tostring(err) ~= input_error then
        input_error = tostring(err)
        uevr.params.functions.log_warn('[Crisol input] ' .. input_error)
    end
end)
