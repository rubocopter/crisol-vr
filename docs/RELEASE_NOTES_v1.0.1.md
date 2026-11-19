# Crisol VR v1.0.1 — Touch controller compatibility

Fixes an Oculus Touch binding error that could consume movement when UEVR's
right-thumbrest D-pad mode is selected. Resting a thumb on the left movement
stick was incorrectly assigned to the right-thumbrest modifier. The binding
now uses each physical thumbrest on its own hand.

## Included

- Corrected Touch thumbrest bindings for runtimes exposing the Oculus Touch
  interaction profile, including compatible Quest controller routes.
- Packaging checks for native movement axes and physical modifier paths.
- 102 new physical-input mapping tests for Touch, Index, Vive, Microsoft Motion
  and native Sense, covering controller swaps, resting touches and pad clicks.
- Updated controller and connection instructions inside the profile and in
  the English/Spanish project guides.

The tested native PS VR2 Sense layout is included unchanged.

## Install or update

1. Download **CRToiPrototype-Win64-Shipping.zip** from this release's Assets.
2. Close Crisol and UEVR and back up your existing game profile.
3. Import the ZIP with UEVR **Import Config**, without extracting it.
4. Start your headset's OpenXR runtime and Crisol, select
   **CRToiPrototype-Win64-Shipping.exe**, choose **OpenXR** and inject.

Quest Link/Air Link uses the Meta OpenXR runtime. Virtual Desktop can use
VDXR or SteamVR OpenXR, and Steam Link uses SteamVR OpenXR. Enable streaming
of motion controllers. UEVR selects the supplied mapping when the effective
interaction profile matches it. PS VR2 Sense users can keep their selected
community layout.

The profile's D-pad gesture uses the left stick while the left controller is
near the headset. Move it away for ordinary walking. Details are in the
[controller guide](https://github.com/rubocopter/crisol-vr/blob/v1.0.1/docs/CONTROLLERS.md).

## Validation and remaining hardware checks

**299 automated tests pass**, and all **43 shipped Lua scripts compile with
Lua 5.4**. The bindings were compared with official UEVR 1.05 input handling.

Quest 3 hardware validation remains pending. The author uses PS VR2, so
community testing is needed to establish whether this correction resolves
the reported Quest 3 movement failure on the affected setup. Other controller
families also retain their hardware-testing limitations.

## Downloads

- **CRToiPrototype-Win64-Shipping.zip** — the UEVR profile to import.
- **crisol_sense_openxr.json**, **Install-SenseBindings.ps1** and
  **Sense-OpenXR-README.txt** — optional native Sense setup files.
- **SHA256SUMS.txt** — checksums for the downloads.

Requirements, credits and known graphical/animation limitations are in the
[project guide](https://github.com/rubocopter/crisol-vr/blob/v1.0.1/README.md).
UEVR and the game are obtained separately. OpenAI Codex assisted with code,
testing and documentation.
