"""Run the real UI discovery and projection callbacks with engine doubles."""
from pathlib import Path

from lupa import LuaRuntime

SCRIPT = Path(__file__).resolve().parents[1] / "profile/scripts/crisol_vr_ui.lua"


def ui():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("""
        intervals = {}; widgets = {}; icon_components = {}; warnings = {}
        pawn = {PlayerArms = {}}; global_scans = 0; cached_scans = 0; traces = 0
        aim_method=1; hand_direction={X=1,Y=0,Z=0}
        view_origin = {X=0,Y=0,Z=0}; view_rotation = {Pitch=0,Yaw=0,Roll=0}
        player_controller = {
            GetPlayerViewPoint = function(self, origin, rotation)
                origin.X=view_origin.X; origin.Y=view_origin.Y; origin.Z=view_origin.Z
                rotation.Pitch=view_rotation.Pitch; rotation.Yaw=view_rotation.Yaw; rotation.Roll=view_rotation.Roll
            end,
        }
        layout = {
            GetViewportSize = function() return {X=2560,Y=1440} end,
            GetViewportScale = function() return 1 end,
            ProjectWorldLocationToWidgetPosition = function(self, pc, loc, out)
                out.X=1280; out.Y=720; return true
            end,
        }
        utils = {
            find_default_instance = function() return layout end,
            getValid = function(o) if o and not o.invalid then return o end end,
            vector2D = function(x,y) return {X=x,Y=y} end,
            vector = function(x,y,z) return {X=x or 0,Y=y or 0,Z=z or 0} end,
            rotator = function() return {Pitch=0,Yaw=0,Roll=0} end,
            getForwardVector = function(rotation)
                local pitch, yaw = math.rad(rotation.Pitch), math.rad(rotation.Yaw)
                return {X=math.cos(pitch)*math.cos(yaw),Y=math.cos(pitch)*math.sin(yaw),Z=math.sin(pitch)}
            end,
            getTargetLocation = function(origin, direction)
                traces=traces+1; trace_origin=origin; trace_direction=direction
                return trace_target
            end,
            get_world = function() return {} end,
            get_player_controller = function() return player_controller end,
            setInterval = function(ms, fn) intervals[ms] = fn end,
            registerPreLevelChangeCallback = function(fn) level_reset = fn end,
        }
        local function query(class)
            if class == 'Class /Script/UMG.UserWidget' then return widgets end
            if class == 'Class /Script/UMG.WidgetComponent' then return icon_components end
            error('Unexpected UI class: '..class)
        end
        utils.find_all_instances = function(class) global_scans=global_scans+1; return query(class) end
        utils.find_all_of = function(class) cached_scans=cached_scans+1; return query(class) end
        controllers = {
            controllerExists = function() return true end,
            createController = function() end,
            getControllerLocation = function(id) return {X=0,Y=0,Z=0} end,
            getControllerDirection = function(id)
                if id==1 then return hand_direction end
                return {X=1,Y=0,Z=0}
            end,
            getControllerRightVector = function(id) return {X=0,Y=1,Z=0} end,
            getControllerUpVector = function(id) return {X=0,Y=0,Z=1} end,
            getControllerTargetLocation = function() traces=traces+1; return nil end,
        }
        uevr = {
            api = {get_local_pawn = function() return pawn end},
            params = {
                vr = {get_mod_value = function() return nil end,
                    get_aim_method=function() return aim_method end},
                sdk = {callbacks = {on_script_reset = function(fn) script_reset = fn end}},
                functions = {log_info = function() end, log_warn = function(s) warnings[#warnings+1]=s end},
            },
            sdk = {callbacks = {on_post_engine_tick = function(fn) tick = fn end}},
        }
        package.preload['libs/uevr_utils'] = function() return utils end
        package.preload['libs/controllers'] = function() return controllers end
        package.preload['libs/crisol_aim'] = function()
            return {get_target=function() return applied_shot_target end}
        end
        function new_widget(label, x, y)
            return {
                visible=true, in_viewport=true, owner=pawn,
                RenderTransform={Translation={X=x or 0,Y=y or 0}},
                get_full_name=function() return label end,
                IsInViewport=function(self) return self.in_viewport end,
                GetOwningPlayerPawn=function(self) return self.owner end,
                IsVisible=function(self) return self.visible end,
                SetRenderTranslation=function(self, v) self.translation={X=v.X,Y=v.Y}; self.updates=(self.updates or 0)+1 end,
            }
        end
        function new_icon(widget)
            return {
                GetUserWidgetObject=function() return widget end,
                IsVisible=function() return true end,
                K2_GetComponentLocation=function() return {X=100,Y=10,Z=0} end,
                get_full_name=function() return 'WidgetComponent test' end,
            }
        end
        function scan()
            local ms=0
            for period in pairs(intervals) do if period>ms then ms=period end end
            assert(ms<=1500, 'Discovery should run promptly')
            intervals[ms]()
            if intervals[150] then intervals[150]() end
        end
    """)
    lua.globals().module = lua.execute(SCRIPT.read_text(encoding="utf-8"))
    return lua


