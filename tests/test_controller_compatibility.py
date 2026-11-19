"""Physical shipped bindings -> per-hand XR actions -> real Lua input callback.

The adapter models the external runtime boundary, not the helper's marker
predicate. UEVR 1.05 VR.hpp exposes numeric action handles (not TouchpadClick)
and VR.cpp/OpenXR.cpp use physical hand indices 0/1 as OpenXR subactions.
Only direct inputs, cardinal pad sectors and ordinary Xbox conversion are
needed here; D-pad gestures, snap turning and runtime hardware are out of scope.
No downloaded research files, SteamVR installation, network or USB are needed.
"""

from itertools import combinations
import json
from pathlib import Path

from lupa import LuaRuntime
import pytest


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile"
HELPER = PROFILE / "scripts/libs/crisol_controller_input.lua"
XR_PROFILES = ("oculus_touch", "valve_index", "htc_vive", "microsoft_motion", "khr_simple")
PROFILES = (*XR_PROFILES, "sense")
HANDS = ("left", "right")
AXIS_FIELDS = ("sThumbLX", "sThumbLY", "sThumbRX", "sThumbRY")
NORMAL_AXES = (8191, -16383, -24575, 12287)
SWAPPED_AXES = (-24575, 12287, 8191, -16383)
POSITIONS = ((0.25, -0.5), (-0.75, 0.375))

# Fixed public Lua registry from VR.hpp; action names in binding JSON are lower
# case, while get_action_handle requires these exact paths. Internal OpenXR
# Touchpad/TouchpadClick actions intentionally have no public Lua handle.
PUBLIC_ACTIONS = (
    "Pose", "GripPose", "Trigger", "Grip", "Joystick", "JoystickClick",
    "AButtonLeft", "BButtonLeft", "AButtonTouchLeft", "BButtonTouchLeft",
    "AButtonRight", "BButtonRight", "AButtonTouchRight", "BButtonTouchRight",
    "DPad_Up", "DPad_Right", "DPad_Down", "DPad_Left", "SystemButton",
    "ThumbrestTouchLeft", "ThumbrestTouchRight",
)
HANDLES = {f"/actions/default/in/{name}": index + 101
           for index, name in enumerate(PUBLIC_ACTIONS)}
ACTION_BY_HANDLE = {handle: path.rsplit("/", 1)[1].lower()
                    for path, handle in HANDLES.items()}


def physical(hand, component):
    return f"/user/hand/{hand}/input/{component}"


def subsets(items):
    """Every simultaneous combination, including none and all."""
    for size in range(len(items) + 1):
        yield from combinations(items, size)


