CRISOL VR 1.0.2
===============

Import CRToiPrototype-Win64-Shipping.zip with UEVR Import Config.
Back up your existing game profile first, then restart the game and UEVR.
Select CRToiPrototype-Win64-Shipping.exe, choose OpenXR and inject.
Use the latest UEVR nightly: https://github.com/praydog/UEVR-nightly/releases/latest
Tested with nightly 01143, PS VR2 Sense and SteamVR OpenXR. Native Stereo Fix
is enabled in the profile and stops multicolored pixel flicker on that setup.

Quest Link/Air Link: use the Meta OpenXR runtime with motion controllers.
Virtual Desktop VDXR: enable motion-controller streaming and use OpenXR.
Steam Link / Virtual Desktop through SteamVR: use SteamVR as OpenXR runtime.
UEVR loads the supplied Touch mapping when the runtime exposes Oculus Touch.

Movement/turn uses the native sticks on Touch, Index and Microsoft Motion,
and the trackpads on Vive wands. Trigger, grip, face buttons, stick clicks
and pause are mapped through the effective interaction profile. Other
controller families require a runtime mapping to a supported profile.
Simple controllers provide only a limited subset of the game's controls.

PS VR2 Sense: keep your tested native SteamVR community layout selected.
The separate Sense installer/layout is for Sony controllers.

The profile corrects the Touch thumbrest modifier paths. Previously,
resting your left thumb on the movement stick could activate UEVR's opposite
thumbrest D-pad modifier. With right-touch D-pad mode, that consumes walking.

The supplied D-pad gesture also deliberately uses movement while the left
controller is near the headset. Move that controller away to walk normally.
To disable this feature during diagnosis, disable DPad Shifting AND select
a non-gesture method (0).

Test the right hand before picking anything up. Rotate the controller with a
neutral wrist, squeeze the grip to curl the fingers, and press/release the
trigger to move the index. Repeat after putting away a weapon or the walkie.
These animations respond to controller inputs. They do not use individual
finger tracking.

The author verified the camera, tracked reticle, firing alignment and two-handed
support with PS VR2 Sense. The reload blood effect can still appear detached
from the tracked left wrist.

Project and issue reports: https://github.com/rubocopter/crisol-vr
