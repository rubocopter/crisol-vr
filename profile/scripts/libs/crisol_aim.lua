-- Use the gun's rendered barrel direction for both native gameplay traces
-- and the headlocked HUD. Samples are captured after UEVR moves the gun.
local utils = require('libs/uevr_utils')
local controllers = require('libs/controllers')
local M = {}
local mathlib = utils.find_default_instance('Class /Script/Engine.KismetMathLibrary')
local sample, enabled, shot_target
local trace_distance = 8192
local view_location = utils.vector(0, 0, 0)
local view_rotation = utils.rotator(0, 0, 0)

local function valid(object) return utils.getValid(object) ~= nil end
local function difference(a, b) return utils.vector(a.X-b.X, a.Y-b.Y, a.Z-b.Z) end

function M.set_sample(pawn, weapon, barrel, muzzle)
    if sample and (sample.pawn ~= pawn or sample.weapon ~= weapon) then shot_target = nil end
    sample = {pawn=pawn, weapon=weapon, barrel=utils.vector(barrel), muzzle=utils.vector(muzzle)}
end

function M.clear_sample()
    sample, shot_target = nil, nil
end

function M.set_enabled(active)
    enabled = active
    if not active then shot_target = nil end
end

local function has_sample(pawn)
    return enabled and sample and sample.pawn == pawn and valid(sample.weapon)
        and sample.weapon:IsVisible() and not sample.weapon.bHiddenInGame
end

function M.get_ray(pawn)
    if not has_sample(pawn) then return end
    local controller = controllers.getController(1,true)
    if not valid(controller) then return end
    local world = controller:K2_GetComponentToWorld()
    local barrel = mathlib:TransformLocation(world, sample.barrel)
    local muzzle = mathlib:TransformLocation(world, sample.muzzle)
    local vector = difference(muzzle, barrel)
    local length = math.sqrt(vector.X*vector.X+vector.Y*vector.Y+vector.Z*vector.Z)
    if length < 0.1 then return end
    return barrel, utils.vector(vector.X/length, vector.Y/length, vector.Z/length)
end

function M.get_target(pawn)
    if shot_target and has_sample(pawn) then return shot_target end
end

function M.apply_controller_rotation(pawn)
    shot_target = nil
    local barrel, direction = M.get_ray(pawn)
    if not barrel then return false end
    local player_controller = utils.get_player_controller()
    if not valid(player_controller) or not player_controller.SetControlRotation then return false end

    -- Crisol traces shots from its native view. Account for that origin when
    -- rotating it towards the target of the physically tracked muzzle.
    local target = utils.getTargetLocation(barrel, direction, 0, {pawn}, false, 10, trace_distance)
    if not target then
        target = utils.vector(barrel.X+direction.X*trace_distance,
            barrel.Y+direction.Y*trace_distance, barrel.Z+direction.Z*trace_distance)
    end
    player_controller:GetPlayerViewPoint(view_location,view_rotation)
    local offset = difference(target,view_location)
    local horizontal = math.sqrt(offset.X*offset.X+offset.Y*offset.Y)
    if horizontal < 0.01 and math.abs(offset.Z)<0.01 then return false end
    player_controller:SetControlRotation(utils.rotator(
        math.deg(math.atan(offset.Z,horizontal)),
        math.deg(math.atan(offset.Y,offset.X)),0))
    shot_target = target
    return true
end

return M
