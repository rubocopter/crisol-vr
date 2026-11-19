# Controller compatibility follow-up

The user requests broad support for known headsets/controllers after a Quest 3
user reports no movement on UEVR 1.05. The transport and runtime are unknown.
Use the supported effective runtime profiles and preserve the working native
Sense layout. Virtual Desktop/OpenXR is an assumption, not reported evidence.

- [x] Compare the five shipped OpenXR overrides and input processing against
  official UEVR 1.05. Identify concrete failures before changing behavior.
- [x] Correct Touch thumbrest routing so touching the movement stick cannot
  activate the opposite-thumbrest D-pad modifier. Add a failing regression
  using the actual JSON and UEVR's input conversion rule.
- [x] Exercise physical inputs through the shipped helper for all effective
  profile families, swaps, resting touches, Vive sectors and Sense Create.
- [x] Address any other verified loader/runtime compatibility gaps discovered
  in the scoped review, preserving normal movement and essential actions.
- [x] Update controller/transport documentation, run relevant regressions and
  build a verified local compatibility candidate for the user to test/share.

Local simulated input tests cannot establish full hardware compatibility or
confirm the cause of Sparrowone's report without runtime evidence.

## Verification

- 299 tests passed with Lua 5.4, including 102 physical-input mapping tests.
- All 43 shipped Lua scripts compile. Candidate ZIP contains 75 verified entries.
- SHA256 2a9acdadf2a6b4455d072086127b2cee4096c7d479a95692163a67f83a596b35.
- Local/shared export 20261119T182035156152Z-43b8bb04.
- Touch RIGHT_TOUCH modifier failure reproduced before correction. The unchanged
  head-gesture mode is a separate conditional movement consumer.
- Quest 3 hardware validation and the report's exact runtime remain pending.
- Three share-setup tests now isolate preflight from the host Builds directory.
