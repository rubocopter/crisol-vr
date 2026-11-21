# Crisol VR v1.0.2

The reticle follows the barrel, the game's firing aim uses the same target,
and moving the weapon leaves the headset view stable. Two-handed support
engages at the weapon's support point and releases when the left hand moves
away. The free right hand also has updated grip and trigger poses.

**Native Stereo Fix is enabled by default.** It stopped individual pixels
from flickering in multiple colors on the author's PS VR2 setup. Use OpenXR
with the latest UEVR nightly. The author tested nightly 01143 (`4ee5c6b6`)
with PS VR2 Sense and SteamVR. [Latest UEVR nightly](https://github.com/praydog/UEVR-nightly/releases/latest).

## Install or update

1. Close Crisol and UEVR and back up your existing game profile.
2. Import `CRToiPrototype-Win64-Shipping.zip` from this release's assets using
   **Import Config** in UEVR. Import the ZIP directly.
3. Start your headset's OpenXR runtime and Crisol, select
   `CRToiPrototype-Win64-Shipping.exe`, choose **OpenXR**, and inject.

PS VR2 Sense users can keep their existing SteamVR layout. The release includes
the optional native Sense JSON, the Windows installation script, its guide,
and SHA-256 checksums. [English guide](https://github.com/rubocopter/crisol-vr/blob/v1.0.2/README.md) · [Guía en español](https://github.com/rubocopter/crisol-vr/blob/v1.0.2/docs/README.es.md).

## Known issue and validation

**Reload blood can still appear detached from the left wrist.** The author
verified camera behavior, reticle tracking, firing alignment and two-handed
support with PS VR2 Sense. Other headsets still need gameplay checks.

## Resumen en español

La mira sigue el cañón y comparte el punto de apuntado con los disparos. La
cámara sigue el visor y el giro con el stick. El apoyo a dos manos se activa
al acercar la palma al arma y se suelta al separarla.

El perfil deja **Native Stereo Fix** activado para evitar el parpadeo de
píxeles multicolor observado en PS VR2. Usa el último nightly de UEVR con
OpenXR. **La sangre de recarga aún puede verse separada de la muñeca izquierda.**

This is an unofficial profile. Crisol and UEVR are required separately.
OpenAI Codex assisted with code, tests and documentation.
