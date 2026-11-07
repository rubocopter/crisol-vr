-- Keep health/menus headlocked. Only the weapon reticle and interaction icons
-- get independent positioning. Native game visibility and interaction logic remain in charge.
local utils = require('libs/uevr_utils')
local controllers = require('libs/controllers')
local mathlib = utils.find_default_instance('Class /Script/Engine.KismetMathLibrary')
local layout = utils.find_default_instance('Class /Script/UMG.WidgetLayoutLibrary')
local crosshairs, components, active_icons, changed = {}, {}, {}, {}
local last_error, reported_projection = nil, false
local reported_errors = {}
local function report_error(message)
    message = tostring(message)
    if not reported_errors[message] then
        reported_errors[message] = true
        uevr.params.functions.log_warn('[Crisol VR UI] ' .. message)
    end
end
local viewport_h, dpi, ui_size, ui_distance, offset_x, offset_y = 1440, 1, 2.285, 3.045, 0, 0
local debug_time, debug_count = 0, 0
local viewport_w = 2560
local native_screen = utils.vector2D(0, 0)

local function number_param(name, default)
    return tonumber(uevr.params.vr:get_mod_value(name)) or default
end
local function copy3(v) return {X=v.X, Y=v.Y, Z=v.Z} end
local function valid(object) return utils.getValid(object) ~= nil end
local function dot(a, b) return a.X*b.X + a.Y*b.Y + a.Z*b.Z end
local function sub(a, b) return {X=a.X-b.X, Y=a.Y-b.Y, Z=a.Z-b.Z} end

-- Intersection of the right aim ray and the headlocked UEVR UI plane.
-- World coordinates are cm; the compositor settings are metres.
local function project_ray(origin, direction, head, forward, right, up, distance, size, height, scale, xoff, yoff)
    local delta = sub(origin, head)
    local denominator = dot(direction, forward)
    if denominator < 0.05 then return nil end
    local t = (distance*100 - dot(delta, forward)) / denominator
    if t <= 0 then return nil end
    local intersection = {X=delta.X+direction.X*t, Y=delta.Y+direction.Y*t, Z=delta.Z+direction.Z*t}
    local pixels_per_cm = height / scale / (size*100)
    return (dot(intersection, right)-xoff*100)*pixels_per_cm,
        -(dot(intersection, up)-yoff*100)*pixels_per_cm
end

local function restore()
    for _, widget in ipairs(crosshairs) do
        pcall(function() if valid(widget) then widget:SetRenderTranslation(utils.vector2D(0, 0)) end end)
    end
    for widget in pairs(changed) do
        pcall(function()
            if valid(widget) then widget:SetRenderTranslation(utils.vector2D(0, 0)) end
        end)
    end
    crosshairs, components, active_icons, changed = {}, {}, {}, {}
end

