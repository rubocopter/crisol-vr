"""Execute shipped hand callbacks in Lua; engine doubles do not replace hand logic."""
from pathlib import Path

import pytest
from lupa import LuaRuntime


SCRIPT = Path(__file__).resolve().parents[1] / "profile/scripts/libs/crisol_hand_pose.lua"

ENGINE = r'''
callbacks={}; scans={}; warnings={}; classes={}; actors={}; holding=false
function vec(x,y,z) return {X=x or 0,Y=y or 0,Z=z or 0} end
function tr(x,y,z,yaw) return {Translation=vec(x,y,z),Rotation={Yaw=yaw or 0},Scale3D=vec(1,1,1)} end
function rotate(p,yaw)
    local a=math.rad(yaw or 0)
    return vec(math.cos(a)*p.X-math.sin(a)*p.Y,math.sin(a)*p.X+math.cos(a)*p.Y,p.Z)
end
function compose(a,b) -- Unreal applies A, then B (including B's rotation).
    local p=rotate(a.Translation,b.Rotation.Yaw)
    return tr(p.X+b.Translation.X,p.Y+b.Translation.Y,p.Z+b.Translation.Z,
        (a.Rotation.Yaw or 0)+(b.Rotation.Yaw or 0))
end
function inverse(a)
    local p=rotate(vec(-a.Translation.X,-a.Translation.Y,-a.Translation.Z),-(a.Rotation.Yaw or 0))
    return tr(p.X,p.Y,p.Z,-(a.Rotation.Yaw or 0))
end
function near(actual,want) assert(math.abs(actual-want)<0.00001,tostring(actual)..' ~= '..tostring(want)) end
function fname(s) return {to_string=function() return s end} end
Vector3f={new=vec}; Quaternionf={new=function() return {} end}
local serial=0
function component(name,owner,x)
    serial=serial+1
    local c={name=name or 'Mesh',owner=owner,address=serial,visible=true,
        RelativeLocation=vec(),RelativeRotation={},RelativeScale3D=vec(1,1,1),
        world=tr(x),bones={},socket=fname('None')}
    function c:get_address() return self.address end
    function c:get_fname() return fname(self.name) end
    function c:GetOwner() return self.owner end
    function c:IsVisible() return self.visible end
    function c:SetVisibility(v) self.visible=v end
    function c:SetRenderInMainPass(v) self.bRenderInMainPass=v end
    function c:SetFirstPersonPrimitiveType(v) self.FirstPersonPrimitiveType=v end
    function c:GetAttachParent() return self.parent end
    function c:GetAttachSocketName() return self.socket end
    function c:K2_AttachToComponent(p,s)
        if self.fail_attach then return false end
        self.parent=p; self.socket=s; return true
    end
    function c:K2_DetachFromComponent() self.parent=nil end
    function c:K2_SetRelativeTransform(t) self.relative=t; self.RelativeLocation=t.Translation end
    function c:K2_GetComponentToWorld() return self.world end
    function c:K2_GetComponentLocation() return self.world.Translation end
    function c:K2_SetWorldTransform(t) self.world=t; self.world_writes=(self.world_writes or 0)+1 end
    function c:GetBoneTransformByName(n) return self.bones[n:to_string()] or tr() end
    function c:SetBoneTransformByName(n,t) self.bones[n:to_string()]=t end
    function c:GetSocketTransform(n) return self.bones[n:to_string()] or self.world end
    function c:DoesSocketExist() return false end
    function c:GetAnimInstance() return anim end
    return c
end
function actor(cls,owned)
    local a={cls=cls,owner=owned,components={}}
    function a:get_full_name() return self.cls..' Object' end
    function a:GetOwner() return self.owner end
    function a:GetAttachParentActor() return self.parent end
    function a:K2_GetComponentsByClass(kind)
        if kind=='Class /Script/Engine.SkeletalMeshComponent' then return self.components end
        return {}
    end
    local m=component('Mesh',a)
    a.components={m}; actors[#actors+1]=a
    local cl=classes[cls]
    if not cl then
        cl={name=cls}
        function cl:get_fname() return fname(self.name) end
        function cl:get_objects_matching(defaults)
            assert(defaults==false)
            scans[self.name]=(scans[self.name] or 0)+1
            local result={}
            for _,entry in ipairs(actors) do if entry.cls==self.name then result[#result+1]=entry end end
            return result
        end
        classes[cls]=cl
    end
    function a:get_class() return cl end
    return a,m
end
anim={GetCurrentActiveMontage=function(self) return self.montage end}
pawn={Children={},GetIsUsingKnife=function(self) return self.knife end}
source=component('Source'); left=component('Left'); right=component('Right')
lc=component('LC',nil,0); rc=component('RC',nil,100)
left.parent=lc; right.parent=rc
physical_left=vec(0,1,0); physical_right=vec(1,1,0); using_controllers=true
physical_left_rotation={x=0,y=0,z=0,w=1}; physical_right_rotation={x=0,y=0,z=0,w=1}
active_xinput=0; XINPUT_GAMEPAD_LEFT_SHOULDER=0x100
    utils={
    isButtonPressed=function(s,mask) return (s.Gamepad.wButtons & mask)~=0 end,
    getValid=function(o) if o and not o.invalid then return o end end,
    vector=vec, rotator=function() return {} end, fname_from_string=fname,
    setInterval=function(ms,fn) callbacks.interval=fn end,
    registerPostEngineTickCallback=function(fn) callbacks.tick=fn end,
    registerPostCalculateStereoViewCallback=function(fn) callbacks.stereo=fn end,
    registerOnInputGetStateCallback=function(fn) callbacks.input=fn end,
    registerPreLevelChangeCallback=function(fn) callbacks.level=fn end,
    get_class=function(s) return s end,
    find_all_instances=function(kind,defaults)
        scans[kind]=(scans[kind] or 0)+1
        local result={}
        if kind=='Class /Script/CoreUObject.Class' then
            for _,cl in pairs(classes) do result[#result+1]=cl end
        else -- Old broad fallback, retained to reproduce its regressions.
            for _,a in ipairs(actors) do for _,m in ipairs(a.components) do result[#result+1]=m end end
        end
        return result
    end,
}
utils.find_all_of=utils.find_all_instances
UEVR_UObjectHook={get_objects_by_class=function(class,defaults) return class:get_objects_matching(defaults) end}
hands={exists=function() return true end,
    getHandComponent=function(id) return id==0 and left or right end,
    setHoldingAttachment=function(_,v) holding=v end,
    hideHands=function() left.visible=false; right.visible=false end}
controllers={getController=function(id) return id==0 and lc or rc end}
animation={add=function() end,resetAnimation=function() end,updateAnimation=function() end,
    setBoneSpaceLocalRotator=function() end}
mathlib={
    MakeTransform=function(_,p,r,s) return {Translation=p,Rotation=r,Scale3D=s} end,
    MakeRelativeTransform=function(_,a,b)
        return compose(a,inverse(b))
    end,
    InvertTransform=function(_,a) return inverse(a) end,
    ComposeTransforms=function(_,a,b) return compose(a,b) end,
    TransformRotation=function(_,a,r) return {Yaw=(a.Rotation.Yaw or 0)+(r.Yaw or 0)} end,
    TransformLocation=function(_,a,p) return compose(tr(p.X,p.Y,p.Z),a).Translation end,
}
uevr={api={get_local_pawn=function() return pawn end},params={
    vr={is_using_controllers=function() return using_controllers end,
        get_lowest_xinput_index=function() return active_xinput end,
        get_left_controller_index=function() return 1 end,get_right_controller_index=function() return 2 end,
        get_pose=function(id,p,q)
            local v=id==1 and physical_left or physical_right
            p.x=v.X; p.y=v.Y; p.z=v.Z; p.X=v.X; p.Y=v.Y; p.Z=v.Z
            local r=id==1 and physical_left_rotation or physical_right_rotation
            q.x=r.x; q.y=r.y; q.z=r.z; q.w=r.w
        end,
        get_left_joystick_source=function() return 0 end,is_action_active=function() return false end},
    functions={log_info=function() end,log_warn=function(s) warnings[#warnings+1]=s end},
    sdk={callbacks={on_script_reset=function(fn) callbacks.reset=fn end}}}}
json={load_file=function() return {} end}
package.preload['libs/uevr_utils']=function() return utils end
package.preload['libs/hands']=function() return hands end
package.preload['libs/controllers']=function() return controllers end
package.preload['libs/animation']=function() return animation end

-- Locate lexical state without adding test APIs to the shipped Lua.
function slot(name)
    local seen={}
    local function search(fn)
        if seen[fn] then return end; seen[fn]=true
        for i=1,200 do
            local n,v=debug.getupvalue(fn,i)
            if not n then break end
            if n==name then return fn,i end
            if n~='_ENV' and type(v)=='function' then
                local f,j=search(v); if f then return f,j end
            end
        end
    end
    for _,fn in pairs(callbacks) do local f,i=search(fn); if f then return f,i end end
    error('No upvalue '..name)
end
function put(name,value) local f,i=slot(name); debug.setupvalue(f,i,value) end
function read(name) local f,i=slot(name); local _,v=debug.getupvalue(f,i); return v end
function tick(n,dt) for i=1,n or 1 do callbacks.tick(nil,dt or 0.05) end end
function clean() assert(#warnings==0,table.concat(warnings,'\n')) end
function armed(cls)
    gun_actor,gun=actor(cls or 'CRWDivinePistolNew_BP_C',pawn)
    put('weapon',gun); put('attached_weapon',gun); right.parent=gun
    put('pistol',{mesh=gun,effects={}})
    put('grip_cache',{[gun:get_address()]=tr()})
    holding=true
end
'''


