-- UI camera safety and gameplay tracing are different policies. In gameplay
-- Crisol still uses ControlRotation for interaction and shots; a tracked mesh
-- alone does not redirect those traces. Do not select head aim just because
-- the player is looking AT an interactable before pressing its action button.
local utils = require('libs/uevr_utils')
local M = {}
local cached_pawn, inspection_widgets
local elapsed = math.huge

local function valid(object) return utils.getValid(object) ~= nil end
local function call(object, name)
    if object and object[name] then return object[name](object) end
end

local function inspection_open(pawn, delta)
    if cached_pawn ~= pawn then
        cached_pawn, inspection_widgets, elapsed = pawn, {}, math.huge
    end
    elapsed = elapsed + math.max(tonumber(delta) or 0, 0)
    if elapsed >= 0.2 then
        elapsed, inspection_widgets = 0, {}
        for _, widget in ipairs(utils.find_all_of('Class /Script/UMG.UserWidget', false) or {}) do
            pcall(function()
                if valid(widget) then
                    local class = widget:get_full_name():match('^(%S+)') or ''
                    if (class:find('InspectionWBP', 1, true) or class:find('Inspection3DMenu', 1, true))
                        and widget:GetOwningPlayerPawn() == pawn then
                        inspection_widgets[#inspection_widgets+1] = widget
                    end
                end
            end)
        end
    end
    for _, widget in ipairs(inspection_widgets or {}) do
        local ok, visible = pcall(function()
            return valid(widget) and widget:IsVisible() and widget:IsInViewport()
        end)
        if ok and visible then return true end
    end
    return false
end

function M.camera_mode(delta)
    local pawn = uevr.api and uevr.api:get_local_pawn(0)
    if not valid(pawn) or not valid(pawn.PlayerArms) then
        cached_pawn, inspection_widgets, elapsed = nil, {}, math.huge
        return 1, 'menu/no player'
    end
    -- PlayerController.IsPaused is a native C++ method, not a reflected
    -- Blueprint call available through UEVR. Query the current world through
    -- GameplayStatics so controller-only menus also keep head tracking.
    local world = utils.get_world()
    if valid(world) then
        local statics = utils.find_default_instance('Class /Script/Engine.GameplayStatics')
        if valid(statics) and statics:IsGamePaused(world) then return 1, 'paused world' end
    end
    local state = call(pawn, 'GetPlayerState')
    -- Reflected ECRPlayerState: None=0, Absorb=1, Damage=2, Interacting=3,
    -- Block=4, Dead=5, Healing=6. None/Damage remain controller-aimed.
    if state == 1 or state == 3 or state == 4 or state == 5 or state == 6 then
        return 1, 'scripted interaction'
    end
    if call(pawn, 'GetIsCharacterOnCinematicMode') == true then return 1, 'cinematic' end
    if pawn.bIsTabMenu == true then return 1, 'tab menu' end
    local controller = uevr.api.get_player_controller and uevr.api:get_player_controller(0) or pawn.Controller
    if valid(controller) then
        if controller.bShowMouseCursor == true or controller.bIsTabMenu == true then
            return 1, 'UI/pause'
        end
        local manager = controller.PlayerCameraManager
        local view = valid(manager) and manager.ViewTarget
        local target = view and view.Target
        if valid(target) and target ~= pawn then return 1, 'scripted camera' end
    end
    if inspection_open(pawn, delta) then return 1, 'inspection UI' end
    if type(state) ~= 'number' then return 1, 'waiting for player state' end
    return 2, 'gameplay/controller traces'
end

return M
