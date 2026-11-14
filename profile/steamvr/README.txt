NATIVE PS VR2 SENSE / STEAMVR / UEVR OPENXR
========================================

Status: native layout selected on Fractal and working in headset per the user's
2026-11-14 test report. Pause-camera behavior remains a separate code issue.
Importing the UEVR ZIP does NOT select this SteamVR binding. Keep UEVR OpenXR.
Use the separate test kit's tools/Install-SenseBindings.ps1 (Windows PowerShell
5.1, no Python/admin/DevTools). The Python tool is for developer/offline checks.
For standalone downloads, keep Install-SenseBindings.ps1 and the JSON together;
use the same preparation steps below with the standalone paths noted in step 3.

VERIFIED SAVED LAYOUT
--------------------
The shipped crisol_sense_openxr.json is a byte-for-byte copy of the native file
returned on USB: F:/steamvr/input/steam.app.1790930_playstation_vr2_sense.json.
SHA256: 6519535c2cc16b55f7c0d9eb12818972958818a9a5d09bc19bc4a21e17731e1e
Saved name: Asignación compartida de Oni psvr2
The user also published this layout in SteamVR community bindings. Select it
for Crisol and PS VR2 Sense in SteamVR's Controller Bindings UI. The returned
files contain no Workshop/community ID or URL, so no direct link is available.

F:/Crisol-Test/sense-actions.json records OpenXR, the real defaultopenxr actions
and UEVR's accepted Valve Index profile. sense-before.json records the former
Vive auto-remapping. sense-after.json reports success and selection of the
prepared native file; its binding_config matches sense-prepared.json.
The later personal save has exactly the same sources, modes, channels, outputs,
parameters, poses and haptics as that readback. SteamVR only renamed the layout,
added empty alias_info/simulated_actions/skeleton and empty stick parameters,
and omitted empty eyetracking. Manifest version is 0. The old "Offline authored;
headset verification pending" description remains in the JSON to preserve the
saved artifact exactly; the evidence and user report above supersede that text.

Compared with the old Vive auto-remapping, this verified layout uses the Valve
Index application profile; native joystick mode and joystickclick replace the
trackpad-mode/touchpad routes and stick-click face-touch markers. Square becomes
X rather than systembutton; all four face buttons have direct click/touch routes.
Options supplies systembutton, and Create supplies the reserved left-hand View
marker. L1/R1 no longer force a nonexistent hardware click. Aim/grip poses use
openxr_aim/handgrip instead of tip/grip. Haptic routes remain unchanged.

The file is a SteamVR per-app binding, NOT a Sony OpenXR interaction profile:
  app_key:             steam.app.1790930
  category:            openxr
  controller_type:     playstation_vr2_sense
  action set:          /actions/defaultopenxr
  interaction_profile: /interaction_profiles/valve/index_controller

Physical sources remain Sony Sense. The application-facing interaction_profile
must be accepted by UEVR: Valve documents this requirement for OpenXR bindings.
The reviewed UEVR loader supports Valve Index; this avoids Oculus conversion.
No simulated_controller_type/HMD/rendermodel options are enabled. A strictly
Sony interaction_profile would require app/runtime support absent here; no
unsupported Sony OpenXR profile is invented.

EXPECTED CONTROLS
-----------------
Cross/Circle = A/B; Square/Triangle = X/Y.
L2/R2 -> trigger; L1/R1 -> grip; left/right native sticks -> joystick;
L3/R3 -> joystickclick. L1/R1/L2/R2 expose analog value, NOT hardware click.
SteamVR button mode synthesizes a boolean click from that value with its normal
threshold; these sources deliberately have no force_input=click parameter.
Options -> systembutton using direct button/click, NEVER complex_button/single.
UEVR emits Start on short release, View/Back after holding more than 0.5 seconds.
Create -> View/Back through the shipped input helper. Its direct click uses
AButtonTouchRight on the physical LEFT source, reserved there by all five core
XR presets. Right Cross touch cannot trigger View; controller swapping is
accounted for. It requires this build of the UEVR Lua helper to be loaded.
The existing D-pad gesture remains a UEVR feature.
Hand aim = /pose/openxr_aim; grip = /pose/handgrip; haptics = /output/haptic.

OPTIONAL OFFLINE PREPARATION / CAPTURE / SELECTION (NO PYTHON)
-----------------------------------------------------------
Use these steps to prepare a local copy or collect evidence on another machine.
Selecting the published community layout above is the alternative to preparing
a local file; neither occurs automatically when importing the UEVR profile.