@pytest.fixture
def lua():
    vm = LuaRuntime(unpack_returned_tuples=True)
    vm.execute(ENGINE)
    vm.globals().pose = vm.execute(SCRIPT.read_text(encoding="utf-8"))
    vm.execute(r'''
        put('source',source); put('player',pawn); put('mathlib',mathlib)
        put('left_wrist',fname('l_wrist_jnt')); put('weapon_bone',fname('r_weapon'))
        put('no_socket',fname('None')); put('hit',{})
        put('right_free',{transform=tr(),bones={}})
        put('left_pose',{mesh=left,free=tr(),wrist_inverse=tr(),effects_checked=true,
            original_bones={{name=fname('l_wrist_jnt'),transform=tr()},
                {name=fname('l_index_01_jnt'),transform=tr(2)}},
            grip={alpha=0.18,joints={}},trigger={alpha=0.12,joints={}},thumb={alpha=0.14,joints={}}})
    ''')
    return vm


def test_fallback_selects_on_first_callback(lua):
    lua.execute("a,m=actor('CRWDivinePistolNew_BP_C',pawn); callbacks.interval(); assert(read('weapon')==m); clean()")


def test_hidden_child_does_not_block_equipped_fallback(lua):
    lua.execute(r'''
        hidden,hm=actor('CRDivineShotGun_BP_C',pawn); hidden.bHidden=true; pawn.Children={hidden}
        equipped,em=actor('CRWDivinePistolNew_BP_C',pawn)
        for i=1,100 do callbacks.interval() end
        assert(read('weapon')==em); clean()
    ''')


