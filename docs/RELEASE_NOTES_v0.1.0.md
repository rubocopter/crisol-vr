## Crisol: Theater of Idols VR — v0.1.0 (public beta)

First public beta of the **UEVR profile for Crisol: Theater of Idols**, focused on PS VR2 Sense controllers.

### Included
- 6DoF pistol aiming with right-hand motion tracking.
- Experimental native hands, tracked grip and contextual animation fallback.
- Head-oriented movement, VR UI/reticle separation and interaction prompts.
- UEVR settings, Oculus Touch / OpenXR bindings, UObjectHook attachments, Lua runtime modules and necessary data.

### Install
1. Download **`CRToiPrototype-Win64-Shipping.zip`** below (not GitHub's "Source code" ZIP).
2. In UEVR choose **Import Config** and select the ZIP without extracting it.
3. Start Crisol with your OpenXR runtime, select **`CRToiPrototype-Win64-Shipping.exe`** in UEVR and click **Inject**.

### Known limitations
This is an **experimental profile**. Hand pose alignment and blood/reload animations can still glitch. DLSS Quality/Balanced caused colored flashing surfaces in VR during testing. `VR_NativeStereoFix=false` is required in the tested configuration. An installed OpenXR Toolkit API layer previously caused crashes. See the [README](https://github.com/rubocopter/crisol-vr#known-issues).

The downloadable ZIP structure, file hashes and JSON have been verified; fresh import on another PC has not yet been independently tested.

**Support:** https://ko-fi.com/onitaku
