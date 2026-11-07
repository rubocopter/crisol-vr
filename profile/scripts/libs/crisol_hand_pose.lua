local utils = require('libs/uevr_utils')
local hands = require('libs/hands')
local controllers = require('libs/controllers')
local animation = require('libs/animation')
local M = {}
local weapon, attached_weapon, source, mathlib, hit
local fingers = {'thumb', 'index', 'middle', 'ring', 'pinky'}
local errors = {}
local saved_tick = nil
local grip_cache = {}
local grip_pose_cache = {}
local tracking = json.load_file('crisol_weapon_tracking.json') or {}
local trigger_poses = json.load_file('crisol_trigger_pose.json') or {}
local projection_original={}
local player, native_anim, native_mode, right_recovery
local weapon_bone, left_wrist, no_socket
local pistol
local hand_effects = {}
local magazine_original = {}
local touch_handles = {}
-- These two unused UEVR actions carry left trigger and stick touch in this
-- profile. Its D-pad uses head gestures, so it does not use thumbrest actions.
local touch_actions = {
    trigger='ThumbrestTouchLeft',
    stick='ThumbrestTouchRight',
    square='BButtonTouchRight',
    triangle='BButtonTouchLeft',
}
-- ECRPlayerState, as registered by CRPlayerCharacter in the shipping build.
local PLAYER_ABSORB, PLAYER_INTERACTING, PLAYER_HEALING = 1,3,6
local scripted_montage_prefixes = {
    'ga_absorb', 'ga_stairs_', 'ga_wagon_', 'ga_moveobject_', 'ga_movetruck_',
    'ga_syringe_', 'ga_healing_', 'ga_mov_climb', 'ga_mov_crawlclimb',
    'ga_mov_narrowsection', 'ga_newliftgate_', 'ga_boat_', 'ga_lever_',
    'syringe_anim_', 'cine_', 'gabriel_cinematic_',
}
local scripted_interactable_names = {
    'wagon', 'moveobject', 'movetruck', 'pushable', 'ladder', 'placestairs', 'gabrielnarrow',
}
local left_pose={}
local input={grip=0,left_trigger=0,right_trigger=false}

utils.registerOnInputGetStateCallback(function(_,index,state)
    if index~=0 then return end
    input.grip=utils.isButtonPressed(state, XINPUT_GAMEPAD_LEFT_SHOULDER) and 1 or 0
    input.left_trigger=state.Gamepad.bLeftTrigger/255
    input.right_trigger=state.Gamepad.bRightTrigger>100
end)
local function warn(err)
    err = tostring(err)
    if not errors[err] then errors[err] = true; uevr.params.functions.log_warn('[Crisol hand pose] ' .. err) end
end
local function valid(obj) return utils.getValid(obj) ~= nil end
local function vector_sub(a,b) return utils.vector(a.X-b.X,a.Y-b.Y,a.Z-b.Z) end
local function vector_add(a,b) return utils.vector(a.X+b.X,a.Y+b.Y,a.Z+b.Z) end
local function scale(v,k) return utils.vector(v.X*k,v.Y*k,v.Z*k) end
local function dot(a,b) return a.X*b.X+a.Y*b.Y+a.Z*b.Z end
local function perpendicular(v,axis) return vector_sub(v,scale(axis,dot(v,axis))) end
local function normalize(a)
    local n = math.sqrt(a.X*a.X+a.Y*a.Y+a.Z*a.Z)
    assert(n > 0.001, 'Degenerate finger axis')
    return utils.vector(a.X/n,a.Y/n,a.Z/n)
end
local function cross(a,b) return utils.vector(a.Y*b.Z-a.Z*b.Y,a.Z*b.X-a.X*b.Z,a.X*b.Y-a.Y*b.X) end
local function angles(r) return {r.Pitch,r.Yaw,r.Roll} end
local function world_projection(component)
    if not valid(component) then return end
    if projection_original[component]==nil then
        projection_original[component]={fov=component.UseDesiredFOV,first=component.FirstPersonPrimitiveType}
    end
    if component.UseDesiredFOV~=nil then component.UseDesiredFOV=false end
    if component.FirstPersonPrimitiveType~=nil and component.FirstPersonPrimitiveType~=0 then
        component:SetFirstPersonPrimitiveType(0)
    end
end