def test_hidden_child_does_not_block_cached_candidate(lua):
    lua.execute(r'''
        a,m=actor('CRWDivinePistolNew_BP_C',pawn)
        put('fallback_elapsed',20); callbacks.interval(); assert(read('weapon')==m)
        hidden,hm=actor('CRDivineShotGun_BP_C',pawn); hm.visible=false; pawn.Children={hidden}
        callbacks.interval(); callbacks.interval(); assert(read('weapon')==m); clean()
    ''')


def test_fallback_targets_actor_classes_and_bounds_steady_scans(lua):
    lua.execute(r'''
        a,m=actor('CRWDivinePistolNew_BP_C',pawn)
        for i=1,100 do callbacks.interval() end
        assert(read('weapon')==m)
        assert(not scans['Class /Script/Engine.SkeletalMeshComponent'])
        assert(not scans['Class /Script/Engine.StaticMeshComponent'])
        assert((scans.CRWDivinePistolNew_BP_C or 0)>0)
        assert(scans.CRWDivinePistolNew_BP_C<=12); clean()
    ''')


@pytest.mark.parametrize("change", ["m.visible=false", "m.bHiddenInGame=true", "a.bHidden=true", "a.owner={}", "m.invalid=true", "m.owner={}"])
def test_cached_fallback_is_revalidated_and_replaced(lua, change):
    # Both weapon classes are loaded, as with inventory; only actor discovery
    # needs refreshing when the equipped component is invalidated.
    lua.execute("actor('CRDivineShotGun_BP_C',{})")
    lua.execute("a,m=actor('CRWDivinePistolNew_BP_C',pawn); put('fallback_elapsed',20); callbacks.interval(); assert(read('weapon')==m)")
    lua.execute(change)
    lua.execute(r'''
        b,n=actor('CRDivineShotGun_BP_C',pawn)
        for i=1,6 do callbacks.interval() end
        assert(read('weapon')==n); clean()
    ''')


