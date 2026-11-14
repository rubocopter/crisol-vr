from pathlib import Path

from lupa import LuaRuntime

SCRIPT = Path(__file__).resolve().parents[1] / "profile/scripts/hands.lua"


def lifecycle():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("""
        pawn={PlayerArms={}}; created=false; setup_count=0; destroy_count=0; reset_count=0
        fail_setup=false; configured_pawn=nil; right_missing=false
        local mesh={GetBoneTransformByName=function() return {Translation={X=1,Y=2,Z=3}} end}
        local utils={
            setInterval=function(ms,fn) poll=fn end,
            getValid=function(o) if o and not o.invalid then return o end end,
            fname_from_string=function(s) return s end,
            vector=function(x,y,z) return {X=x,Y=y,Z=z} end,
            set_component_relative_transform=function() end,
            find_default_instance=function() return {
                MakeRotFromXZ=function() return {Pitch=0,Yaw=0,Roll=0} end,
                NegateRotator=function(self,r) return r end,
            } end,
        }
        local hands={
            setAutoCreateHands=function() end,
            exists=function() return created end,
            createFromConfig=function() created=true; right_missing=false end,
            destroyHands=function() destroy_count=destroy_count+1; created=false end,
            getHandComponent=function(id) if id==1 and right_missing then return nil end; return mesh end,
            setRotation=function() end,
        }
        local pose={
            setup=function(p)
                setup_count=setup_count+1
                if fail_setup then error('pose setup failed') end
                configured_pawn=p
            end,
            reset=function() reset_count=reset_count+1; configured_pawn=nil end,
        }
        package.preload['libs/uevr_utils']=function() return utils end
        package.preload['libs/hands']=function() return hands end
        package.preload['libs/crisol_hand_pose']=function() return pose end
        package.preload['libs/controllers']=function() return {
            createController=function() end,controllerExists=function() return true end,
        } end
        uevr={api={get_local_pawn=function() return pawn end},params={functions={
            log_info=function() end,log_warn=function() end,
        }}}
    """)
    lua.execute(SCRIPT.read_text(encoding="utf-8"))
    return lua


def test_recreates_hands_for_replaced_pawn_without_level_change():
    lua = lifecycle()
    lua.execute("""
        poll(); assert(configured_pawn==pawn)
        pawn={PlayerArms={}}
        poll()
        assert(configured_pawn==pawn and setup_count==2)
        assert(destroy_count==1 and reset_count>=1)
    """)


def test_recreates_hands_when_same_pawn_replaces_arms():
    lua = lifecycle()
    lua.execute("poll(); pawn.PlayerArms={}; poll(); assert(setup_count==2)")


def test_failed_setup_is_cleaned_up_and_retried():
    lua = lifecycle()
    lua.execute("""
        fail_setup=true; poll()
        assert(not created, 'Partially initialized hands must not prevent retries')
        fail_setup=false; poll()
        assert(created and configured_pawn==pawn and setup_count==2)
    """)


def test_recreates_pair_when_only_one_hand_survives():
    lua = lifecycle()
    lua.execute("""
        poll(); right_missing=true; poll()
        assert(setup_count==2 and not right_missing and destroy_count==1)
    """)


def test_departing_pawn_releases_hands_and_stable_pawn_is_not_rebuilt():
    lua = lifecycle()
    lua.execute("""
        poll(); poll(); poll(); assert(setup_count==1 and destroy_count==0)
        pawn=nil; poll()
        assert(not created and configured_pawn==nil and destroy_count==1)
        poll(); assert(destroy_count==1)
    """)
