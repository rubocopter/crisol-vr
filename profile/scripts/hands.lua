local uevrUtils = require('libs/uevr_utils')
local controllers = require('libs/controllers')
local hands = require('libs/hands')
local pose = require('libs/crisol_hand_pose')

hands.setAutoCreateHands(false)
local last_error = nil
local created_pawn, created_arms
local function hands_ready()
    -- The library's exists() accepts either hand; this profile needs both.
    return uevrUtils.getValid(hands.getHandComponent(0, 'Arms')) ~= nil
        and uevrUtils.getValid(hands.getHandComponent(1, 'Arms')) ~= nil
end
local function clear_hands()
    -- Release prop/effect attachments before destroying their hand parents.
    -- This also makes a failed setup retryable instead of leaving valid but
    -- unconfigured hand components behind forever.
    pcall(pose.reset)
    pcall(hands.destroyHands)
    created_pawn, created_arms = nil, nil
end
local function align_hand(hand)
    local mesh = hands.getHandComponent(hand, 'Arms')
    if mesh == nil then return end
    local prefix = hand == 0 and 'l_' or 'r_'
    local function bone_location(name)
        return mesh:GetBoneTransformByName(uevrUtils.fname_from_string(prefix .. name), 1).Translation
    end
    local wrist = bone_location('wrist_jnt')
    local middle = bone_location('middle_01_jnt')
    local dorsal = bone_location('wrist_up_jnt')
    local mathlib = uevrUtils.find_default_instance('Class /Script/Engine.KismetMathLibrary')
    local forward = uevrUtils.vector(middle.X-wrist.X, middle.Y-wrist.Y, middle.Z-wrist.Z)
    local up = uevrUtils.vector(dorsal.X-wrist.X, dorsal.Y-wrist.Y, dorsal.Z-wrist.Z)
    local rotation = mathlib:NegateRotator(mathlib:MakeRotFromXZ(forward, up))
    hands.setRotation(hand, 1, rotation.Pitch, 'Arms')
    hands.setRotation(hand, 2, rotation.Yaw, 'Arms')
    hands.setRotation(hand, 3, rotation.Roll, 'Arms')
    uevr.params.functions.log_info(string.format('[Crisol hands] Aligned hand %d: %.2f, %.2f, %.2f', hand, rotation.Pitch, rotation.Yaw, rotation.Roll))
end

uevrUtils.setInterval(1000, function()
    local ok, err = pcall(function()
        local pawn = uevr.api:get_local_pawn(0)
        local arms = uevrUtils.getValid(pawn) and uevrUtils.getValid(pawn.PlayerArms)
        if not arms then
            if created_pawn ~= nil or hands.exists() then clear_hands() end
            return
        end
        if hands.exists() and hands_ready() and created_pawn == pawn and created_arms == arms then return end
        if created_pawn ~= nil or hands.exists() then clear_hands() end
        if not controllers.controllerExists(0) then controllers.createController(0) end
        if not controllers.controllerExists(1) then controllers.createController(1) end
        if not controllers.controllerExists(0) or not controllers.controllerExists(1) then
            return
        end
        hands.createFromConfig('hands_parameters', 'Main', '')
        if hands.exists() then
            assert(hands_ready(), 'Unable to create both tracked hands')
            uevrUtils.set_component_relative_transform(hands.getHandComponent(0,'Arms'),{0,0,0},{0,0,0})
            uevrUtils.set_component_relative_transform(hands.getHandComponent(1,'Arms'),{0,0,0},{0,0,0})
            align_hand(0)
            uevrUtils.set_component_relative_transform(hands.getHandComponent(0,'Arms'),{0,0,0},{Pitch=0,Yaw=-20,Roll=0})
            pose.setup(pawn)
            created_pawn, created_arms = pawn, arms
            last_error = nil
            uevr.params.functions.log_info('[Crisol hands] Created wrist-cut hands from PlayerArms')
        end
    end)
    if not ok then
        clear_hands()
        if tostring(err) ~= last_error then
            last_error = tostring(err)
            uevr.params.functions.log_warn('[Crisol hands] ' .. last_error)
        end
    end
end)