def test_physical_contact_latches_native_fingers_and_separation_releases(lua):
    lua.execute(r'''
        armed(); physical_right=vec(0.07,1,0) -- 7 cm, cached world controllers remain 100 cm apart
        source.bones.l_wrist_jnt=tr(5); source.bones.l_index_01_jnt=tr(8)
        tick(2); assert(left.parent==lc)
        tick(2); assert(left.parent==gun)
        assert(left.bones.l_index_01_jnt.Translation.X==3)
        physical_right=vec(0.12,1,0); tick(10); assert(left.parent==gun)
        physical_right=vec(0.5,1,0); tick(9); assert(left.parent==lc)
        assert(left.bones.l_index_01_jnt.Translation.X==2); clean()
    ''')


def test_stale_near_world_controllers_cannot_attach_distant_physical_hands(lua):
    lua.execute("armed(); rc.world=tr(0); tick(20); assert(left.parent==lc); clean()")


def test_inactive_controllers_cannot_latch(lua):
    lua.execute("armed(); using_controllers=false; rc.world=tr(); tick(20); assert(left.parent==lc); clean()")


def test_reload_releases_support_and_requires_new_contact(lua):
    lua.execute(r'''
        armed(); rc.world=tr(5); physical_right=vec(0.05,1,0); tick(4)
        assert(left.parent==gun and read('left_pose').support_weapon==gun)
        anim.bIsReloading=true; tick(); assert(read('left_pose').support_weapon==nil)
        anim.bIsReloading=false; physical_right=vec(1,1,0); rc.world=tr(100)
        tick(10); assert(left.parent==lc); clean()
    ''')


def test_weapon_change_releases_both_old_mounts(lua):
    lua.execute(r'''
        armed(); rc.world=tr(5); physical_right=vec(0.05,1,0); tick(4)
        local old=gun
        new_actor,new=actor('CRDivineShotGun_BP_C',pawn)
        put('weapon',new)
        put('grip_pose_cache',{[new:get_address()]={component=new,bones={},animation={},relative=tr()}})
        physical_right=vec(1,1,0); tick()
        assert(left.parent==lc and right.parent==new and old~=read('attached_weapon')); clean()
    ''')


def test_native_transition_restores_walkie_and_free_hand(lua):
    lua.execute(r'''
        a,radio=actor('Walkie_BP_C',pawn); local parent=source; local socket=fname('Radio')
        radio.parent=parent; radio.socket=socket
        put('weapon',radio); put('walkie',radio); put('attached_weapon',radio); right.parent=radio
        put('tracked_walkie',{component=radio,controller=rc,parent=parent,socket=socket,
            relative=tr(7),relative_to_controller=tr(3)})
        pawn.knife=true; tick()
        assert(source.visible and not right.visible and not holding)
        assert(radio.relative.Translation.X==7 and read('tracked_walkie')==nil)
        put('weapon',nil); put('walkie',nil); pawn.knife=false; tick(20)
        assert(not source.visible and right.visible and right.parent==rc); clean()
    ''')