local function build_left_animation(mesh)
    left_pose={mesh=mesh,grip={alpha=0,joints={}},trigger={alpha=0,joints={}},thumb={alpha=0,joints={}}}
    local wrist = mesh:GetBoneTransformByName(utils.fname_from_string('l_wrist_jnt'),1).Translation
    local dorsal = mesh:GetBoneTransformByName(utils.fname_from_string('l_wrist_up_jnt'),1).Translation
    local palm_in = normalize(vector_sub(wrist,dorsal))
    local index_base = mesh:GetBoneTransformByName(utils.fname_from_string('l_index_01_jnt'),1).Translation
    for _, finger in ipairs(fingers) do
        local first = mesh:GetBoneTransformByName(utils.fname_from_string('l_'..finger..'_01_jnt'),1).Translation
        local second = mesh:GetBoneTransformByName(utils.fname_from_string('l_'..finger..'_02_jnt'),1).Translation
        local direction = normalize(vector_sub(second,first))
        local bend_towards,group,amounts = palm_in,left_pose.grip,{58,75,42}
        if finger=='thumb' then
            bend_towards,group,amounts = normalize(vector_sub(index_base,first)),left_pose.thumb,{17,20,12}
        elseif finger=='index' then
            group,amounts = left_pose.trigger,{45,60,35}
        end
        local axis = normalize(cross(direction,bend_towards))
        for joint=1,3 do
            local name = string.format('l_%s_%02d_jnt',finger,joint)
            local bone = utils.fname_from_string(name)
            local local_rotation, parent_transform = animation.getBoneSpaceLocalRotator(mesh,bone,1)
            local local_axis = mathlib:InverseTransformDirection(parent_transform,axis)
            local curl=mathlib:RotatorFromAxisAndAngle(local_axis,amounts[joint])
            group.joints[#group.joints+1]={bone=bone,open=local_rotation,closed=mathlib:ComposeRotators(local_rotation,curl)}
        end
    end
end

local function update_left_animation(delta,pose)
    if not valid(left_pose.mesh) then return end
    local function update(group,target)
        if math.abs(group.alpha-target)<0.002 then return end
        local step=math.min(1,delta/0.075)
        group.alpha=group.alpha+(target-group.alpha)*step
        for _,joint in ipairs(group.joints) do
            local rotation=mathlib:RLerp(joint.open,joint.closed,group.alpha,true)
            animation.setBoneSpaceLocalRotator(left_pose.mesh,joint.bone,rotation,1)
        end
    end
    if pose=='reload' then
        update(left_pose.grip,0.64)
        update(left_pose.trigger,0.54)
        update(left_pose.thumb,0.34)
        return
    elseif pose=='support' then
        update(left_pose.grip,0.85)
        update(left_pose.trigger,0.64)
        update(left_pose.thumb,0.58)
        return
    end
    local vr = uevr.params.vr
    local left = vr.get_left_joystick_source()
    local function touched(name)
        local handle = touch_handles[name]
        return handle ~= nil and handle ~= 0 and vr.is_action_active(handle,left)
    end
    update(left_pose.grip,input.grip==1 and 1 or 0.18)
    update(left_pose.trigger,math.max(input.left_trigger,touched('trigger') and 0.36 or 0.12))
    local thumb_resting = touched('stick') or touched('square') or touched('triangle')
    update(left_pose.thumb,thumb_resting and 0.75 or (input.grip==1 and 0.36 or 0.14))
end

function M.setup(pawn)
    player,source = pawn,pawn.PlayerArms
    mathlib = utils.find_default_instance('Class /Script/Engine.KismetMathLibrary')
    hit = utils.get_struct_object('ScriptStruct /Script/Engine.HitResult')
    saved_tick = source.VisibilityBasedAnimTickOption
    source.VisibilityBasedAnimTickOption = 0 -- refresh the hidden native mesh for live finger poses
    world_projection(source)
    native_anim=source:GetAnimInstance()
    native_mode,right_recovery = nil,nil
    weapon_bone = utils.fname_from_string('r_weapon')
    left_wrist = utils.fname_from_string('l_wrist_jnt')
    no_socket = utils.fname_from_string('None')
    for name,action in pairs(touch_actions) do
        local ok,handle = pcall(uevr.params.vr.get_action_handle,'/actions/default/in/'..action)
        touch_handles[name] = ok and handle or nil
    end
    hands.setAutoHandleInput(false)
    source:SetVisibility(false,false)
    build_left_animation(hands.getHandComponent(0,'Arms'))
    local left = hands.getHandComponent(0,'Arms')
    local a = left:GetBoneTransformByName(utils.fname_from_string('l_wrist_jnt'),1).Translation
    local b = left:GetBoneTransformByName(utils.fname_from_string('l_middle_01_jnt'),1).Translation
    local palm = utils.vector((a.X+b.X)/2,(a.Y+b.Y)/2,(a.Z+b.Z)/2)
    local rotation = left.RelativeRotation
    local p = mathlib:RotateAngleAxis(palm,rotation.Yaw,utils.vector(0,0,1))
    utils.set_component_relative_transform(left,{-p.X,-p.Y,-p.Z},{Pitch=rotation.Pitch,Yaw=rotation.Yaw,Roll=rotation.Roll})
    left_pose.wrist_inverse=mathlib:InvertTransform(left:GetBoneTransformByName(left_wrist,1))
    left_pose.free=mathlib:MakeTransform(left.RelativeLocation,left.RelativeRotation,left.RelativeScale3D)
    weapon, attached_weapon = nil,nil
end

local function classify_action()
    if not valid(native_anim) then native_anim=source:GetAnimInstance() end
    local montage = valid(native_anim) and native_anim:GetCurrentActiveMontage()
    local path = valid(montage) and montage:get_full_name():lower() or ''
    local name = path:match('%.([^%.]+)$') or ''
    if path:find('/divineknife/',1,true) or name:find('^ga_dk_')
        or (player.GetIsUsingKnife and player:GetIsUsingKnife()==true) then
        return 'native','knife'
    end
    for _,prefix in ipairs(scripted_montage_prefixes) do
        if name:sub(1,#prefix)==prefix then return 'native',name end
    end
    if name:find('opendoor',1,true) or name:find('instakill',1,true) or name:find('struggle',1,true) then
        return 'native',name
    end

    -- The absorb loop is an animation state, so GetCurrentActiveMontage can be nil.
    local state = player.GetPlayerState and player:GetPlayerState()
    if state==PLAYER_ABSORB then return 'native','absorb' end
    if state==PLAYER_HEALING then return 'native','healing' end

    local interaction = player.GetActualInteractuable and player:GetActualInteractuable()
    if valid(interaction) and interaction.bStartAbsorb==true then return 'native','absorb' end
    if state==PLAYER_INTERACTING then
        if valid(interaction) then
            local class = interaction:get_full_name():lower():match('^(%S+)') or ''
            for _,kind in ipairs(scripted_interactable_names) do
                if class:find(kind,1,true) then return 'native',kind end
            end
        end
        if player.GetActualInteractuablePlaceUsing then
            local ok,place = pcall(function() return player:GetActualInteractuablePlaceUsing() end)
            if ok and type(place)=='userdata' and valid(place) then return 'native','scripted interaction' end
        end
    end
    if player.GetIsCharacterOnCinematicMode and player:GetIsCharacterOnCinematicMode()==true then
        return 'native','cinematic'
    end

    if (valid(native_anim) and native_anim.bIsReloading==true)
        or name:find('reload',1,true) or name:find('loopbreaker',1,true) then
        return 'reload','weapon reload'
    end
end

local function update_action_visibility(mode,reason)
    local show_source = mode=='native'
    if show_source and (native_mode~=mode or source.bRenderInMainPass==false) then
        source:SetRenderInMainPass(true)
    end
    if native_mode~=mode then
        if show_source then
            hands.hideHands(true)
            right_recovery=nil
        else
            local left=hands.getHandComponent(0,'Arms')
            if valid(left) then left:SetVisibility(true,false) end
            if native_mode=='native' then right_recovery={elapsed=0,ready=false} end
        end
        native_mode=mode
        uevr.params.functions.log_info('[Crisol hands] '..(reason or 'Returned to Sense hands'))
    end
    if source:IsVisible()~=show_source then source:SetVisibility(show_source,false) end
end

local function set_left_parent(parent,transform)
    local mesh=left_pose.mesh
    if not valid(mesh) or not valid(parent) then return false end
    if mesh:GetAttachParent()~=parent then
        if not mesh:K2_AttachToComponent(parent,no_socket,1,1,1,false) then return false end
    end
    mesh:K2_SetRelativeTransform(transform,false,hit,false)
    return true
end

local function release_left()
    if left_pose.mounted and set_left_parent(controllers.getController(0,true),left_pose.free) then
        left_pose.mounted=false
    end
end

local function update_left_mount(mode,weapon_ready,delta)
    if weapon_ready and mode=='reload' then
        -- Keep the wrist cut used for ordinary Sense tracking. Copy only the
        -- native wrist's motion relative to the weapon, never the arm mesh.
        local native=source:GetSocketTransform(left_wrist,0)
        local anchor=source:GetSocketTransform(weapon_bone,0)
        local wrist=mathlib:MakeRelativeTransform(native,anchor)
        local rotation=mathlib:TransformRotation(wrist,utils.rotator(0,0,0))
        wrist=mathlib:MakeTransform(wrist.Translation,rotation,utils.vector(1,1,1))
        local relative=mathlib:ComposeTransforms(left_pose.wrist_inverse,wrist)
        if set_left_parent(weapon,relative) then
            left_pose.mounted=true
            if pistol then pistol.near_time,pistol.supporting=0,false end
            return 'reload'
        end
    elseif weapon_ready and pistol and pistol.mesh==weapon then
        local d=pistol.distance
        pistol.distance_age=(pistol.distance_age or 0)+delta
        if not d or pistol.distance_age>0.22 or d>14 then
            pistol.near_time,pistol.supporting=0,false
        elseif d<=9 and not pistol.supporting then
            pistol.near_time=(pistol.near_time or 0)+delta
            pistol.supporting=pistol.near_time>=0.09
        elseif not pistol.supporting then
            pistol.near_time=0
        end
        if pistol.supporting and set_left_parent(weapon,pistol.support_transform) then
            left_pose.mounted=true
            return 'support'
        end
    end
    release_left()
end

local function original_effect(component)
    return {
        component=component,
        parent=component:GetAttachParent(),
        socket=component:GetAttachSocketName(),
        relative=mathlib:MakeTransform(component.RelativeLocation,component.RelativeRotation,component.RelativeScale3D),
    }
end

local function mount_effect(entry,target,socket,relative)
    local component=entry.component
    if not valid(component) or not valid(target) then return end
    if component:GetAttachParent()~=target then
        -- Keep authored effects that have been moved by the game recoverable.
        local original=original_effect(component)
        if not component:K2_AttachToComponent(target,socket,1,1,1,false) then return end
        entry.parent,entry.socket,entry.relative=original.parent,original.socket,original.relative
        entry.target=target
    end
    component:K2_SetRelativeTransform(relative,false,hit,false)
end

local function restore_effects(entries)
    for _,entry in ipairs(entries) do
        local component=entry.component
        local parent=valid(component) and component:GetAttachParent()
        if entry.target and valid(component)
            and (parent==entry.target or (not valid(parent) and not valid(entry.target))) then
            if valid(entry.parent) then
                if component:K2_AttachToComponent(entry.parent,entry.socket,1,1,1,false) then
                    component:K2_SetRelativeTransform(entry.relative,false,hit,false)
                    entry.target=nil
                end
            else
                component:K2_DetachFromComponent(1,1,1,false)
                component:K2_SetWorldTransform(entry.relative,false,hit,false)
                entry.target=nil
            end
        else
            entry.target=nil
        end
    end
end

local function mount_hand_effects()
    local left=left_pose.mesh
    if not valid(left) then return end
    local vat=utils.fname_from_string('VAT_reload_socket')
    if not source:DoesSocketExist(vat) then return end
    if #hand_effects==0 and player.K2_GetComponentsByClass then
        local class=utils.get_class('Class /Script/Niagara.NiagaraComponent')
        if not class then return end
        local effects={DamageState_Start=true,DamageState_Loop=true,DamageState_End=true}
        for _,component in ipairs(player:K2_GetComponentsByClass(class) or {}) do
            if effects[component:get_fname():to_string()] and component:GetAttachParent()==source
                and component:GetAttachSocketName():to_string():lower()=='vat_reload_socket' then
                hand_effects[#hand_effects+1]=original_effect(component)
            end
        end
    end
    if #hand_effects==0 then return end
    local vat_in_wrist=mathlib:MakeRelativeTransform(source:GetSocketTransform(vat,0),source:GetSocketTransform(left_wrist,0))
    for _,entry in ipairs(hand_effects) do
        if valid(entry.component) and entry.component:GetAttachParent()==source then
            mount_effect(entry,left,left_wrist,mathlib:ComposeTransforms(entry.relative,vat_in_wrist))
        end
    end
end

local function sync_pistol_effects(active)
    if not pistol or not pistol.to_controller then return end
    local right=controllers.getController(1,true)
    if not valid(right) then return end
    for _,entry in ipairs(pistol.effects) do
        if valid(entry.component) then
            local component=entry.component
            if component:GetAttachParent()~=right then
                local original=original_effect(component)
                entry.parent,entry.socket,entry.relative=original.parent,original.socket,original.relative
                entry.target=nil
            end
            if active or not entry.target then
                -- The actual gun is restored to its flat pose between stereo
                -- renders. The Sense component stays in VR space for Niagara's
                -- simulation tick as well as for local-space emitters.
                local relative
                if entry.parent==pistol.mesh then
                    relative=mathlib:ComposeTransforms(entry.relative,pistol.mesh:GetSocketTransform(entry.socket,2))
                else
                    local native=entry.relative
                    if valid(entry.parent) then
                        native=mathlib:ComposeTransforms(native,entry.parent:GetSocketTransform(entry.socket,0))
                    end
                    relative=mathlib:MakeRelativeTransform(native,source:GetSocketTransform(weapon_bone,0))
                end
                mount_effect(entry,right,no_socket,mathlib:ComposeTransforms(relative,pistol.to_controller))
            end
        end
    end
end

local function rotate_quat(q,v,inverse)
    local x,y,z,w=q.x,q.y,q.z,q.w
    if inverse then x,y,z=-x,-y,-z end
    local tx,ty,tz=2*(y*v.z-z*v.y),2*(z*v.x-x*v.z),2*(x*v.y-y*v.x)
    return {x=v.x+w*tx+y*tz-z*ty,y=v.y+w*ty+z*tx-x*tz,z=v.z+w*tz+x*ty-y*tx}
end

local function match_left_palm(anchor)
    local owner=weapon:GetOwner()
    local records=tracking[owner:get_full_name():match('^(%S+)')]
    if not records or not records.Mesh then return end
    local function native_location(name)
        return mathlib:MakeRelativeTransform(source:GetSocketTransform(utils.fname_from_string(name),0),anchor).Translation
    end
    local wrist=native_location('r_wrist_jnt')
    local forward=vector_sub(native_location('r_middle_01_jnt'),wrist)
    local up=vector_sub(native_location('r_wrist_up_jnt'),wrist)
    local function mirrored_controller_vector(v)
        -- UObjectHook applies inverse(rotation_offset) to the aim pose.
        local r=rotate_quat(records.Mesh.rotation_offset,{x=-v.Y,y=-v.Z,z=v.X},true)
        return utils.vector(r.z,r.x,-r.y) -- GLM->UE, then mirror sagittal Y
    end
    local target=mathlib:MakeRotFromXZ(mirrored_controller_vector(forward),mirrored_controller_vector(up))
    local left=hands.getHandComponent(0,'Arms')
    local function left_location(name) return left:GetBoneTransformByName(utils.fname_from_string(name),1).Translation end
    local w=left_location('l_wrist_jnt')
    local middle=left_location('l_middle_01_jnt')
    local frame=mathlib:MakeRotFromXZ(vector_sub(middle,w),vector_sub(left_location('l_wrist_up_jnt'),w))
    local inverse=mathlib:InvertTransform(mathlib:MakeTransform(utils.vector(0,0,0),frame,utils.vector(1,1,1)))
    local rotation=mathlib:ComposeRotators(mathlib:TransformRotation(inverse,utils.rotator(0,0,0)),target)
    local orientation=mathlib:MakeTransform(utils.vector(0,0,0),rotation,utils.vector(1,1,1))
    local palm=utils.vector((w.X+middle.X)/2,(w.Y+middle.Y)/2,(w.Z+middle.Z)/2)
    local p=mathlib:TransformLocation(orientation,palm)
    left_pose.free=mathlib:MakeTransform(scale(p,-1),rotation,left.RelativeScale3D)
    if not left_pose.mounted then left:K2_SetRelativeTransform(left_pose.free,false,hit,false) end
    json.dump_file('crisol_left_alignment.json',{rotation=angles(rotation),target=angles(target),location={-p.X,-p.Y,-p.Z}},4)
    uevr.params.functions.log_info(string.format('[Crisol hand pose] Mirrored right palm orientation for left Sense: %.2f,%.2f,%.2f',rotation.Pitch,rotation.Yaw,rotation.Roll))
end

local function center_weapon_palm(palm)
    local owner=weapon:GetOwner()
    local cls=owner:get_full_name():match('^(%S+)')
    if not tracking[cls] or not tracking[cls].Mesh then return end
    world_projection(weapon)
    local state=UEVR_UObjectHook.get_or_add_motion_controller_state(weapon)
    if state then
        state:set_location_offset(Vector3f.new(-palm.Y,-palm.Z,palm.X)) -- Unreal local -> UEVR/GLM local
    end

    -- Leave the reservoir and reload particles in their original hierarchy.
    -- Match the reservoir's projection to the gun without tracking it separately.
    local mag_name=cls=='CRWDivinePistolNew_BP_C' and 'LiquidMag'
        or cls=='CRWDMachineGun_BP_C' and 'LiquidMag_Test'
    if mag_name and owner.K2_GetComponentsByClass then
        local class=utils.get_class('Class /Script/Engine.StaticMeshComponent')
        for _,component in ipairs(owner:K2_GetComponentsByClass(class) or {}) do
            local name=component:get_fname():to_string()
            if name==mag_name or (mag_name=='LiquidMag' and name=='LiquidMag1') then
                world_projection(component)
            end
        end
    end
    uevr.params.functions.log_info(string.format('[Crisol hand pose] Centered %s palm at Sense grip: %.2f,%.2f,%.2f',cls,palm.X,palm.Y,palm.Z))
end

local function setup_pistol(palm,anchor)
    local owner=weapon:GetOwner()
    if not owner:get_full_name():find('^CRWDivinePistolNew_BP_C ') then return end
    if pistol and pistol.mesh==weapon then return end
    if pistol then restore_effects(pistol.effects) end
    local function point(name) return weapon:GetSocketTransform(utils.fname_from_string(name),2).Translation end
    local barrel=point('DP_barrel')
    local forward=normalize(vector_sub(point('Muzzle'),barrel))
    local down=normalize(perpendicular(vector_sub(point('DP_trigger'),barrel),forward))
    local side=cross(forward,down)
    local right_dorsal=mathlib:InverseTransformLocation(anchor,source:GetSocketTransform(utils.fname_from_string('r_wrist_up_jnt'),0).Translation)
    local outward=scale(side,dot(vector_sub(right_dorsal,palm),side)>0 and -1 or 1)
    local center=vector_add(palm,vector_add(scale(outward,3.1),vector_add(scale(down,1.6),scale(forward,1.5))))

    local left=left_pose.mesh
    local wrist=left:GetBoneTransformByName(left_wrist,1).Translation
    local finger=left:GetBoneTransformByName(utils.fname_from_string('l_middle_01_jnt'),1).Translation
    local dorsal=left:GetBoneTransformByName(utils.fname_from_string('l_wrist_up_jnt'),1).Translation
    local hand_frame=mathlib:MakeRotFromXZ(vector_sub(finger,wrist),vector_sub(dorsal,wrist))
    local reach=vector_add(scale(forward,0.8),scale(outward,-0.6))
    local pose_frame=mathlib:MakeRotFromXZ(reach,vector_add(outward,scale(down,0.35)))
    local origin=utils.vector(0,0,0)
    local unit=utils.vector(1,1,1)
    local inverse=mathlib:InvertTransform(mathlib:MakeTransform(origin,hand_frame,unit))
    local rotation=mathlib:ComposeRotators(mathlib:TransformRotation(inverse,utils.rotator(0,0,0)),pose_frame)
    local offset=mathlib:TransformLocation(mathlib:MakeTransform(origin,rotation,unit),scale(vector_add(wrist,finger),0.5))
    pistol={mesh=weapon,palm=palm,support_center=center,support_transform=mathlib:MakeTransform(vector_sub(center,offset),rotation,unit),effects={}}

    for _,name in ipairs({'GetStartReloadComponent','GetLoopReloadComponent','GetEndReloadComponent'}) do
        if owner[name] then
            local component=owner[name](owner)
            if valid(component) then pistol.effects[#pistol.effects+1]=original_effect(component) end
        end
    end

    -- The inner blood mesh mounts to MagSocket; recess it toward the barrel
    -- along the depth of the magazine, in socket space.
    local socket=utils.fname_from_string('MagSocket')
    if owner.K2_GetComponentsByClass and weapon:DoesSocketExist(socket) then
        local class=utils.get_class('Class /Script/Engine.StaticMeshComponent')
        local mount=weapon:GetSocketTransform(socket,2)
        local inward=normalize(perpendicular(vector_sub(barrel,mount.Translation),forward))
        local offset=mathlib:InverseTransformDirection(mount,scale(inward,1.0))
        for _,component in ipairs(owner:K2_GetComponentsByClass(class) or {}) do
            if component:get_fname():to_string()=='LiquidMag' and component:GetAttachParent()==weapon
                and component:GetAttachSocketName():to_string()=='MagSocket' and not magazine_original[component] then
                local location=component.RelativeLocation
                local original=utils.vector(location.X,location.Y,location.Z)
                component:K2_SetRelativeLocation(vector_add(original,offset),false,hit,false)
                magazine_original[component]=original
                break
            end
        end
    end
end

utils.registerPostCalculateStereoViewCallback(function(_,view_index)
    if not pistol or native_mode=='native' or (view_index+1)%2~=0
        or not uevr.params.vr.is_using_controllers() then return end
    local ok,err=pcall(function()
        if pistol.mesh~=attached_weapon or not valid(pistol.mesh) then return end
        local left=controllers.getControllerLocation(0)
        local right=controllers.getController(1,true)
        if not left or not valid(right) then return end
        local actual=pistol.mesh:K2_GetComponentToWorld()
        if not pistol.to_controller then
            local palm_world=mathlib:TransformLocation(actual,pistol.palm)
            local gap=vector_sub(right:K2_GetComponentLocation(),palm_world)
            if dot(gap,gap)>100 then return end
            pistol.to_controller=mathlib:MakeRelativeTransform(actual,right:K2_GetComponentToWorld())
        end
        local target=mathlib:TransformLocation(actual,pistol.support_center)
        local gap=vector_sub(left,target)
        pistol.distance=math.sqrt(dot(gap,gap))
        pistol.distance_age=0
    end)
    if not ok then warn(err) end
end)

local function align_pistol_trigger(mesh, relative, trigger_pose)
    local function add(a,b) return utils.vector(a.X+b.X,a.Y+b.Y,a.Z+b.Z) end
    local function scale(v,k) return utils.vector(v.X*k,v.Y*k,v.Z*k) end
    local function dot(a,b) return a.X*b.X+a.Y*b.Y+a.Z*b.Z end
    local function length(v) return math.sqrt(dot(v,v)) end
    local function perpendicular(v,axis) return vector_sub(v,scale(axis,dot(v,axis))) end
    local function weapon_bone(name) return weapon:GetSocketTransform(utils.fname_from_string(name),2).Translation end
    local pivot,barrel=weapon_bone('DP_trigger'),weapon_bone('DP_barrel')
    local forward=normalize(vector_sub(weapon_bone('Muzzle'),barrel))
    local down=normalize(perpendicular(vector_sub(pivot,barrel),forward))
    local side=cross(forward,down)
    -- The trigger bone is at the hinge. Target the distal joint just in front
    -- of the blade, on the near side so the fingertip pad can wrap around it.
    local contact=add(pivot,add(scale(forward,0.90),add(scale(down,0.95),scale(side,1.10))))
    local target=mathlib:InverseTransformLocation(relative,contact)
    local names,bones={},{}
    for i=1,3 do
        names[i]=string.format('r_index_%02d_jnt',i)
        bones[i]=utils.fname_from_string(names[i])
    end
    local function apply(pose)
        for i=1,3 do
            local r=pose[names[i]]
            animation.setBoneSpaceLocalRotator(mesh,bones[i],utils.rotator(r[1],r[2],r[3]),1)
        end
    end
    local function location(i) return mesh:GetBoneTransformByName(bones[i],1).Translation end
    local function turn(i,from,to)
        local a,b=normalize(from),normalize(to)
        local axis=cross(a,b)
        local sine=length(axis)
        if sine<0.0001 then return end
        local delta=mathlib:RotatorFromAxisAndAngle(scale(axis,1/sine),math.deg(math.atan(sine,dot(a,b))))
        local rotation=mathlib:TransformRotation(mesh:GetBoneTransformByName(bones[i],1),utils.rotator(0,0,0))
        mesh:SetBoneRotationByName(bones[i],mathlib:ComposeRotators(rotation,delta),1)
    end
    apply(trigger_pose.on)
    local a,b,c=location(1),location(2),location(3)
    local upper,lower=length(vector_sub(b,a)),length(vector_sub(c,b))
    local direction=normalize(vector_sub(target,a))
    local reach=math.min(upper+lower-0.01,math.max(math.abs(upper-lower)+0.01,length(vector_sub(target,a))))
    local along=(upper*upper+reach*reach-lower*lower)/(2*reach)
    local outward=normalize(perpendicular(vector_sub(b,a),direction))
    local middle=add(a,add(scale(direction,along),scale(outward,math.sqrt(math.max(0,upper*upper-along*along)))))
    local distal=mathlib:TransformRotation(mesh:GetBoneTransformByName(bones[3],1),utils.rotator(0,0,0))
    turn(1,vector_sub(b,a),vector_sub(middle,a))
    turn(2,vector_sub(location(3),location(2)),vector_sub(add(a,scale(direction,reach)),location(2)))
    mesh:SetBoneRotationByName(bones[3],distal,1)
    local corrected={}
    for i=1,3 do corrected[names[i]]=angles(animation.getBoneSpaceLocalRotator(mesh,bones[i],1)) end
    local error_cm=length(vector_sub(location(3),target))
    apply(trigger_pose.off)
    uevr.params.functions.log_info(string.format('[Crisol hand pose] Pistol index contact residual: %.3f cm',error_cm))
    return corrected
end

local function capture_right_grip(mesh,anchor,relative)
    -- Preserve animated joint positions and scales as well as rotations. Ref-pose
    -- finger translations differ from the game's grip by several centimetres.
    local wrist_name=utils.fname_from_string('r_wrist_jnt')
    local inverse=mathlib:InvertTransform(relative)
    for index=0,mesh:GetNumBones()-1 do
        local bone=mesh:GetBoneName(index)
        if bone:to_string()=='r_wrist_jnt' or mesh:BoneIsChildOf(bone,wrist_name) then
            local native=mathlib:MakeRelativeTransform(source:GetSocketTransform(bone,0),anchor)
            mesh:SetBoneTransformByName(bone,mathlib:ComposeTransforms(native,inverse),1)
        end
    end
    local positions={right_grip_weapon={on={},off={}},right_trigger_weapon={on={},off={}}}
    for _,finger in ipairs(fingers) do
        for joint=1,3 do
            local name=string.format('r_%s_%02d_jnt',finger,joint)
            local bone=utils.fname_from_string(name)
            local rotation=animation.getBoneSpaceLocalRotator(mesh,bone,1)
            local group=finger=='index' and positions.right_trigger_weapon or positions.right_grip_weapon
            group.off[name]=angles(rotation)
            group.on[name]=angles(rotation)
        end
    end
    local wrist=mesh:GetBoneTransformByName(utils.fname_from_string('r_wrist_jnt'),1).Translation
    local dorsal=mesh:GetBoneTransformByName(utils.fname_from_string('r_wrist_up_jnt'),1).Translation
    local first=mesh:GetBoneTransformByName(utils.fname_from_string('r_index_01_jnt'),1).Translation
    local second=mesh:GetBoneTransformByName(utils.fname_from_string('r_index_02_jnt'),1).Translation
    local axis=normalize(cross(normalize(vector_sub(second,first)),normalize(vector_sub(wrist,dorsal))))
    for joint=1,3 do
        local name=string.format('r_index_%02d_jnt',joint)
        local bone=utils.fname_from_string(name)
        local r,parent=animation.getBoneSpaceLocalRotator(mesh,bone,1)
        local local_axis=mathlib:InverseTransformDirection(parent,axis)
        positions.right_trigger_weapon.on[name]=angles(mathlib:ComposeRotators(r,mathlib:RotatorFromAxisAndAngle(local_axis,({8,12,6})[joint])))
    end
    local owner_class=weapon:GetOwner():get_full_name():match('^(%S+)')
    local trigger_pose=trigger_poses[owner_class]
    if trigger_pose then
        positions.right_trigger_weapon.off=trigger_pose.off
        positions.right_trigger_weapon.on=owner_class=='CRWDivinePistolNew_BP_C'
            and align_pistol_trigger(mesh,relative,trigger_pose) or trigger_pose.on
        uevr.params.functions.log_info('[Crisol hand pose] Using captured native trigger poses for '..owner_class)
    end
    local definition={positions=positions,poses={grip_right_weapon={{'right_grip_weapon','on'},{'right_trigger_weapon','off'}}}}
    animation.add('right_arms',mesh,definition)
    hands.setHoldingAttachment(1,true)
    animation.resetAnimation('right_arms','right_trigger_weapon',false)
    return definition
end

utils.setInterval(500,function()
    if not hands.exists() then return end
    local ok,err = pcall(function()
        weapon = nil
        local pawn = uevr.api:get_local_pawn(0)
        if pawn == nil then return end
        for _,mesh in ipairs(utils.find_all_instances('Class /Script/Engine.SkeletalMeshComponent',false) or {}) do
            pcall(function()
                local name = mesh:get_full_name()
                if not name:match('%.Mesh$') or not name:find('.PersistentLevel.',1,true) then return end
                local owner = mesh:GetOwner()
                local cls = owner and owner:get_full_name():match('^(%S+)') or ''
                if (cls == 'CRWDivinePistolNew_BP_C' or cls == 'CRDivineShotGun_BP_C'
                    or cls == 'CRWDMachineGun_BP_C' or cls == 'CRDivineSniper_BP_C' or cls == 'CRDivineHarpoon_BP_C')
                    and mesh:IsVisible() and not mesh.bHiddenInGame and not owner.bHidden
                    and (owner:GetOwner() == pawn or owner:GetAttachParentActor() == pawn) then weapon=mesh end
            end)
        end
    end)
    if not ok then warn(err) end
end)

utils.registerPostEngineTickCallback(function(_,delta)
    if not hands.exists() or not valid(source) or not valid(player) or mathlib == nil then return end
    local ok,err = pcall(function()
        local mode,reason = classify_action()
        local mode_changed=mode~=native_mode
        if mode=='native' and mode_changed then
            release_left()
            restore_effects(hand_effects)
            if pistol then
                restore_effects(pistol.effects)
                pistol.distance,pistol.near_time,pistol.supporting=nil,0,false
            end
        end
        update_action_visibility(mode,reason)
        if mode=='native' then return end
        local mesh = hands.getHandComponent(1,'Arms')
        if not valid(mesh) then return end
        local weapon_ready=valid(weapon) and weapon:IsVisible() and not weapon.bHiddenInGame
        if weapon_ready then
            local key=weapon:get_address()
            local cached=grip_pose_cache[key]
            if attached_weapon~=weapon and cached then
                for _,entry in ipairs(cached.bones) do mesh:SetBoneTransformByName(entry.name,entry.transform,1) end
                animation.add('right_arms',mesh,cached.animation)
                hands.setHoldingAttachment(1,true)
                animation.resetAnimation('right_arms','right_trigger_weapon',false)
                mesh:K2_AttachToComponent(weapon,utils.fname_from_string('None'),1,1,1,false)
                attached_weapon=weapon
                local ok,err=pcall(setup_pistol,cached.palm,source:GetSocketTransform(weapon_bone,0))
                if not ok then warn(err) end
                uevr.params.functions.log_info('[Crisol hand pose] Restored cached grip; skipped transient reload pose')
            end
            if attached_weapon ~= weapon and mode~='reload' then
                local wrist_name=utils.fname_from_string('r_wrist_jnt')
                local native_wrist=source:GetSocketTransform(wrist_name,0)
                local anchor=source:GetSocketTransform(weapon_bone,0)
                local relative_wrist=mathlib:MakeRelativeTransform(native_wrist,anchor)
                local local_wrist=mesh:GetBoneTransformByName(wrist_name,1)
                local relative=mathlib:ComposeTransforms(mathlib:InvertTransform(local_wrist),relative_wrist)
                local t=relative_wrist.Translation
                assert(t.X*t.X+t.Y*t.Y+t.Z*t.Z<2500,'Native grip is outside weapon reach')
                local finger_animation=capture_right_grip(mesh,anchor,relative)
                local middle=source:GetSocketTransform(utils.fname_from_string('r_middle_01_jnt'),0).Translation
                local w=native_wrist.Translation
                local palm_world=utils.vector((middle.X+w.X)/2,(middle.Y+w.Y)/2,(middle.Z+w.Z)/2)
                local palm=mathlib:InverseTransformLocation(anchor,palm_world)
                center_weapon_palm(palm)
                match_left_palm(anchor)
                grip_cache[key]=relative
                local bones={}
                for index=0,mesh:GetNumBones()-1 do
                    local bn=mesh:GetBoneName(index)
                    if bn:to_string()=='r_wrist_jnt' or mesh:BoneIsChildOf(bn,wrist_name) then
                        bones[#bones+1]={name=bn,transform=mesh:GetBoneTransformByName(bn,1)}
                    end
                end
                grip_pose_cache[key]={bones=bones,animation=finger_animation,palm=palm}
                mesh:K2_AttachToComponent(weapon,utils.fname_from_string('None'),1,1,1,false)
                mesh:K2_SetRelativeTransform(relative,false,hit,false)
                local comparisons={}
                for _,n in ipairs({'r_wrist_jnt','r_index_01_jnt','r_index_02_jnt','r_index_03_jnt','r_middle_01_jnt','r_middle_03_jnt'}) do
                    local bn=utils.fname_from_string(n)
                    local expected=mathlib:MakeRelativeTransform(source:GetSocketTransform(bn,0),anchor)
                    local actual=mesh:GetBoneTransformByName(bn,1)
                    actual=mathlib:ComposeTransforms(actual,relative)
                    local a,b=expected.Translation,actual.Translation
                    local dx,dy,dz=a.X-b.X,a.Y-b.Y,a.Z-b.Z
                    comparisons[n]={error=math.sqrt(dx*dx+dy*dy+dz*dz),expected={a.X,a.Y,a.Z},actual={b.X,b.Y,b.Z}}
                end
                json.dump_file('crisol_grip_comparison.json',{bones=comparisons,source_scale={source.RelativeScale3D.X,source.RelativeScale3D.Y,source.RelativeScale3D.Z},mesh_scale={mesh.RelativeScale3D.X,mesh.RelativeScale3D.Y,mesh.RelativeScale3D.Z},weapon_scale={weapon.RelativeScale3D.X,weapon.RelativeScale3D.Y,weapon.RelativeScale3D.Z}},4)
                attached_weapon = weapon
                local ok,err=pcall(setup_pistol,palm,anchor)
                if not ok then warn(err) end
                local r=mathlib:TransformRotation(relative,utils.rotator(0,0,0))
                json.dump_file('hands_right_grip_crisol.json',{anchor='r_weapon',location={t.X,t.Y,t.Z},rotation=angles(r),palm={palm.X,palm.Y,palm.Z},animation=finger_animation},4)
                uevr.params.functions.log_info('[Crisol hand pose] Fixed right grip on r_weapon; reload animation cannot move wrist')
            end
            if attached_weapon==weapon then
                mesh:K2_SetRelativeTransform(grip_cache[key],false,hit,false)
                animation.updateAnimation('right_arms','right_trigger_weapon',input.right_trigger,{duration=0.075})
            else
                mesh:SetVisibility(false,false)
                right_recovery=right_recovery or {elapsed=0,ready=false}
            end
        elseif attached_weapon ~= nil then
            controllers.attachComponentToController(1,mesh)
            utils.set_component_relative_transform(mesh,{0,0,0},{0,0,0})
            attached_weapon = nil
        end
        if pistol and (not weapon_ready or pistol.mesh~=weapon) then
            restore_effects(pistol.effects)
            pistol=nil
        end
        local pose=update_left_mount(mode,weapon_ready,delta or 0)
        update_left_animation(delta or 0,pose)
        if not left_pose.effects_checked or mode_changed then
            mount_hand_effects()
            left_pose.effects_checked=true
        end
        sync_pistol_effects(mode=='reload')
        if right_recovery then
            local ready=weapon_ready and attached_weapon==weapon
            right_recovery.elapsed=right_recovery.elapsed+(delta or 0)
            if (ready and right_recovery.ready) or (not weapon_ready and mode~='reload' and right_recovery.elapsed>=0.6) then
                mesh:SetVisibility(true,false)
                right_recovery=nil
                uevr.params.functions.log_info('[Crisol hands] Right Sense hand restored')
            else
                right_recovery.ready=ready
            end
        end
    end)
    if not ok then warn(err) end
end)

local function restore_attachments()
    pcall(restore_effects,hand_effects)
    if pistol then pcall(restore_effects,pistol.effects) end
    for component,original in pairs(magazine_original) do
        pcall(function()
            if valid(component) then component:K2_SetRelativeLocation(original,false,hit,false) end
        end)
    end
end

uevr.params.sdk.callbacks.on_script_reset(function()
    restore_attachments()
    pcall(function()
        if not valid(source) then return end
        if saved_tick ~= nil then source.VisibilityBasedAnimTickOption=saved_tick end
        source:SetRenderInMainPass(true)
        source:SetVisibility(true,false)
    end)
    for component,original in pairs(projection_original) do
        pcall(function()
            if not valid(component) then return end
            if original.fov~=nil then component.UseDesiredFOV=original.fov end
            if original.first~=nil then component:SetFirstPersonPrimitiveType(original.first) end
        end)
    end
end)
utils.registerPreLevelChangeCallback(function()
    restore_attachments()
    weapon,attached_weapon,source,player,native_anim=nil,nil,nil,nil,nil
    native_mode,right_recovery=nil,nil
    pistol,hand_effects,magazine_original=nil,{},{}
    left_pose={}
    grip_cache,grip_pose_cache,projection_original={},{},{}
end,10)
return M