class ShippedController:
    def __init__(self, name, swapped=False):
        self.name = name
        self.swapped = swapped
        self.actions = {}
        self.ready = self.openxr = self.using = True
        if name == "sense":
            data = json.loads((PROFILE / "steamvr/crisol_sense_openxr.json").read_text())
            sources = data["bindings"]["/actions/defaultopenxr"]["sources"]
            self.bindings = [
                {"path": f"{source['path']}/{channel}",
                 "action": output["output"].rsplit("/", 1)[1]}
                for source in sources for channel, output in source["inputs"].items()
            ]
            self.associations = []
        else:
            data = json.loads((PROFILE / f"_interaction_profiles_{name}_controller.json").read_text())
            self.bindings = data["bindings"]
            self.associations = data["vector2_associations"]

        self.lua = LuaRuntime(unpack_returned_tuples=True)
        # Keep handles numeric and source zero valid. Reject incorrect argument
        # types/subactions instead of a permissive fake accepting string names.
        vr = self.lua.table_from({
            "is_runtime_ready": lambda: self.ready,
            "is_openxr": lambda: self.openxr,
            "is_using_controllers": lambda: self.using,
            "get_lowest_xinput_index": lambda: 0,
            "get_left_joystick_source": lambda: int(self.swapped),
            "get_right_joystick_source": lambda: int(not self.swapped),
            "get_action_handle": lambda path: HANDLES.get(path, 0),
            "is_action_active": self.is_action_active,
            "get_mod_value": lambda _vr, key: str(self.swapped).lower()
            if key == "VR_SwapControllerInputs" else None,
        })
        self.lua.globals().uevr = self.lua.table_from({
            "params": self.lua.table_from({"vr": vr}),
        })
        self.callback = self.lua.execute(HELPER.read_text(encoding="utf-8")).process

    def is_action_active(self, handle, source):
        assert type(handle) is int and handle in ACTION_BY_HANDLE, f"Invalid Lua handle: {handle!r}"
        assert type(source) is int and source in (0, 1), f"Invalid XR subaction: {source!r}"
        return bool(self.actions.get((ACTION_BY_HANDLE[handle], source), False))

    def inputs(self, pressed=(), positions=POSITIONS):
        values = {path: True for path in pressed}
        for hand, position in zip(HANDS, positions):
            component = (f"{hand}_stick/position" if self.name == "sense" else
                         "trackpad" if self.name == "htc_vive" else "thumbstick")
            values[physical(hand, component)] = position
        return values

    def resolve(self, values):
        self.actions = {}
        for binding in self.bindings:
            path = binding["path"]
            if path not in values:
                continue
            source = HANDS.index(path.split("/")[3])
            key = binding["action"], source
            value = values[path]
            # Multiple physical bindings to a boolean action combine with OR.
            self.actions[key] = value if isinstance(value, tuple) else bool(value or self.actions.get(key))

        # UEVR's vector associations force boolean outputs only while clicked.
        # Tests use exact cardinal sectors, avoiding a reimplementation of its
        # distance threshold and ambiguity at sector boundaries.
        for association in self.associations:
            source = HANDS.index(association["path"].rsplit("/", 1)[1])
            if not self.actions.get((association["activator"], source)):
                continue
            position = self.actions.get((association["modifier"], source))
            for output in association["outputs"]:
                if position == (output["value"]["x"], output["value"]["y"]):
                    self.actions[output["action"], source] = True

    def poll(self, values, user_index=0):
        self.resolve(values)
        # Basic UEVR Xbox conversion before the Lua callback. Expected test
        # values below are literals derived from physical controls, not this
        # action dictionary or the helper's marker pair.
        pad = dict.fromkeys(AXIS_FIELDS, 0)
        pad.update(wButtons=0, bLeftTrigger=0, bRightTrigger=0)
        sources = (1, 0) if self.swapped else (0, 1)
        for side, source in zip(("L", "R"), sources):
            x, y = self.actions.get(("joystick", source), (0, 0))
            pad[f"sThumb{side}X"], pad[f"sThumb{side}Y"] = int(x * 32767), int(y * 32767)
            pad[f"b{'Left' if side == 'L' else 'Right'}Trigger"] = (
                255 if self.actions.get(("trigger", source)) else 0)
            for action, bit in (("joystickclick", 0x0040 if side == "L" else 0x0080),
                                ("grip", 0x0100 if side == "L" else 0x0200)):
                if self.actions.get((action, source)):
                    pad["wButtons"] |= bit
        face_bits = (0x2000, 0x1000, 0x8000, 0x4000) if self.swapped else (0x1000, 0x2000, 0x4000, 0x8000)
        for action, bit in zip(("abuttonright", "abuttonleft", "bbuttonright", "bbuttonleft"), face_bits):
            if any(self.actions.get((action, source)) for source in (0, 1)):
                pad["wButtons"] |= bit
        state = self.lua.table_from({"Gamepad": self.lua.table_from(pad)})
        self.callback(None, user_index, state)
        return dict(state.Gamepad.items())


def assert_axes(pad, expected, context):
    assert tuple(pad[field] for field in AXIS_FIELDS) == expected, context


@pytest.mark.parametrize("name", PROFILES)
@pytest.mark.parametrize("swapped", [False, True], ids=["normal", "swapped"])
def test_resting_shipped_profiles_preserve_available_movement(name, swapped):
    controller = ShippedController(name, swapped)
    pad = controller.poll(controller.inputs())
    # KHR simple has no physical movement control; do not invent one.
    expected = (0, 0, 0, 0) if name == "khr_simple" else SWAPPED_AXES if swapped else NORMAL_AXES
    assert_axes(pad, expected, name)
    assert pad["wButtons"] == 0


@pytest.mark.parametrize("swapped", [False, True], ids=["normal", "swapped"])
@pytest.mark.parametrize("selected", [(), ("left",), ("right",), HANDS])
def test_khr_simple_select_reaches_triggers_without_inventing_sticks(swapped, selected):
    controller = ShippedController("khr_simple", swapped)
    pad = controller.poll(controller.inputs([physical(hand, "select/click") for hand in selected]))
    assert_axes(pad, (0, 0, 0, 0), selected)
    left, right = (255 if hand in selected else 0 for hand in HANDS)
    assert (pad["bLeftTrigger"], pad["bRightTrigger"]) == ((right, left) if swapped else (left, right))
    assert pad["wButtons"] == 0