def test_walkie_changed_native_parent_is_not_overwritten(lua):
    lua.execute(r'''
        a,radio=actor('Walkie_BP_C',pawn); radio.parent=left
        put('weapon',radio); put('walkie',radio); put('attached_weapon',radio); right.parent=radio
        put('grip_cache',{[radio:get_address()]=tr(2)})
        put('tracked_walkie',{component=radio,controller=rc,parent=source,socket=radio.socket,
            relative=tr(7),relative_to_controller=tr(3)})
        tick(); assert(not radio.world_writes); assert(read('tracked_walkie')==nil); clean()
    ''')


def test_failed_native_grip_does_not_black_out_hand_forever(lua):
    lua.execute(r'''
        a,m=actor('CRDivineShotGun_BP_C',pawn); put('weapon',m)
        source.bones.r_wrist_jnt=tr(100) -- game has not supplied a usable grip
        tick(25)
        assert(right.visible and right.parent==rc and not holding)
        assert(#warnings>0) -- expected reach rejection, not a silently swallowed test error
        for _,s in ipairs(warnings) do assert(s:find('Native grip is outside weapon reach',1,true)) end
    ''')


def test_level_change_drops_cache_and_searches_immediately(lua):
    lua.execute(r'''
        a,m=actor('CRWDivinePistolNew_BP_C',pawn); put('fallback_elapsed',20); callbacks.interval()
        callbacks.level(); a.invalid=true; m.invalid=true
        pawn={Children={}}; a2,m2=actor('CRDivineShotGun_BP_C',pawn)
        put('source',source); put('player',pawn); callbacks.interval()
        assert(read('weapon')==m2); clean()
    ''')


def test_reset_restores_source_projection_and_clears_state_idempotently(lua):
    lua.execute(r'''
        armed(); source.VisibilityBasedAnimTickOption=0; source.visible=false
        source.bRenderInMainPass=false; source.UseDesiredFOV=false
        put('saved_tick',3)
        put('projection_original',{[source]={fov=true}})
        pose.reset(); pose.reset()
        assert(source.VisibilityBasedAnimTickOption==3 and source.visible and source.bRenderInMainPass)
        assert(source.UseDesiredFOV==true and right.parent==rc and not holding)
        assert(read('weapon')==nil and read('source')==nil and read('pistol')==nil)
        assert(next(read('grip_cache'))==nil and next(read('left_pose'))==nil)
        callbacks.tick(nil,0.05); callbacks.interval(); clean()
    ''')


def test_partial_setup_failure_reset_restores_original_hidden_source(lua):
    lua.execute(r'''
        source.visible=false; source.bRenderInMainPass=false; source.VisibilityBasedAnimTickOption=4
        source.UseDesiredFOV=true; source.FirstPersonPrimitiveType=2; pawn.PlayerArms=source
        utils.find_default_instance=function() return mathlib end
        utils.get_struct_object=function() return {} end
        local ok=pcall(pose.setup,pawn) -- fails at missing setAutoHandleInput after source mutation
        assert(not ok and source.VisibilityBasedAnimTickOption==0 and source.UseDesiredFOV==false)
        pose.reset(); pose.reset()
        assert(source.VisibilityBasedAnimTickOption==4 and not source.visible and not source.bRenderInMainPass)
        assert(source.UseDesiredFOV and source.FirstPersonPrimitiveType==2); clean()
    ''')


@pytest.mark.parametrize("pose_failure", [
    "uevr.params.vr.get_pose=function() end",
    "uevr.params.vr.get_pose=function() error('unavailable') end",
    "physical_left=vec(); physical_right=vec()",
    "uevr.params.vr.get_right_controller_index=function() return 1 end",
])
def test_unavailable_pose_never_uses_cached_contact(lua, pose_failure):
    lua.execute("armed(); rc.world=tr()")
    lua.execute(pose_failure)
    lua.execute("tick(20); assert(left.parent==lc); clean()")


@pytest.mark.parametrize("weapon_class", ["CRDivineShotGun_BP_C", "CRWDMachineGun_BP_C", "CRDivineSniper_BP_C", "CRDivineHarpoon_BP_C"])
def test_supported_gun_cached_mount_can_use_native_support(lua, weapon_class):
    lua.globals().gun_class = weapon_class
    lua.execute(r'''
        a,m=actor(gun_class,pawn); put('weapon',m)
        put('grip_pose_cache',{[m:get_address()]={component=m,bones={},animation={},relative=tr()}})
        physical_right=vec(0.05,1,0); tick(4)
        assert(right.parent==m and left.parent==m); clean()
    ''')