def test_new_hud_is_projected_on_next_discovery_poll():
    lua = ui()
    lua.execute("""
        scan()
        local crosshair = new_widget('CRCrosshair_C /Engine/Transient.Test')
        local icon = new_widget('CRInteractIconSlot_C /Engine/Transient.Icon')
        widgets={crosshair}; icon_components={new_icon(icon)}
        scan(); tick(nil, 1/90)
        assert(crosshair.translation, 'A new reticle must not wait 12 seconds')
        assert(icon.translation, 'A new interaction icon must not wait for a slow global scan')
        assert(#warnings==0)
    """)


def test_discovery_uses_class_index_instead_of_global_object_enumeration():
    lua = ui()
    lua.execute("scan(); assert(global_scans==0); assert(cached_scans>0)")


def test_destroyed_hud_is_replaced_on_next_poll():
    lua = ui()
    lua.execute("""
        local old = new_widget('CRCrosshair_C /Engine/Transient.Old')
        widgets={old}; scan(); tick(nil, 1/90)
        old.invalid=true
        local replacement=new_widget('CRCrosshair_C /Engine/Transient.New')
        widgets={replacement}; scan(); tick(nil, 1/90)
        assert(replacement.translation)
        assert(#warnings==0)
    """)


def test_restores_authored_translation_on_pawn_change():
    lua = ui()
    lua.execute("""
        local widget = new_widget('CRCrosshair_C /Engine/Transient.Authored', 13, -7)
        widgets={widget}; scan(); tick(nil, 1/90)
        pawn=nil; scan()
        assert(widget.translation.X==13 and widget.translation.Y==-7)
        local before=widget.updates
        tick(nil, 1/90)
        assert(widget.updates==before)
    """)


def test_inactive_ui_does_not_trace_weapon():
    lua = ui()
    lua.execute("""
        local hidden=new_widget('CRCrosshair_C /Engine/Transient.Hidden')
        hidden.visible=false; widgets={hidden}; scan(); tick(nil, 1/90)
        assert(traces==0)
    """)


def test_pawn_loss_stops_old_hud_updates_before_next_discovery_poll():
    lua = ui()
    lua.execute("""
        local widget = new_widget('CRCrosshair_C /Engine/Transient.Old', 9, 4)
        widgets={widget}; scan(); tick(nil, 1/90)
        pawn=nil; tick(nil, 1/90)
        assert(widget.translation.X==9 and widget.translation.Y==4)
        local before=widget.updates
        tick(nil, 1/90); assert(widget.updates==before)
    """)


def test_projection_preserves_geometry_and_rejects_behind_head():
    lua = ui()
    lua.execute("""
        local origin={X=0,Y=0,Z=0}
        local forward={X=1,Y=0,Z=0}; local right={X=0,Y=1,Z=0}; local up={X=0,Y=0,Z=1}
        local x,y=module.project_ray(origin,{X=1,Y=0.1,Z=0.2},origin,forward,right,up,3,2,1000,1,0,0)
        assert(math.abs(x-150)<0.001 and math.abs(y+300)<0.001)
        assert(module.project_ray(origin,{X=-1,Y=0,Z=0},origin,forward,right,up,3,2,1000,1,0,0)==nil)
    """)


def test_reticle_uses_native_view_ray_instead_of_lower_right_controller_ray():
    lua = ui()
    lua.execute("""
        -- The native camera is behind the tracked head (including UEVR's
        -- forward camera offset); the controller is right and below it.
        view_origin={X=0,Y=0,Z=0}
        controllers.getControllerLocation=function(id)
            if id==1 then return {X=45,Y=25,Z=-35} end
            return {X=3.001444,Y=0,Z=0}
        end
        local crosshair=new_widget('CRCrosshair_C /Engine/Transient.NativeAim')
        widgets={crosshair}; scan(); tick(nil, 1/90)
        assert(crosshair.translation, table.concat(warnings, '\\n'))
        assert(math.abs(crosshair.translation.X)<0.001 and math.abs(crosshair.translation.Y)<0.001,
            'A lower-right hand must not displace a centered native shot down-right')
        assert(trace_origin and trace_origin.X==0 and trace_origin.Y==0 and trace_origin.Z==0,
            'Collision targeting must start at the native game viewpoint')
    """)


