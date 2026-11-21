"""Exercise real tracked-gun aim and native shot rotation with Lua engine doubles."""
from pathlib import Path

from lupa import LuaRuntime


SCRIPT = Path(__file__).resolve().parents[1] / "profile/scripts/libs/crisol_aim.lua"
UTILS = SCRIPT.with_name("uevr_utils.lua")


def aim_runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(r'''
        function vec(x,y,z)
            if type(x)=='table' then return {X=x.X,Y=x.Y,Z=x.Z} end
            return {X=x or 0,Y=y or 0,Z=z or 0}
        end
        local function transform(t,p)
            local angle=math.rad(t.Yaw)
            return vec(t.X+p.X*math.cos(angle)-p.Y*math.sin(angle),
                t.Y+p.X*math.sin(angle)+p.Y*math.cos(angle),t.Z+p.Z)
        end
        pawn={}; gun={visible=true}
        function gun:IsVisible() return self.visible end
        right={world={X=100,Y=0,Z=0,Yaw=0}}
        function right:K2_GetComponentToWorld() return self.world end
        view=vec(0,0,0); rotation=nil; hit=nil; traced={}
        pc={}
        function pc:GetPlayerViewPoint(position,rot)
            position.X=view.X; position.Y=view.Y; position.Z=view.Z
        end
        function pc:SetControlRotation(value) rotation=value end
        utils={
            vector=vec,
            rotator=function(p,y,r) return {Pitch=p,Yaw=y,Roll=r} end,
            find_default_instance=function() return {TransformLocation=function(_,t,p) return transform(t,p) end} end,
            getValid=function(v) if v and not v.invalid then return v end end,
            get_player_controller=function() return pc end,
            getTargetLocation=function(origin,dir)
                traced={origin=origin,direction=dir}
                return hit
            end,
        }
        controllers={getController=function() return right end}
        package.preload['libs/uevr_utils']=function() return utils end
        package.preload['libs/controllers']=function() return controllers end
    ''')
    lua.globals().aim = lua.execute(SCRIPT.read_text(encoding="utf-8"))
    return lua


def test_gun_ray_follows_right_controller_and_native_rotation_accounts_for_parallax():
    lua = aim_runtime()
    lua.execute(r'''
        aim.set_sample(pawn,gun,vec(0,0,0),vec(20,0,0))
        assert(not aim.get_ray(pawn))
        aim.set_enabled(true)
        local origin,direction=aim.get_ray(pawn)
        assert(origin.X==100 and direction.X==1 and direction.Y==0)
        hit=vec(100,100,0)
        assert(aim.apply_controller_rotation(pawn))
        assert(math.abs(rotation.Yaw-45)<0.00001)
        assert(traced.origin.X==100 and traced.direction.X==1)
        assert(aim.get_target(pawn)==hit, 'HUD must use the exact point applied to the shot')

        right.world={X=100,Y=0,Z=0,Yaw=90}
        origin,direction=aim.get_ray(pawn)
        assert(math.abs(direction.X)<0.00001 and math.abs(direction.Y-1)<0.00001)
        hit=nil
        assert(aim.apply_controller_rotation(pawn))
        assert(math.abs(rotation.Yaw-89.3007)<0.01,
            'Native shot must aim at the weapon ray from the game camera')
        assert(math.abs(aim.get_target(pawn).Y-8192)<0.01)
        aim.clear_sample()
        assert(not aim.get_ray(pawn))
        assert(not aim.get_target(pawn))
    ''')


def test_native_rotation_with_reflected_vectors_without_arithmetic_metamethods():
    lua = aim_runtime()
    source = UTILS.read_text(encoding="utf-8")
    trace = source[source.index("function M.getLineTraceHitResult("):
                   source.index("function M.getArrayRange(")]
    lua.execute(r'''
        local M = utils
        local reusable_hit_result = {Location=vec(1000,100,0)}
        local zero_color = {}
        local kismet_system_library = {LineTraceSingle=function(_,world,origin,endpoint)
            assert(origin.X==100 and endpoint.X==8292 and endpoint.Y==0)
            return true
        end}
        function M.get_world() return {} end
        function M.vectorDistance(a,b) return math.sqrt((a.X-b.X)^2+(a.Y-b.Y)^2+(a.Z-b.Z)^2) end
    ''' + trace + r'''
        aim.set_enabled(true)
        aim.set_sample(pawn,gun,vec(0,0,0),vec(20,0,0))
        assert(aim.apply_controller_rotation(pawn))
        assert(math.abs(rotation.Yaw-math.deg(math.atan(0.1)))<0.00001)
    ''')


def test_invalid_or_switched_gun_does_not_apply_stale_aim():
    lua = aim_runtime()
    lua.execute(r'''
        aim.set_enabled(true)
        aim.set_sample(pawn,gun,vec(0,0,0),vec(20,0,0))
        assert(not aim.get_ray({}))
        gun.visible=false
        assert(not aim.apply_controller_rotation(pawn))
        gun.visible=true; right.invalid=true
        assert(not aim.get_ray(pawn))
        right.invalid=nil; gun.invalid=true
        assert(not aim.get_ray(pawn))
        gun.invalid=nil
        aim.set_enabled(false)
        assert(not aim.apply_controller_rotation(pawn))
    ''')