def test_walkie_controller_replacement_recovers_and_reset_restores_prop(lua):
    lua.execute(r'''
        a,radio=actor('Walkie_BP_C',pawn); radio.parent=source
        local old=rc; old.invalid=true; rc=component('Replacement',nil,20)
        put('weapon',radio); put('walkie',radio); put('attached_weapon',radio); right.parent=radio
        put('grip_cache',{[radio:get_address()]=tr(2)})
        put('tracked_walkie',{component=radio,controller=old,parent=source,socket=radio.socket,
            relative=tr(7),relative_to_controller=tr(3)})
        tick(); assert(read('tracked_walkie')==nil and right.parent==rc)
        -- Reuse the captured test grip after the deferred native pose tick.
        put('attached_weapon',radio); right.parent=radio; put('grip_cache',{[radio:get_address()]=tr(2)})
        tick(); assert(read('tracked_walkie').controller==rc)
        assert(radio.world.Translation.X==18)
        pose.reset(); assert(radio.relative.Translation.X==7 and right.parent==rc)
        clean()
    ''')


def test_reset_releases_partially_attached_right_hand(lua):
    lua.execute(r'''
        a,m=actor('Walkie_BP_C',pawn); right.parent=m
        put('attached_weapon',nil) -- attachment succeeded, next setup operation failed
        pose.reset(); assert(right.parent==rc and not holding); clean()
    ''')


def test_input_follows_active_vr_xinput_index_and_ignores_other_pads(lua):
    lua.execute(r'''
        active_xinput=2
        local pressed={Gamepad={wButtons=0x100,bLeftTrigger=204,bRightTrigger=128}}
        callbacks.input(nil,0,pressed)
        assert(read('input').grip==0 and read('input').left_trigger==0)
        callbacks.input(nil,2,pressed)
        assert(read('input').grip==1 and read('input').left_trigger==0.8 and read('input').right_trigger)
        callbacks.input(nil,1,{Gamepad={wButtons=0,bLeftTrigger=0,bRightTrigger=0}})
        assert(read('input').grip==1 and read('input').right_trigger)
        using_controllers=false; callbacks.input(nil,2,pressed)
        assert(read('input').grip==0 and read('input').left_trigger==0 and not read('input').right_trigger)
        clean()
    ''')


def test_unarmed_discovery_bounds_class_metadata_refresh(lua):
    lua.execute(r'''
        for i=1,100 do callbacks.interval() end
        assert(scans['Class /Script/CoreUObject.Class']<=11)
        assert(read('weapon')==nil); clean()
    ''')


def test_recognized_child_seeds_class_for_prompt_fallback(lua):
    lua.execute(r'''
        a,m=actor('CRWDivinePistolNew_BP_C',pawn); pawn.Children={a}; callbacks.interval()
        a.bHidden=true
        b,n=actor('CRDivineShotGun_BP_C',pawn); pawn.Children={b}; callbacks.interval()
        assert(read('weapon')==n)
        pawn.Children={}; callbacks.interval(); callbacks.interval()
        assert(read('weapon')==n and scans['Class /Script/CoreUObject.Class']==1)
        clean()
    ''')


def test_support_uses_native_anchor_before_vr_and_preserves_rotated_bones(lua):
    lua.execute(r'''
        armed(); physical_right=vec(0.05,1,0)
        -- Native r_weapon and the rendered UObjectHook weapon occupy different
        -- spaces. Native frame: (10,20), yaw 90; VR frame: (600,700), yaw -60.
        source.bones.r_weapon=tr(10,20,0,90); gun.world=tr(600,700,0,-60)
        source.bones.l_wrist_jnt=tr(10,25,0,120)
        source.bones.l_index_01_jnt=tr(7,25,0,150)
        read('left_pose').wrist_inverse=inverse(tr(1,2,0,20))
        tick(4); assert(left.parent==gun,'support rejected by mixed native/VR anchor')
        local wrist=compose(compose(left.bones.l_wrist_jnt,left.relative),gun.world)
        near(wrist.Translation.X,602.5); near(wrist.Translation.Y,695.669872981)
        near(wrist.Rotation.Yaw,-30)
        local finger=compose(compose(left.bones.l_index_01_jnt,left.relative),gun.world)
        near(finger.Translation.X,605.098076211); near(finger.Translation.Y,697.169872981)
        near(finger.Rotation.Yaw,0)
        -- UObjectHook restores the weapon on the next game frame. The mount
        -- must be identical when that restore happens before the callback.
        local before=left.relative
        gun.world=source.bones.r_weapon; tick()
        near(left.relative.Translation.X,before.Translation.X)
        near(left.relative.Translation.Y,before.Translation.Y)
        near(left.relative.Rotation.Yaw,before.Rotation.Yaw); clean()
    ''')


