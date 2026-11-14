# Crisol VR import profile fixes

**Goal:** Deliver an importable test ZIP for the user's second PC, prioritizing PSVR2 Sense, head-only camera movement in menus/inspection, native-looking two-hand support at physical controller contact, and stable hands/walkie.

**Authority:** User request of 2026-11-13 and `docs/REVISION_2026-11-13.md`. User explicitly requests implementation and a local ZIP; release follows their headset test. Routine implementation choices are delegated to the agent.

**Architecture:** Keep the UEVR profile and Lua modules. Fix discovery and state transitions, use native wrist/finger poses for support, and query supported OpenXR bindings directly. Preserve separate gun tracking. Avoid speculative graphics-quality reductions. Use bounded, targeted discovery and cache invalidation rather than frequent whole-world enumeration.

**Safety:** Existing dirty state is preserved in `dist/before-fixes-20261113.zip`. Work in the existing checkout on `codex/vr-profile-fixes-20261113`; do not change the live installed UEVR profile. No publishing, merging, or version tag.

## Tasks and ownership

- [x] Hands: `profile/scripts/libs/crisol_hand_pose.lua`, `tests/test_hand_pose.py`. Reproduce hidden-child blocking and delayed fallback; fix selection, lifecycle and proximity-based support. Test separation/contact/release, weapon changes, reload/native transitions, walkie restoration and bounded scans. Preserve native finger poses when attached.
- [x] Bindings: controller JSON files, new input helper if needed, `tools/build_release.py`, `tests/test_bindings.py`, `tests/test_controller_input.py`, `README.md`, `docs/README.es.md`, `profile/PSVR2_SENSE.txt`. Verify against UEVR/Sony source; ensure pause, face buttons, sticks, grips/triggers, D-pad, and safe trackpad sectors. Distinguish supported loaded profiles from dormant templates. Reject unusable associations. Include second-PC import/test instructions and modest diagnostics.
- [x] Camera/UI (parent): `profile/scripts/crisol_sense.lua`, `profile/scripts/crisol_vr_ui.lua`, associated tests and shared test setup. Enforce head camera from startup and promptly after transitions without waiting a second; preserve independent gun aiming. Recover widgets promptly using targeted classes/caches. Test menu without pawn, inspection, settings drift, replacement HUD, inactive UI and projection.
- [x] Broader inspection/integration: audit main scripts, config, attachments and lifecycle. Fix confirmed issues with focused reproductions, and record uncertain hardware-dependent issues without inventing fixes.
- [x] Verify/package: full Python test suite, Lua compilation, release builder, CRC/source/hash comparison, independent review of final changes. Deliver `dist/CRToiPrototype-Win64-Shipping.zip` with import instructions and short second-PC checklist. Keep v0.1.0 unchanged.

## Review focus

Main menu can lack a pawn. Save loads can recreate pawn, HUD, hands and props. Hidden inventory actors must not block an equipped prop. Controller button names differ from UEVR's Xbox action names. OpenXR overrides replace defaults and only supported loader names are effective. Controller sample freshness and native/VR transform phases can affect apparent contact. No actual headset verification is claimed by simulated tests.

## Verification

Use Python unittest/pytest with installed Lupa to execute real Lua callbacks against isolated engine doubles. Each behavioral fix first has a failing regression scenario. Final commands: `python -m pytest -q`, Lua `load()` over every shipped Lua file, `python tools/build_release.py`, `git diff --check`. Independently reopen the ZIP and compare all shipped source bytes and its SHA-256.

## Progress

- Backup created; implementation branch created. Prior review and user clarification read.

- Implementation complete; workers frozen. Full suite: 88 passing, also under Lua 5.4; all 42 shipped Lua files compile.
- Independent final review found no blocking P1/P2 issues. The last both-hands validity fix received targeted review.
- Final local ZIP: 67 profile files + 3 notices, 280972 bytes. CRC, source bytes, safe paths, five effective profiles and SHA-256 independently verified.
- No release published. User headset verification and real CPU/GPU measurements remain pending by design. See docs/PRUEBA_2026-11-13.md.
