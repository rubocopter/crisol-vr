# Changelog

## [v1.0.1] - 2026-11-19

- Correct the Oculus Touch thumbrest modifiers. Touching the left movement stick previously activated the right-thumbrest action and could consume locomotion with UEVR's right-touch D-pad mode.
- Validate native movement axes and the physical Touch thumbrests during packaging, and exercise shipped controller bindings through the input helper with physical button/contact states.
- Document the effective OpenXR routes for Quest/Touch, Index, Vive, WMR, compatible controller families and native Sense. The Quest 3 no-movement report's transport/runtime remains unknown, so it is not established that the corrected modifier explains that report.

## [v1.0.0] - 2026-11-14

- Include the tested native PS VR2 Sense SteamVR layout, preserving the author's saved mapping. Prioritize the published community layout, with a native JSON and PowerShell guide as fallback; keep UEVR on OpenXR without Oculus conversion.
- Restore right-controller interaction and shooting traces during gameplay while keeping head-controlled view in the main menu, inspection and contextual cameras.
- Fix pause detection for head-controlled pause menus, including paused worlds without a visible cursor and world replacement. Local camera regression tests cover pause/resume and world replacement.
- Improve native two-hand support using physical controller proximity, correct support-hand transform handling, refresh mounted poses and restore bones after failed release.
- Recover hand setup after pawn/arm replacement or initialization failure; recover equipped weapons despite hidden inventory children and remove the initial discovery blackout.
- Correct the reported lower-right pointer offset by using the game's effective view and traced target rather than the raw controller ray. Preserve UEVR aim interpolation and UI height scaling; local regressions cover native aim and collision parallax.
- Improve HUD discovery and lifecycle handling, restore authored widget offsets and avoid whole-map mesh enumeration.
- Validate the five core UEVR OpenXR overrides, add Index trackpad pause and prevent Vive sector clicks from also sending locomotion axes. Exclude sixteen inactive templates from the release ZIP; non-Sense hardware remains unverified.
- Add deterministic, snapshot-checked ZIP packaging and regression tests, plus local build export and diagnostics tools for development.
- Update the English and Spanish landing pages, installation and release notes for v1.0.0. Add version identification and Codex assistance credit.

The author reports working PS VR2 Sense controls with SteamVR and UEVR OpenXR, acceptable performance, and publication of the working Sense layout to the SteamVR community. See the release notes for known limitations and the validation scope of the latest fixes.

## [v0.1.0] - 2026-11-07

Initial public beta of the Crisol: Theater of Idols UEVR profile.

- PS VR2 Sense compatibility bindings, right-hand tracked weapon aiming and experimental native hand poses.
- Head-oriented locomotion and separation of headset HUD from weapon-facing reticle and interaction prompts.
- Contextual hand animation switching, experimental finger pose behavior and weapon attachments.
- UEVR settings validated from the currently used profile, including Native Stereo Fix disabled.
- GitHub Release archive with profile files directly at ZIP root.

Known limitations: hand and blood effect alignment, animation transition artifacts, DLSS Quality/Balanced glitches under UEVR, high GPU cost. See README.
