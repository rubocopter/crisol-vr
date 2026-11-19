# Controller compatibility

Use UEVR **OpenXR** for the bindings supplied by this project. A headset's
display and its controller interaction profile are separate runtime choices.
The profile maps the effective controller family selected by that runtime.

| Headset/controller setup | Effective input route | Configuration |
| --- | --- | --- |
| Quest 1/2/3/3S or Quest Pro through Link/Air Link | Oculus Touch compatibility in the Meta OpenXR runtime | Enable motion controllers and select OpenXR in UEVR. |
| Quest through Virtual Desktop VDXR | Oculus Touch compatibility exposed by VDXR | Enable motion-controller streaming and select OpenXR. |
| Quest through Steam Link or Virtual Desktop using SteamVR | Touch or the compatible profile selected by SteamVR | Make SteamVR the OpenXR runtime and use the matching layout. |
| Index controllers with an OpenXR headset | Valve Index | Sticks for movement/turn, left trackpad press for pause. |
| Vive wands with an OpenXR headset | HTC Vive | Trackpad movement and clicked sectors for face buttons. |
| WMR controllers with an available compatible runtime | Microsoft Motion | Real sticks for movement, trackpad sectors for face buttons. |
| PICO, Vive Cosmos/Focus and other motion controllers | A runtime mapping to a supported Touch, Index, Vive or Motion profile | Controls follow the effective profile. Dedicated native profiles require injector/runtime support. |
| PS VR2 Sense through SteamVR | Physical Sense layout with UEVR's supported Index action contract | Select the author's Sense community layout as described in the main guide. |
| Khronos simple controllers | Simple select/menu | The available inputs cover only part of the game. |

## Movement and D-pad

Both native sticks are mapped directly on Touch, Index and Microsoft Motion.
Vive uses its native trackpads. Clicking a Vive sector consumes only that
pad's movement axes while it supplies a face-button action. Microsoft Motion's
trackpad sectors preserve its separate sticks.

The supplied D-pad method uses the left controller near the headset. Keep the
left controller away from the headset for ordinary locomotion. In UEVR 1.05,
disabling only the D-pad-shifting checkbox does not disable a selected head
gesture. To disable D-pad conversion for a diagnostic test, disable shifting
and choose a non-gesture method. Other D-pad methods deliberately consume the
selected stick while their modifier is active.

The 1.0.1-rc.1 candidate corrects the Touch modifier paths to the left and right
physical thumbrests. In 1.0.0, left-stick contact was assigned to the right
thumbrest modifier. That combination can suppress walking if right-touch
D-pad mode is selected. The candidate preserves the tested native Sense file.

## Coverage

PS VR2 Sense was tested by the author with SteamVR and OpenXR. Automated
regressions exercise the shipped mappings and input helper. They cover
physical button/contact states and preserve normal stick axes across core
controller families. Other controller hardware still needs live testing.

Sparrowone reported no Quest 3 movement with UEVR 1.05. The connection and
selected runtime were not supplied. Virtual Desktop/OpenXR is a working
assumption, and the exact cause remains unconfirmed.

OpenVR uses UEVR's SteamVR action bindings rather than the supplied
`_interaction_profiles_*.json` overrides. The OpenXR input helper leaves
OpenVR axes unchanged. Full OpenVR binding equivalence is not established by
the OpenXR mapping tests.

## Sources

- [UEVR 1.05 OpenXR loader and stick lookup](https://github.com/praydog/UEVR/blob/1.05/src/mods/vr/runtimes/OpenXR.cpp).
- [UEVR 1.05 default physical component paths](https://github.com/praydog/UEVR/blob/1.05/src/mods/vr/runtimes/OpenXR.hpp).
- [UEVR 1.05 D-pad conversion and head gesture](https://github.com/praydog/UEVR/blob/1.05/src/mods/VR.cpp).
- [UEVR 1.05 D-pad method enum](https://github.com/praydog/UEVR/blob/1.05/src/mods/VR.hpp).
- [UEVR runtime selection and Virtual Desktop guidance](https://docs.uevr.io/usage/overview.html).
- [Khronos Oculus Touch component paths](https://registry.khronos.org/OpenXR/specs/1.0-khr/html/xrspec.html#_oculus_touch_controller_profile).
