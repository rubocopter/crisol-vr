# Crisol: Theater of Idols VR — v1.0.0

A UEVR profile for **Crisol: Theater of Idols** with 6DoF pistol aiming, the game's own hands, head-oriented movement and a VR interface.

The author tested **PS VR2 Sense with SteamVR and UEVR OpenXR** successfully, with acceptable performance. The working native Sense layout is included and published in SteamVR community bindings.

## What's changed since v0.1.0

- Native Sense controls using Sony physical inputs through SteamVR, retaining UEVR OpenXR without Oculus conversion. Community layout selection is the recommended setup path.
- Controller-directed interaction and shooting during gameplay, with head-controlled view in menus, puzzles and inspection.
- Corrected pause detection so head view is retained even when the world pauses without a visible cursor. Local camera regression tests cover pause/resume and world replacement.
- Improved two-hand support, hand/weapon recovery and contextual animation handling, including the walkie-talkie.
- Corrected the pointer appearing below/right of the bullet impact by following the game's effective aim and traced target.
- Improved HUD refresh and restoration of authored widget offsets.
- Five core OpenXR controller overrides, Index trackpad pause and Vive sector-click movement suppression. Inactive source templates are excluded from the release ZIP.
- Version identification, regression checks and validated profile packaging.

## Install

You need the PC game, [UEVR](https://github.com/praydog/UEVR/releases) and an OpenXR-compatible PC VR setup.

1. Download **`CRToiPrototype-Win64-Shipping.zip`** from this release's **Assets**.
2. Back up an existing custom UEVR profile, then choose **Import Config** and import the ZIP **without extracting it**.
3. Start your OpenXR runtime (SteamVR for PS VR2) and Crisol. Select **`CRToiPrototype-Win64-Shipping.exe`** in UEVR, choose **OpenXR** and click **Inject**.
4. For **PS VR2 Sense**, open SteamVR **Controller Bindings** for Crisol and PS VR2 Sense, and select the author's community layout **“Asignación compartida de Oni psvr2”**.
5. Load your save.

**Importing the UEVR ZIP does not activate a SteamVR layout.** Keep the native Sense layout selected and UEVR on OpenXR. If you cannot find the community layout, use the [native-binding guide](https://github.com/rubocopter/crisol-vr/blob/v1.0.0/profile/steamvr/README.txt).

When upgrading, close Crisol and UEVR, back up and rename `%APPDATA%\UnrealVRMod\CRToiPrototype-Win64-Shipping`, then import v1.0.0 to avoid retaining old scripts. Restart the game and UEVR after changing bindings; restart SteamVR if its layout changed.

## Release downloads

- **`CRToiPrototype-Win64-Shipping.zip`** — importable UEVR profile, with files directly at ZIP root.
- **`crisol_sense_openxr.json`** — the saved native Sense SteamVR layout, also included inside the profile ZIP.
- **`Install-SenseBindings.ps1`** and **`Sense-OpenXR-README.txt`** — optional local-binding setup and selection instructions.
- **`SHA256SUMS.txt`** — checksums for the release downloads.

GitHub's generated **Source code** archives are for development. The profile ZIP is the file to import into UEVR.

## Known limitations

- The latest pause-menu camera and pointer/impact-alignment corrections still need headset verification.
- Other controller mappings are unverified on hardware. The Khronos simple profile lacks enough inputs for full gameplay.
- Hand poses, animation transitions and blood effects during reload/absorption remain experimental.
- DLSS Quality/Balanced have caused colored flashing surfaces in VR; Performance or DLAA worked better in the tested setup.
- Keep `VR_NativeStereoFix=false`. An installed OpenXR Toolkit layer previously caused save-loading crashes on the development machine.

[English guide](https://github.com/rubocopter/crisol-vr/blob/v1.0.0/README.md) · [Guía en español](https://github.com/rubocopter/crisol-vr/blob/v1.0.0/docs/README.es.md) · [Report an issue](https://github.com/rubocopter/crisol-vr/issues) · [Support on Ko-fi](https://ko-fi.com/onitaku)

Thanks to **praydog** for UEVR, **jbusfield** for UEVRLib and the hands tutorial, and **onitaku / rubocopter** for the Crisol profile. **OpenAI Codex** assisted with code, testing and documentation. This is an unofficial fan-made profile; the game and UEVR are obtained separately.
