-- Keep head camera in menus/inspection, and restore controller-driven game
-- traces outside them. A tracked gun mesh does not redirect Crisol's own
-- interaction/shooting logic when Head/HMD is forced for all gameplay.
local context = require('libs/crisol_context')
local aim = require('libs/crisol_aim')
local utils = require('libs/uevr_utils')
local callbacks = uevr.sdk.callbacks
local policy = {
    VR_AimUsePawnControlRotation = 'false',
    VR_MovementOrientation = '1',
    UI_FollowView = 'true',
}
local last_error, context_error
local view

local function angle_delta(a, b)
    return (a - b + 180) % 360 - 180
end

local function release_view()
    local old = view
    view = nil
    if not old or not utils.getValid(old.controller) then return end
    local current = old.controller:GetControlRotation()
    -- If a scripted camera already took ownership, keep its new rotation.
    if math.abs(angle_delta(current.Yaw, old.shot_yaw)) < 0.01 then
        old.controller:SetControlRotation(utils.rotator(old.pitch, old.yaw, old.roll))
    end
end

if callbacks.on_early_calculate_stereo_view_offset then
    -- UEVR uses this basis for the headset AND the tracked meshes. Set it
    -- before either calculation, so the HUD and gun remain in the same space.
    callbacks.on_early_calculate_stereo_view_offset(function(_, _, _, _, rotation)
        if view then rotation.x, rotation.y, rotation.z = view.pitch, view.yaw, view.roll end
    end)
end

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
    local pawn, controller, pitch, yaw, roll
    if mode == 2 and uevr.api then
        pawn = uevr.api:get_local_pawn(0)
        if callbacks.on_early_calculate_stereo_view_offset and uevr.api.get_player_controller then
            controller = uevr.api:get_player_controller(0)
            if utils.getValid(controller) and controller.GetControlRotation then
                local rotation = controller:GetControlRotation()
                pitch, yaw, roll = rotation.Pitch, rotation.Yaw, rotation.Roll
            end
        end
    end
    if view and (mode ~= 2 or view.pawn ~= pawn or view.controller ~= controller) then
        release_view()
    end
    aim.set_enabled(mode == 2)
    local applied, aimed = true, false
    if mode == 2 then applied, aimed = pcall(aim.apply_controller_rotation, pawn) end
    local render_mode = mode
    if applied and aimed and yaw then
        local shot_yaw = controller:GetControlRotation().Yaw
        if view then
            -- Keep native turn input since our last write and discard the
            -- absolute weapon angle that was put in ControlRotation.
            view.yaw = angle_delta(view.yaw + angle_delta(yaw, view.shot_yaw), 0)
            view.shot_yaw = shot_yaw
        else
            view = {controller=controller, pawn=pawn, pitch=pitch, yaw=yaw, roll=roll, shot_yaw=shot_yaw}
        end
        -- Game mode stops UEVR's stock controller aim from reorienting the
        -- tracking origin on top of the weapon rotation Crisol already uses.
        render_mode = 0
    else
        release_view()
    end
    if vr.get_aim_method() ~= render_mode then vr.set_aim_method(render_mode) end
    local modify = mode == 2 and (not applied or not aimed) and 'true' or 'false'
    if vr:get_mod_value('VR_AimModifyPlayerControlRotation') ~= modify then
        vr.set_mod_value('VR_AimModifyPlayerControlRotation', modify)
    end
    for key, value in pairs(policy) do
        if vr:get_mod_value(key) ~= value then vr.set_mod_value(key, value) end
    end
    if not applied then error(aimed, 0) end
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
callbacks.on_pre_engine_tick(maintain_camera_policy)
-- Interactions can start during the engine tick. Apply their safe camera
-- before stereo rendering instead of waiting for the next engine frame.
callbacks.on_post_engine_tick(function() maintain_camera_policy(nil, 0) end)
uevr.params.sdk.callbacks.on_script_reset(release_view)
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
