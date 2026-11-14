"""Regression: safe UI camera must not turn gameplay aiming into head aiming."""
from pathlib import Path

from lupa import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]


def runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("""
        settings={}; writes=0; aim=2; warnings={}; widgets={}; scans=0
        world={paused=false}; pause_queries=0
        statics={IsGamePaused=function(self,w)
            assert(w==world); pause_queries=pause_queries+1; return w.paused
        end}
        pawn=nil; controller={bShowMouseCursor=false}; state=0
        function gameplay()
            pawn={PlayerArms={},GetPlayerState=function() return state end}
            controller.PlayerCameraManager={ViewTarget={Target=pawn}}
        end
        uevr={api={
            get_local_pawn=function() return pawn end,
            get_player_controller=function() return controller end,
        },params={vr={
            set_mod_value=function(k,v) settings[k]=v; writes=writes+1 end,
            get_mod_value=function(self,k) return settings[k] end,
            get_aim_method=function() return aim end,
            set_aim_method=function(v) aim=v; settings.VR_AimMethod=tostring(v); writes=writes+1 end,
        },functions={log_info=function() end,log_warn=function(s) warnings[#warnings+1]=s end}},
        sdk={callbacks={
            on_pre_engine_tick=function(fn) pre_tick=fn end,
            on_post_engine_tick=function(fn) post_tick=fn end,
            on_xinput_get_state=function(fn) input_tick=fn end,
        }}}
        package.preload['libs/uevr_utils']=function() return {
            getValid=function(o) if o and not o.invalid then return o end end,
            get_world=function() return world end,
            find_default_instance=function(class)
                assert(class=='Class /Script/Engine.GameplayStatics'); return statics
            end,
            find_all_of=function(class)
                assert(class=='Class /Script/UMG.UserWidget'); scans=scans+1; return widgets
            end,
            setInterval=function() end,
        } end
        package.preload['libs/crisol_controller_input']=function() return {process=function() end} end
        package.path=SCRIPT_ROOT..'/?.lua;'..package.path
    """.replace("SCRIPT_ROOT", repr((ROOT / "profile/scripts").as_posix())))
    lua.execute((ROOT / "profile/scripts/crisol_sense.lua").read_text(encoding="utf-8"))
    return lua


def test_gameplay_restores_controller_trace_and_control_rotation():
    lua = runtime()
    lua.execute("""
        gameplay(); pre_tick(nil,1/90)
        assert(aim==2, 'Interaction and bullet traces must use the right controller during gameplay')
        assert(settings.VR_AimModifyPlayerControlRotation=='true')
        assert(settings.UI_FollowView=='true')
    """)


def test_menu_then_gameplay_then_interaction_then_return():
    lua = runtime()
    lua.execute("""
        pre_tick(nil,1/90); assert(aim==1)
        gameplay(); pre_tick(nil,1/90); assert(aim==2)
        state=3; assert(post_tick, 'Inspection must switch before its first rendered frame')
        post_tick(nil,1/90); assert(aim==1)
        assert(settings.VR_AimModifyPlayerControlRotation=='false')
        state=0; pre_tick(nil,1/90); assert(aim==2)
        pawn=nil; post_tick(nil,1/90); assert(aim==1)
    """)


def test_scripted_camera_and_visible_cursor_keep_head_camera():
    lua = runtime()
    lua.execute("""
        gameplay(); controller.PlayerCameraManager.ViewTarget.Target={}
        pre_tick(nil,1/90); assert(aim==1)
        controller.PlayerCameraManager.ViewTarget.Target=pawn
        controller.bShowMouseCursor=true; pre_tick(nil,1/90); assert(aim==1)
        controller.bShowMouseCursor=false; pre_tick(nil,1/90); assert(aim==2)
    """)


def test_inspection_widget_blocks_hand_aim_without_blocking_next_gameplay():
    lua = runtime()
    lua.execute("""
        gameplay()
        local inspection={visible=true,
            get_full_name=function() return 'InspectionWBP_C /Engine/Transient.Test' end,
            IsVisible=function(self) return self.visible end,
            IsInViewport=function() return true end,
            GetOwningPlayerPawn=function() return pawn end,
        }
        widgets={inspection}; pre_tick(nil,1/90); assert(aim==1)
        inspection.visible=false; pre_tick(nil,1/90); assert(aim==2)
        local before=scans
        for i=1,5 do pre_tick(nil,1/90) end
        assert(scans==before, 'Do not enumerate widgets every engine tick')
    """)


def test_blocked_and_cinematic_states_use_head_camera():
    lua = runtime()
    lua.execute("""
        gameplay(); state=4; pre_tick(nil,1/90); assert(aim==1)
        state=0; pawn.GetIsCharacterOnCinematicMode=function() return true end
        pre_tick(nil,1/90); assert(aim==1)
        pawn.GetIsCharacterOnCinematicMode=function() return false end
        pre_tick(nil,1/90); assert(aim==2)
    """)


def test_looking_at_interactable_still_uses_hand_aim_until_activation():
    lua = runtime()
    lua.execute("""
        gameplay(); pawn.GetActualInteractuable=function() return {} end
        pre_tick(nil,1/90); assert(aim==2)
        state=2; pre_tick(nil,1/90); assert(aim==2)
        state=3; post_tick(nil,1/90); assert(aim==1)
    """)


def test_tab_menu_is_head_aimed_even_without_mouse_cursor():
    lua = runtime()
    lua.execute("""
        gameplay(); pawn.bIsTabMenu=true
        pre_tick(nil,1/90); assert(aim==1)
        pawn.bIsTabMenu=false; pre_tick(nil,1/90); assert(aim==2)
    """)


def test_invalid_context_falls_back_to_head_then_recovers():
    lua = runtime()
    lua.execute("""
        gameplay(); pre_tick(nil,1/90); assert(aim==2)
        local get_pawn=uevr.api.get_local_pawn
        uevr.api.get_local_pawn=function() error('world changing') end
        pre_tick(nil,1/90)
        assert(aim==1 and settings.VR_AimModifyPlayerControlRotation=='false')
        pre_tick(nil,1/90); assert(#warnings==1)
        uevr.api.get_local_pawn=get_pawn
        pre_tick(nil,1/90); assert(aim==2)
    """)


def test_world_pause_without_reflected_controller_method_uses_head_and_resumes():
    lua = runtime()
    lua.execute("""
        gameplay(); pre_tick(nil,1/90); assert(aim==2)
        assert(controller.IsPaused==nil and not controller.bShowMouseCursor)
        world.paused=true; post_tick(nil,0)
        assert(aim==1, 'Pause must keep the camera on the headset without a cursor or controller IsPaused')
        assert(settings.VR_AimModifyPlayerControlRotation=='false')
        world.paused=false; pre_tick(nil,1/90)
        assert(aim==2 and settings.VR_AimModifyPlayerControlRotation=='true')
        assert(pause_queries>0)
    """)


def test_pause_query_uses_current_world_after_level_change():
    lua = runtime()
    lua.execute("""
        gameplay(); pre_tick(nil,1/90); assert(aim==2)
        world={paused=true}; gameplay(); post_tick(nil,0); assert(aim==1)
        world.paused=false; pre_tick(nil,1/90); assert(aim==2)
    """)
