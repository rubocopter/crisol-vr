CRISOL VR - CONTROLLER COMPATIBILITY UPDATE 1.0.1
==================================================

Import CRToiPrototype-Win64-Shipping.zip with UEVR Import Config.
Back up your existing game profile first, then restart the game and UEVR.
Select CRToiPrototype-Win64-Shipping.exe, choose OpenXR and inject.

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

This release corrects the Touch thumbrest modifier paths. Previously,
resting your left thumb on the movement stick could activate UEVR's opposite
thumbrest D-pad modifier. With right-touch D-pad mode, that consumes walking.

The supplied D-pad gesture also deliberately uses movement while the left
controller is near the headset. Move that controller away to walk normally.
To disable this feature during diagnosis, disable DPad Shifting AND select
a non-gesture method (0). The checkbox alone does not stop UEVR 1.05's gesture.

Please test walking/turning while touching the sticks, triggers and buttons,
then check face buttons, pause and grip/trigger actions. The native Sense
layout is preserved. Physical testing of other controller families remains
pending; Sparrowone's exact Quest 3 runtime/transport is unknown.

Project and issue reports: https://github.com/rubocopter/crisol-vr