1. Import the UEVR profile, launch SteamVR and Crisol, select OPENXR in UEVR,
   inject, wake both controllers. Keep this run alive during capture/selection.
   In SteamVR Controller Bindings select the running Crisol app and PS VR2 Sense.
   Preserve your prior layout. Choose Create New Binding for the physical
   PS VR2 Sense controller, the app's Valve Index OpenXR action profile, and
   disable controller/HMD/rendermodel simulation. Save Personal. Saving a copy
   of a converted Oculus layout alone may retain its compatibility metadata;
   inspect the actual controller_type, not merely the displayed file name.
   The physical controller must remain playstation_vr2_sense. Do not rename
   an Oculus export or change its category to bypass the preparer's checks.

2. Open normal Windows PowerShell in the extracted test-kit directory. Run the
   block below. These requests are read-only and only write local evidence files.
   The dashboard HTTP port 27062 was observed in Corsario vrserver.txt; if your
   SteamVR version uses a different port, use the local Binding UI origin instead.
   The same-machine address is intentional: do not use Corsario's IP on Fractal.

   $ErrorActionPreference = 'Stop'
   $base = 'http://127.0.0.1:27062'
   $appKey = 'steam.app.1790930'
   $controller = 'playstation_vr2_sense'
   $registry = Invoke-RestMethod "$base/input/getactions.json?app_key=$appKey" -TimeoutSec 5
   $registry | ConvertTo-Json -Depth 100 | Set-Content .\sense-actions.json -Encoding UTF8
   $previousUrl = $registry.current_binding_url.$controller
   if (-not $previousUrl) { throw 'No native Sense binding: select Sense and Save Personal in Binding UI first.' }
   $query = 'binding_url=' + [uri]::EscapeDataString($previousUrl) + '&controller_type=' + $controller + '&app_key=' + $appKey
   $previous = Invoke-RestMethod "$base/input/loadbindingfromurl.json?$query" -TimeoutSec 5
   $previous | ConvertTo-Json -Depth 100 | Set-Content .\sense-before.json -Encoding UTF8

   Copy Steam/logs/xrclient_CRToiPrototype-Win64-Shipping.txt from THIS Fractal
   run beside those files (the kit log collector may collect it for you).
   This log plus exported app_key/category/controller_type guard the app/API.
   The tool checks the actual getactions registry and accepted profiles, and
   rejects compatibility files. If it refuses, retain the exact error/evidence.
   Do not change app_key/controller_type/category by hand to bypass validation.

3. From the kit root (adjust paths only if its packager used another layout):

   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Install-SenseBindings.ps1 -Binding .\sense-before.json -Actions .\sense-actions.json -XrLog .\xrclient_CRToiPrototype-Win64-Shipping.txt -Template .\profile\steamvr\crisol_sense_openxr.json -Output .\sense-prepared.json

   For standalone downloads together in the current directory, replace only
   -File with .\Install-SenseBindings.ps1 and -Template with
   .\crisol_sense_openxr.json in that command.

   The first command is PREVIEW. Add -Write to the same command to create the
   separate file. It backs up a previous output byte-for-byte and is idempotent.
   Inputs remain unchanged. Outputs inside Steam/config or steamvr/input are
   rejected. Neither preparer activates bindings or modifies drivers/runtimes.
   Without -Actions, the PowerShell preparer reads the live local registry itself.

4. ACTIVATION IS A SEPARATE, EXPLICIT ACTION. With Crisol still running in
   OpenXR, review the validated file. The block below requests the same
   selectconfig operation as Valve's Binding UI; it changes this app's selected
   Sense binding. Run it only on Fractal when ready to test. No admin is needed.
   The returned Fractal sense-after.json confirms the prepared file was selected.

   $preparedPath = (Resolve-Path .\sense-prepared.json).Path
   $preparedUrl = ([uri]$preparedPath).AbsoluteUri
   $body = @{app_key=$appKey; controller_type=$controller; url=$preparedUrl} | ConvertTo-Json
   $selection = Invoke-RestMethod -Method Post -Uri "$base/input/selectconfig.action" -ContentType 'application/json' -Body $body -TimeoutSec 5
   if ($selection.error) { throw $selection.error }

   SteamVR selection is asynchronous: refresh the Crisol/Sense Binding UI and
   confirm the selected name matches the shipped template's name:
   "Asignación compartida de Oni psvr2".
   A successful HTTP request alone does not prove selection. Read back:

   $registry = Invoke-RestMethod "$base/input/getactions.json?app_key=$appKey" -TimeoutSec 5
   $activeUrl = $registry.current_binding_url.$controller
   $query = 'binding_url=' + [uri]::EscapeDataString($activeUrl) + '&controller_type=' + $controller + '&app_key=' + $appKey
   $active = Invoke-RestMethod "$base/input/loadbindingfromurl.json?$query" -TimeoutSec 5
   $active | ConvertTo-Json -Depth 100 | Set-Content .\sense-after.json -Encoding UTF8
   $binding = $active.binding_config
   $options = @($binding.bindings.'/actions/defaultopenxr'.sources | Where-Object path -eq '/user/hand/right/input/options')
   if (-not $active.success -or $active.app_key -ne $appKey -or $binding.category -ne 'openxr' -or $binding.controller_type -ne $controller -or $binding.interaction_profile -ne '/interaction_profiles/valve/index_controller' -or $options.Count -ne 1 -or $options[0].mode -ne 'button' -or $options[0].inputs.click.output -ne '/actions/defaultopenxr/in/systembutton' -or $options[0].inputs.single) { throw 'Native selection NOT confirmed; inspect sense-after.json and Binding UI.' }

   Also compare the other native sources in sense-after.json to the prepared
   file. Keep sense-prepared.json at a stable location while selected; don't
   delete the test-kit directory. Restart Crisol/UEVR, keeping OpenXR, and repeat
   readback to establish persistence. Do not restore automatic/default bindings
   during this test: that removes the explicit native selection.