def test_support_refreshes_native_pose_while_latched(lua):
    lua.execute(r'''
        armed(); physical_right=vec(0.05,1,0)
        source.bones.l_index_01_jnt=tr(3); tick(4)
        source.bones.l_index_01_jnt=tr(9,2,0,35); tick()
        near(left.bones.l_index_01_jnt.Translation.X,9)
        near(left.bones.l_index_01_jnt.Rotation.Yaw,35); clean()
    ''')


@pytest.mark.parametrize("transition", [
    "put('weapon',nil)", "gun.visible=false", "anim.bIsReloading=true", "pawn.knife=true",
])
def test_support_transition_clears_latch_and_requires_full_dwell(lua, transition):
    lua.execute("armed(); physical_right=vec(0.05,1,0); tick(4); assert(left.parent==gun)")
    lua.execute(transition)
    lua.execute(r'''
        tick(); local state=read('pistol')
        assert(not state or not state.supporting,'stale support latch')
        assert(not state or (state.near_time==0 and state.far_time==0))
        anim.bIsReloading=false; pawn.knife=false; gun.visible=true
        put('weapon',gun); put('attached_weapon',gun); right.parent=gun
        put('pistol',state or {mesh=gun,effects={}})
        tick(); assert(left.parent==lc,'support reacquired without a new dwell')
        tick(3); assert(left.parent==gun); clean()
    ''')


@pytest.mark.parametrize("failure", ["left.fail_attach=true", "source.bones.l_wrist_jnt=tr(80)"])
def test_failed_support_mount_clears_latch_before_retry(lua, failure):
    lua.execute("armed(); physical_right=vec(0.05,1,0)")
    lua.execute(failure)
    lua.execute(r'''
        tick(3); assert(not read('pistol').supporting,'failed mount kept latch')
        left.fail_attach=false; source.bones.l_wrist_jnt=tr()
        tick(); assert(left.parent==lc,'retry skipped contact dwell')
        tick(3); assert(left.parent==gun); clean()
    ''')


@pytest.mark.parametrize("failure", ["right.parent=rc", "rc.invalid=true", "lc.invalid=true",
    "right.fail_attach=true; put('attached_weapon',nil); right.parent=rc; source.bones.r_wrist_jnt=tr(100)"])
def test_support_requires_ready_right_grip_and_valid_controllers(lua, failure):
    lua.execute(r'''
        armed(); physical_right=vec(0.05,1,0)
        read('pistol').supporting=true; read('pistol').near_time=0.15
        put('grip_pose_cache',{[gun:get_address()]={bones={},animation={},relative=tr()}})
    ''')
    lua.execute(failure)
    lua.execute(r'''
        tick(); assert(left.parent==lc); assert(not read('pistol').supporting)
        for _,s in ipairs(warnings) do assert(s:find('Native grip is outside weapon reach',1,true)) end
    ''')


def test_tracking_loss_releases_immediately_and_does_not_reuse_dwell(lua):
    lua.execute(r'''
        armed(); physical_right=vec(0.05,1,0); tick(4)
        using_controllers=false; tick()
        assert(left.parent==lc and not read('pistol').supporting)
        using_controllers=true; tick(); assert(left.parent==lc)
        tick(3); assert(left.parent==gun); clean()
    ''')


