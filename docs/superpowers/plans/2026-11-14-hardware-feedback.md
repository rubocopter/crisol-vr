# Hardware feedback follow-up

Authority: user tested the 2026-11-13 ZIP. Performance and menu/inspection camera improved. Interaction targeting, sights/shots and two-hand contact remain wrong. Options/non-face Sense inputs fail. User requires OpenXR and a genuine Sense binding, not an invented Sony OpenXR override or an OpenVR switch. Corsario should build; Fractal should run/test.

## Evidence and decisions

- Previous test ZIP preserved in `dist/archive/2026-11-13-OpenXR-test.zip`; SHA-256 `c2e7606b7a1878aafd61dd6e3ba3493b97d1a0421378d0b80cd37515fa230062`.
- Previous camera policy forced Head/HMD plus disabled ControlRotation for all gameplay. Moving a gun mesh alone did not redirect native gameplay traces. Replace this with contextual UI/gameplay policy; preserve OpenXR rendering and the performance changes the user tested successfully.
- Installed executable reflection strings confirm ECRPlayerState enum order None/Absorb/Damage/Interacting/Block/Dead/Healing. Native GetPlayerState wrapper at VA `0x144cc0250` reads a byte at player offset `0xbb8`; GetActualInteractuablePlaceUsing at `0x144cbf520` reads a pointer at `0xe20`. No game/decompiled files are redistributed.
- Add native Sense bindings at the SteamVR layer for the OpenXR application. A UEVR `_interaction_profiles_sony_*.json` that the loader never visits is not a solution. Inspect actual runtime binding format/registry and fail closed on mismatched app/API. Do not switch render runtime.
- Corsario: `192.168.1.4`, private LAN, user `CORSARIO\Oni`, current process not elevated. Fractal resolves to `192.168.1.154`. No ordinary SMB share exists; administrative-share probes from this session returned false. Prepare a dedicated artifact share and reviewed setup; do not expose the repository or require a cloud service.

## Work and ownership

- [x] Parent: failing camera-context scenarios; contextual aim module and pre/post-engine camera updates. Nine focused camera tests pass. Game/UI transitions and final package/source validation completed; actual shots still require the user headset test.
- [x] Hands worker: state/pose/contact defects in `crisol_hand_pose.lua`, stronger rotation/lifecycle tests; no silent extra grip requirement.
- [x] Sense worker: real SteamVR Sense/OpenXR binding route, guarded installer, tests and packaging. Do not mutate live SteamVR settings while investigating.
- [x] Transfer worker: dedicated `E:/Builds` artifact exporter, admin SMB setup, Fractal log collection and instructions; no system changes from unelevated session.
- [x] Parent integration: independent review, full Lua/Python tests and local test ZIP/export. Record what still requires actual Fractal headset events.

No publishing or release tags. Avoid repeating a broad audit; focus on the reported hardware regressions and useful diagnostics.

## Delivery status

- Complete local delivery: 182 tests passed, also on Lua 5.4; all 43 shipped Lua files compile.
- Independent review: collector OpenXR omission corrected; Create marker/swap checks reviewed without further blocking findings.
- UEVR profile and Fractal testkit built and independently checked; final artifact hashes recorded in docs/PRUEBA_2026-11-14.md.
- Final verified export: E:/Builds/Crisol/20261114T005400102124Z-344d961a.
- Pending external steps: user activates native SteamVR binding on Fractal and runs share setup once as administrator on Corsario. No release published.