utils.setInterval(1500, function()
    local ok, err = pcall(function()
        local pawn = uevr.api:get_local_pawn(0)
        if pawn == nil or utils.getValid(pawn.PlayerArms) == nil then return end
        controllers.createController(1)
        controllers.createController(2)
        local size = layout:GetViewportSize(utils.get_world())
        viewport_h = math.max(1, size.Y)
        viewport_w = math.max(1, size.X)
        dpi = math.max(0.01, layout:GetViewportScale(utils.get_world()))
        ui_size = math.max(0.01, number_param('UI_Size', 2.285))
        ui_distance = math.max(0.01, number_param('UI_Distance', 3.045))
        offset_x, offset_y = number_param('UI_X_Offset', 0), number_param('UI_Y_Offset', 0)
        local found = {}
        for _, widget in ipairs(utils.find_all_instances('Class /Script/UMG.UserWidget', false) or {}) do
            pcall(function()
                local name = widget:get_full_name()
                local cls = name:match('^(%S+)') or ''
                if cls:find('Crosshair', 1, true) and name:find('/Engine/Transient', 1, true)
                    and widget:IsInViewport() and widget:GetOwningPlayerPawn() == pawn then
                    found[#found+1] = widget
                end
            end)
        end
        crosshairs = found
        components = {}
        for _, component in ipairs(utils.find_all_instances('Class /Script/UMG.WidgetComponent', false) or {}) do
            pcall(function()
                local widget = component:GetUserWidgetObject()
                if widget ~= nil and widget:get_full_name():match('^CRInteractIconSlot_C ')
                    and widget:GetOwningPlayerPawn() == pawn then
                    components[#components+1] = {component=component, widget=widget}
                end
            end)
        end
    end)
    if not ok and tostring(err) ~= last_error then
        last_error = tostring(err)
        uevr.params.functions.log_warn('[Crisol VR UI] Scan: ' .. last_error)
    end
end)

utils.setInterval(150, function()
    local next_icons = {}
    for _, entry in ipairs(components) do
        pcall(function()
            if valid(entry.component) and valid(entry.widget) and entry.widget:IsVisible()
                and entry.component:IsVisible() then next_icons[#next_icons+1] = entry end
        end)
    end
    active_icons = next_icons
end)

uevr.sdk.callbacks.on_post_engine_tick(function()
    local ok, err = pcall(function()
        if not controllers.controllerExists(2) or not controllers.controllerExists(1) then return end
        local head = controllers.getControllerLocation(2)
        local forward = controllers.getControllerDirection(2)
        local right = controllers.getControllerRightVector(2)
        local up = controllers.getControllerUpVector(2)
        local origin = controllers.getControllerLocation(1)
        local direction = controllers.getControllerDirection(1)
        if not head or not forward or not right or not up or not origin or not direction then return end
        local target = controllers.getControllerTargetLocation(1, 0, {uevr.api:get_local_pawn(0)}, false, 10)
        local aim_origin, aim_direction = origin, direction
        if target then
            local d = sub(target, head)
            local length = math.sqrt(dot(d, d))
            if length > 1 then aim_origin, aim_direction = head, {X=d.X/length, Y=d.Y/length, Z=d.Z/length} end
        end
        local x, y = project_ray(aim_origin, aim_direction, head, forward, right, up, ui_distance, ui_size, viewport_h, dpi, offset_x, offset_y)
        if os.clock() > debug_time and debug_count < 12 then
            debug_time, debug_count = os.clock() + 1, debug_count + 1
            uevr.params.functions.log_info(string.format('[Crisol UI position] x=%s y=%s head=%.1f,%.1f,%.1f hforward=%.3f,%.3f,%.3f right=%.1f,%.1f,%.1f rforward=%.3f,%.3f,%.3f h=%s dpi=%s', tostring(x), tostring(y), head.X, head.Y, head.Z, forward.X, forward.Y, forward.Z, origin.X, origin.Y, origin.Z, direction.X, direction.Y, direction.Z, tostring(viewport_h), tostring(dpi)))
        end
        for _, widget in ipairs(crosshairs) do
            local good, message = pcall(function()
                if valid(widget) then
                    -- Hide an offscreen/behind-head aim by placing it outside the quad.
                    widget:SetRenderTranslation(utils.vector2D(x or viewport_h*10, y or viewport_h*10))
                end
            end)
            if not good then report_error(message) end
        end
        if x and #crosshairs > 0 and not reported_projection then
            reported_projection = true
            uevr.params.functions.log_info('[Crisol VR UI] Right-controller crosshair projection active')
        end
        for _, entry in ipairs(active_icons) do
            local good, message = pcall(function()
                local component, widget = entry.component, entry.widget
                if not valid(component) or not valid(widget) then return end
                local location = component:K2_GetComponentLocation()
                local delta = sub(location, head)
                local distance = math.sqrt(dot(delta, delta))
                if distance < 1 then return end
                local dir = {X=delta.X/distance, Y=delta.Y/distance, Z=delta.Z/distance}
                local ix, iy = project_ray(head, dir, head, forward, right, up, ui_distance, ui_size, viewport_h, dpi, offset_x, offset_y)
                local projected = layout:ProjectWorldLocationToWidgetPosition(utils.get_player_controller(), location, native_screen, false)
                if projected and ix then
                    widget:SetRenderTranslation(utils.vector2D(viewport_w/(2*dpi)+ix-native_screen.X, viewport_h/(2*dpi)+iy-native_screen.Y))
                    if not changed[widget] then
                        uevr.params.functions.log_info('[Crisol VR UI] Reprojected interaction icon: ' .. component:get_full_name())
                    end
                    changed[widget] = true
                elseif changed[widget] then
                    widget:SetRenderTranslation(utils.vector2D(0, 0))
                end
            end)
            if not good then report_error(message) end
        end
    end)
    if not ok and tostring(err) ~= last_error then
        last_error = tostring(err)
        uevr.params.functions.log_warn('[Crisol VR UI] Tick: ' .. last_error)
    end
end)

uevr.params.sdk.callbacks.on_script_reset(restore)
utils.registerPreLevelChangeCallback(function() restore(); reported_projection = false end)

return {project_ray=project_ray}