@pytest.mark.parametrize("lost", ["source.invalid=true", "pawn.invalid=true", "right.invalid=true"])
def test_missing_pose_source_or_right_hand_cannot_leave_support_mounted(lua, lost):
    lua.execute("armed(); physical_right=vec(0.05,1,0); tick(4); assert(left.parent==gun)")
    lua.execute(lost)
    lua.execute(r'''
        tick(); assert(left.parent==lc,'unavailable hand/source left support mounted')
        assert(not read('pistol').supporting and read('left_pose').support_weapon==nil)
        near(left.bones.l_index_01_jnt.Translation.X,2); clean()
    ''')


@pytest.mark.parametrize("failure", ["lc.invalid=true", "left.fail_attach=true"])
def test_release_without_controller_detaches_hides_and_recovers(lua, failure):
    lua.execute("armed(); physical_right=vec(0.05,1,0); tick(4); assert(left.parent==gun)")
    lua.execute(failure)
    lua.execute(r'''
        physical_right=vec(1,1,0); tick(9)
        assert(left.parent==nil and not left.visible,'failed release left a floating gun hand')
        near(left.bones.l_index_01_jnt.Translation.X,2)
        assert(not read('pistol').supporting)
        lc=component('ReplacementLC'); left.fail_attach=false
        tick(); assert(left.parent==lc and left.visible)
        physical_right=vec(0.05,1,0); tick(4); assert(left.parent==gun)
        lc.invalid=true; pose.reset()
        assert(left.parent==nil and not left.visible,'reset retained stale weapon parent'); clean()
    ''')


def test_partial_support_bone_write_restores_every_original_even_if_detach_fails(lua):
    lua.execute(r'''
        armed(); physical_right=vec(0.05,1,0)
        source.bones.l_wrist_jnt=tr(5); source.bones.l_index_01_jnt=tr(8)
        table.insert(read('left_pose').original_bones,{name=fname('l_middle_01_jnt'),transform=tr(4)})
        left.bones.l_wrist_jnt=tr(); left.bones.l_index_01_jnt=tr(2); left.bones.l_middle_01_jnt=tr(4)
        local write=left.SetBoneTransformByName
        function left:SetBoneTransformByName(n,t,space)
            if n:to_string()=='l_middle_01_jnt' and not self.failed_once then
                self.failed_once=true; self.fail_attach=true; error('injected bone write failure')
            end
            write(self,n,t,space)
        end
        tick(3)
        near(left.bones.l_wrist_jnt.Translation.X,0)
        near(left.bones.l_index_01_jnt.Translation.X,2)
        near(left.bones.l_middle_01_jnt.Translation.X,4)
        assert(read('left_pose').support_weapon==nil and not read('pistol').supporting)
        assert(#warnings==1 and warnings[1]:find('injected bone write failure',1,true))
        left.fail_attach=false; physical_right=vec(1,1,0); tick()
        assert(left.parent==lc)
        pose.reset(); pose.reset()
        near(left.bones.l_index_01_jnt.Translation.X,2)
    ''')


def test_contact_defaults_allow_separated_grip_origins_without_grip_button(lua):
    lua.execute(r'''
        armed(); physical_right=vec(0.13,1,0) -- grip origins need not coincide to touch hands
        assert(read('input').grip==0); tick(4); assert(left.parent==gun)
        physical_right=vec(0.4,1,0); tick(9); assert(left.parent==lc); clean()
    ''')


def test_contact_offsets_rotate_with_each_grip_pose(lua):
    lua.execute(r'''
        armed(); local cfg=pose.support_contact
        assert(cfg,'contact geometry must be configurable')
        cfg.acquire_cm=3; cfg.release_cm=8
        cfg.left_offset_m={x=0.05,y=0,z=0}; cfg.right_offset_m={x=-0.05,y=0,z=0}
        -- 90 degrees around tracking Z: inward offsets close a 10 cm Y gap.
        physical_left_rotation={x=0,y=0,z=math.sqrt(0.5),w=math.sqrt(0.5)}
        physical_right_rotation=physical_left_rotation
        physical_right=vec(0,1.10,0); tick(4); assert(left.parent==gun)
        physical_left_rotation={x=0,y=0,z=0,w=1}; physical_right_rotation=physical_left_rotation
        tick(9); assert(left.parent==lc); clean()
    ''')