@pytest.mark.parametrize("swapped", [False, True], ids=["normal", "swapped"])
def test_every_touch_combination_keeps_quest_movement_and_never_emits_create(swapped):
    controller = ShippedController("oculus_touch", swapped)
    touches = tuple(physical(hand, f"{component}/touch")
                    for hand, components in (("left", ("x", "y", "trigger", "thumbstick", "thumbrest")),
                                             ("right", ("a", "b", "trigger", "thumbstick", "thumbrest")))
                    for component in components)
    for pressed in subsets(touches):  # All 1,024 two-hand capacitive combinations.
        pad = controller.poll(controller.inputs(pressed))
        assert_axes(pad, SWAPPED_AXES if swapped else NORMAL_AXES, pressed)
        assert pad["wButtons"] == 0, pressed


@pytest.mark.parametrize("swapped", [False, True], ids=["normal", "swapped"])
def test_every_quest_button_trigger_stick_combination_keeps_movement(swapped):
    controller = ShippedController("oculus_touch", swapped)
    controls = tuple(physical(hand, component)
                     for hand, faces in (("left", ("x", "y")), ("right", ("a", "b")))
                     for component in (*[f"{face}/click" for face in faces],
                                       "trigger/value", "squeeze/value", "thumbstick/click"))
    resting = tuple(physical(hand, f"{component}/touch") for hand in HANDS
                    for component in ("trigger", "thumbstick", "thumbrest"))
    for pressed in subsets(controls):
        pad = controller.poll(controller.inputs((*resting, *pressed)))
        assert_axes(pad, SWAPPED_AXES if swapped else NORMAL_AXES, pressed)
        assert pad["wButtons"] & 0x0020 == 0, pressed


@pytest.mark.parametrize("name", ["valve_index", "microsoft_motion"])
@pytest.mark.parametrize("swapped", [False, True], ids=["normal", "swapped"])
def test_stick_controllers_keep_movement_while_using_either_trackpad(name, swapped):
    controller = ShippedController(name, swapped)
    controls = tuple(physical(hand, component) for hand in HANDS
                     for component in ("trackpad/click", "trackpad/touch", "trackpad/force",
                                       "thumbstick/touch", "thumbstick/click", "trigger/touch"))
    for pressed in subsets(controls):
        values = controller.inputs(pressed)
        values.update({physical(hand, "trackpad"): (0, -1) for hand in HANDS})
        pad = controller.poll(values)
        assert_axes(pad, SWAPPED_AXES if swapped else NORMAL_AXES, (name, pressed))
        assert pad["wButtons"] & 0x0020 == 0, (name, pressed)


@pytest.mark.parametrize("swapped", [False, True], ids=["normal", "swapped"])
@pytest.mark.parametrize("clicked", [(), ("left",), ("right",), HANDS],
                         ids=["neither", "left", "right", "both"])
def test_vive_only_physical_click_suppresses_its_pad_and_release_restores(swapped, clicked):
    controller = ShippedController("htc_vive", swapped)
    touching = tuple(physical(hand, "trackpad/touch") for hand in HANDS)
    # A trigger, grip and mere capacitive touch must not suppress pad movement.
    held = (*touching, physical("left", "trigger/value"), physical("right", "squeeze/click"))
    before = controller.poll(controller.inputs(held))
    expected = SWAPPED_AXES if swapped else NORMAL_AXES
    assert_axes(before, expected, "touch without click")
    pressed = (*held, *(physical(hand, "trackpad/click") for hand in clicked))
    during = controller.poll(controller.inputs(pressed))
    expected_by_hand = {"left": (8191, -16383), "right": (-24575, 12287)}
    for hand in clicked:
        expected_by_hand[hand] = (0, 0)
    order = ("right", "left") if swapped else HANDS
    assert_axes(during, sum((expected_by_hand[hand] for hand in order), ()), clicked)
    for field in ("wButtons", "bLeftTrigger", "bRightTrigger"):
        assert during[field] == before[field], (clicked, field)
    assert controller.poll(controller.inputs(held)) == before


