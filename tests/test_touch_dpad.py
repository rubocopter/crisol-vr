"""Touch locomotion must survive ordinary finger contact on the left hand.

UEVR 1.05 VR.cpp: RIGHT_TOUCH consumes the left axes when ThumbrestTouchRight
is active and neither AButtonTouchRight nor BButtonTouchRight is active.
Drive that predicate from the physical paths in the shipped JSON.
"""
import json
from pathlib import Path

import pytest


PROFILE = Path(__file__).resolve().parents[1] / "profile/_interaction_profiles_oculus_touch_controller.json"


def right_thumbrest_dpad(physical_contacts):
    bindings = json.loads(PROFILE.read_text(encoding="utf-8"))["bindings"]
    active = {item["action"] for item in bindings if item["path"] in physical_contacts}
    return "thumbresttouchright" in active and not active.intersection(
        {"abuttontouchright", "bbuttontouchright"}
    )


@pytest.mark.parametrize("contacts", [
    {"/user/hand/left/input/thumbstick/touch"},
    {"/user/hand/left/input/trigger/touch"},
    {"/user/hand/left/input/thumbstick/touch", "/user/hand/left/input/trigger/touch"},
])
def test_left_hand_contact_keeps_locomotion_with_standard_dpad_modifier(contacts):
    assert not right_thumbrest_dpad(contacts), "Ordinary left-hand contact must not turn movement into D-pad input"


def test_physical_right_thumbrest_can_still_request_dpad():
    assert right_thumbrest_dpad({"/user/hand/right/input/thumbrest/touch"})


def test_thumbrest_modifiers_use_their_own_physical_hand():
    bindings = json.loads(PROFILE.read_text(encoding="utf-8"))["bindings"]
    for side in ("left", "right"):
        paths = [item["path"] for item in bindings if item["action"] == f"thumbresttouch{side}"]
        assert paths == [f"/user/hand/{side}/input/thumbrest/touch"]