5. Roll back by selecting your prior personal layout in SteamVR Binding UI.
   sense-before.json also retains the old binding_config and URI. If using the
   endpoint, select the preserved prior URI with the same app_key/controller_type;
   confirm by readback. The preparer never overwrites that original export.

TEST AND LIMITS
---------------
Test every control individually: menu confirm/back, Options short/hold, L1/R1,
L2/R2, movement/turn, L3/R3, poses/haptics, Create View/Back and D-pad gesture.
Repeat after load/restart. Record physical control, expected Xbox event, observed
event, versions, UEVR Interaction Profile and before/after binding JSON.
The helper's optional bounded Xbox trace is documented in PSVR2_SENSE.txt.
The returned Fractal app/actions/before/after/personal-save exports establish
the native selection; the user reports working controls with a separate pause
camera issue. Per-control observations and restart-persistence evidence were
not included in those exports. A target machine's runtime registry remains a
required preparation gate. If it fails, retain its error/evidence and use the
native authoring UI with the actual listed actions.

SOURCE EVIDENCE (CORSARIO, READ ONLY, 2026-11-14)
-----------------------------------------------
- Steam/logs/xrclient_CRToiPrototype-Win64-Shipping.txt: OpenXRInstance and
  xrCreateSession for steam.app.1790930. appmanifest_1790930.acf names Crisol.
- Steam/config/openxr/steam.app.1790930_knuckles_3_binding.json and
  steam.app.1790930_oculus_touch_2_binding.json: actual /actions/defaultopenxr
  outputs, in/out directions, button/joystick/pose/haptic binding structure.
  All candidate outputs occur in the union of those real per-app exports.
  Their SHA256 respectively:
  510aafac47875186284ed1727f9793f4fc9538e8af1844a55de7c2332575c530
  002729b0cea9d797cc49a0ba7b6d0ad405f25bc815d48075680d1d29317f09f6
- Installed PlayStation VR2 App/SteamVR_Plug-In/resources/input/
  playstation_vr2_sense_controller_profile.json declares every candidate
  physical path and side, INCLUDING /pose/openxr_aim at the end of input_source.
  SHA256 a19f41aa728238ed3a014a56bee3a30385788179edb508d8c31b3ff532a1b6ee
  If another Sony version lacks that pose, do not substitute raw/tip blindly;
  export/check its runtime binding and pose offsets before activation.
- Steam/config/openxr/auto-remapping_toBinding.json contains native l1/r1/l2/r2,
  left_stick/right_stick, openxr_aim and handgrip. It retains compatibility
  metadata, so it is evidence of mode/path support, not a native install export.
- Local UEVR source 4ee5c6b6/OpenXR.cpp: xrCreateActionSet defaultopenxr,
  lowercased action names and per-hand subaction paths. UEVR's Lua handle aliases
  /actions/default/in/... are different: never use them as SteamVR OpenXR outputs.
- Installed SteamVR resources/webinterface/dashboard/controllerbindingui.js:
  getactions.json -> category, action_sets[].actions[], interaction_profiles,
  current_binding_url; loadbindingfromurl.json -> success, app_key, binding_config;
  SaveCurrentBinding writes category/controller_type/app_key/interaction_profile;
  selectconfig.action posts JSON app_key/controller_type/url. Shared module 3804
  in chunk~8012d0c89.js confirms JSON.stringify serialization.
- Valve primary documentation:
  https://github.com/ValveSoftware/openvr/blob/master/docs/Driver_API_Documentation.md#automatic-rebinding
  https://github.com/ValveSoftware/openvr/blob/master/docs/Driver_API_Documentation.md#openxr
  Explicit app bindings take priority over automatic remapping. OpenXR uses an
  application-accepted interaction_profile in the native physical binding file.