# Physical pad sectors must still deliver the intended buttons after axes are
# suppressed. A no-op helper would preserve the buttons but fail the axes check.
@pytest.mark.parametrize("hand,position,button", [
    ("left", (0, -1), 0x4000), ("left", (1, 0), 0x8000), ("left", (0, 1), 0x0040),
    ("right", (0, -1), 0x1000), ("right", (-1, 0), 0x2000), ("right", (0, 1), 0x0080),
])
def test_vive_physical_sector_keeps_gameplay_button(hand, position, button):
    controller = ShippedController("htc_vive")
    positions = (position, POSITIONS[1]) if hand == "left" else (POSITIONS[0], position)
    pad = controller.poll(controller.inputs([physical(hand, "trackpad/click")], positions))
    assert_axes(pad, (0, 0, -24575, 12287) if hand == "left" else (8191, -16383, 0, 0), hand)
    assert pad["wButtons"] == button


@pytest.mark.parametrize("name,component,button", [
    ("oculus_touch", "left/x/click", 0x4000),
    ("oculus_touch", "left/y/click", 0x8000),
    ("oculus_touch", "right/a/click", 0x1000),
    ("oculus_touch", "right/b/click", 0x2000),
    ("sense", "left/square/click", 0x4000),
    ("sense", "left/triangle/click", 0x8000),
    ("sense", "right/cross/click", 0x1000),
    ("sense", "right/circle/click", 0x2000),
])
def test_physical_face_clicks_still_reach_gameplay(name, component, button):
    controller = ShippedController(name)
    hand, component = component.split("/", 1)
    pad = controller.poll(controller.inputs([physical(hand, component)]))
    assert_axes(pad, NORMAL_AXES, component)
    assert pad["wButtons"] == button


@pytest.mark.parametrize("swapped", [False, True], ids=["normal", "swapped"])
def test_native_sense_create_is_a_physical_click_not_right_cross_touch(swapped):
    controller = ShippedController("sense", swapped)
    touches = tuple(physical(hand, component) for hand, component in (
        ("left", "square/touch"), ("left", "triangle/touch"),
        ("right", "cross/touch"), ("right", "circle/touch"),
        ("left", "l2/touch"), ("left", "left_stick/touch")))
    for touched in subsets(touches):
        for create in (False, True, False):  # release while the touches remain
            pressed = (*touched, physical("left", "create/click")) if create else touched
            pad = controller.poll(controller.inputs(pressed))
            assert_axes(pad, SWAPPED_AXES if swapped else NORMAL_AXES, (touched, create))
            assert pad["wButtons"] == (0x0020 if create else 0), (touched, create)


@pytest.mark.parametrize("swapped", [False, True], ids=["normal", "swapped"])
def test_native_sense_buttons_triggers_and_sticks_preserve_axes_with_create(swapped):
    controller = ShippedController("sense", swapped)
    controls = tuple(physical(hand, component) for hand, component in (
        ("left", "square/click"), ("left", "triangle/click"),
        ("right", "cross/click"), ("right", "circle/click"),
        ("left", "l1/click"), ("right", "r1/click"),
        ("left", "l2/click"), ("right", "r2/click"),
        ("left", "left_stick/click"), ("right", "right_stick/click")))
    for pressed in subsets(controls):
        pad = controller.poll(controller.inputs((*pressed, physical("left", "create/click"))))
        assert_axes(pad, SWAPPED_AXES if swapped else NORMAL_AXES, pressed)
        assert pad["wButtons"] & 0x0020 == 0x0020, pressed
        left = 255 if physical("left", "l2/click") in pressed else 0
        right = 255 if physical("right", "r2/click") in pressed else 0
        assert (pad["bLeftTrigger"], pad["bRightTrigger"]) == ((right, left) if swapped else (left, right)), pressed


@pytest.mark.parametrize("name", PROFILES)
@pytest.mark.parametrize("swapped", [False, True], ids=["normal", "swapped"])
@pytest.mark.parametrize("guard", ["openvr", "not-ready", "no-controllers", "other-xinput"])
def test_inactive_or_non_xr_callback_preserves_incoming_axes(name, swapped, guard):
    controller = ShippedController(name, swapped)
    # Activate every actual boolean route, including Vive clicks and Sense
    # Create. The guards must preserve input even in these adversarial states.
    pressed = [binding["path"] for binding in controller.bindings
               if binding["action"] not in {"joystick", "touchpad", "pose", "grippose", "haptic"}]
    values = controller.inputs(pressed)
    baseline = controller.poll(controller.inputs())
    controller.openxr = guard != "openvr"
    controller.ready = guard != "not-ready"
    controller.using = guard != "no-controllers"
    pad = controller.poll(values, user_index=1 if guard == "other-xinput" else 0)
    assert_axes(pad, tuple(baseline[field] for field in AXIS_FIELDS), (name, guard))
    assert pad["wButtons"] & 0x0020 == 0