def test_projection_matches_uevr_quad_height_with_dpi_and_ui_offsets():
    lua = ui()
    lua.execute("""
        -- UEVR OpenXR generate_slate_quad: height=UI_Size; width=aspect*height.
        -- For a 2560x1440 texture, a 2m-high quad is 32/9m wide. A point
        -- 0.5m right, 0.25m up lands at (1640,540) texture pixels before DPI.
        local head={X=0,Y=0,Z=0}
        local x,y=module.project_ray(head,{X=3,Y=0.5,Z=0.25},head,
            {X=1,Y=0,Z=0},{X=0,Y=1,Z=0},{X=0,Y=0,Z=1},3,2,1440,1.5,0.1,-0.05)
        assert(math.abs(x-192)<0.001 and math.abs(y+144)<0.001,
            'UI_Size is compositor height, scaled to widget units with DPI')
    """)


def test_reticle_tracks_effective_native_rotation_and_hit_parallax_each_tick():
    lua = ui()
    lua.execute("""
        local crosshair=new_widget('CRCrosshair_C /Engine/Transient.SmoothedAim')
        widgets={crosshair}; scan()
        -- UEVR AimInterp means the effective native rotation can lag behind
        -- raw tracking. Keep raw tracking centered while native aim changes.
        view_origin={X=0,Y=4,Z=8}
        view_rotation={Pitch=5,Yaw=-7,Roll=0}
        trace_target={X=1000,Y=-120,Z=90}
        tick(nil, 1/90)
        assert(trace_direction, table.concat(warnings, '\\n'))
        assert(math.abs(trace_direction.Y-math.cos(math.rad(5))*math.sin(math.rad(-7)))<0.000001)
        assert(math.abs(trace_direction.Z-math.sin(math.rad(5)))<0.000001)
        local pixels_per_cm=1440/(2.285*100)
        assert(math.abs(crosshair.translation.X-(-120/1000*304.5*pixels_per_cm))<0.001)
        assert(math.abs(crosshair.translation.Y-(-90/1000*304.5*pixels_per_cm))<0.001)
        -- No collision: project the current native ray, not a cached hit or
        -- the controller's unchanged rotation.
        trace_target=nil; view_rotation={Pitch=-4,Yaw=6,Roll=0}
        tick(nil, 1/90)
        assert(math.abs(trace_direction.Z-math.sin(math.rad(-4)))<0.000001)
        local t=304.5/trace_direction.X
        assert(math.abs(crosshair.translation.X-(4+trace_direction.Y*t)*pixels_per_cm)<0.001)
        assert(math.abs(crosshair.translation.Y+(8+trace_direction.Z*t)*pixels_per_cm)<0.001)
    """)


def test_reticle_projects_the_applied_shot_target_without_retracing():
    lua = ui()
    lua.execute("""
        local crosshair=new_widget('CRCrosshair_C /Engine/Transient.GunRay')
        widgets={crosshair}; scan()
        applied_shot_target={X=500,Y=100,Z=0}
        trace_target={X=20,Y=-100,Z=0}
        tick(nil,1/90)
        local first=crosshair.translation.X
        assert(first>0)
        applied_shot_target={X=8192,Y=-2000,Z=0}
        tick(nil,1/90)
        assert(crosshair.translation.X<0 and crosshair.translation.X<first)
        assert(traces==0)
        assert(#warnings==0)
    """)


def test_reticle_follows_right_controller_before_first_stereo_gun_sample():
    lua = ui()
    lua.execute("""
        local crosshair=new_widget('CRCrosshair_C /Engine/Transient.HandFallback')
        widgets={crosshair}; scan()
        aim_method=2; trace_target=nil
        tick(nil,1/90)
        assert(trace_direction.X==1 and crosshair.translation)
        local first=crosshair.translation.X
        hand_direction={X=0.98,Y=0.2,Z=0}
        tick(nil,1/90)
        assert(trace_direction.Y==0.2)
        assert(crosshair.translation.X>first,
            'Crosshair must follow the hand when a gun sample is unavailable')
    """)
