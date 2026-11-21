# Launch, graphics and audio troubleshooting

Use the **latest UEVR nightly** with **OpenXR**. The author tested nightly
01143 (`4ee5c6b6`). With Virtual Desktop, note whether the Streamer uses
**VDXR** or **SteamVR** and keep that runtime during comparisons.
[Download the latest nightly](https://github.com/praydog/UEVR-nightly/releases/latest).

1. Confirm **Native Stereo Fix** is enabled in the Crisol profile. It stopped
   individual pixels from flickering in multiple colors on the author's PS VR2.
   For remaining flashes, test **Lumen** off in Crisol and restart. Try **DLSS**
   off separately if the flashes persist. Keep those graphics settings fixed
   during crash checks.
2. Disconnect the P10 earbuds and their USB dongle for one test, and use the
   Quest's built-in speakers with Virtual Desktop audio streaming. Confirm you
   hear the PC desktop before injecting. Load the same save with the profile.
   If that works, retry with the P10 and specify whether it is paired by
   Bluetooth or uses the dongle, and whether it is connected to the PC or Quest.
   [Soundcore VR P10 connection modes](https://www.soundcore.com/products/vr-p10-a3850z21).
3. If it still crashes with the built-in speakers, close Crisol and UEVR. Back
   up and temporarily rename `%APPDATA%\UnrealVRMod\CRToiPrototype-Win64-Shipping`.
   Inject the same nightly without importing the profile, then load the same
   save with the same audio and graphics settings. If this also crashes, the
   Crisol profile is unnecessary to reproduce it. If only the profile crashes,
   the comparison narrows the investigation to its settings, scripts or attachments.

After each crash, save UEVR's `log.txt` from the active profile directory
before starting another run. In `%LOCALAPPDATA%\CRToiPrototype\Saved\Crashes`,
look for the matching `CrashContext.runtime-xml`. If there is no crash report,
copy the faulting module and exception code from the Windows Application event
at the time of the crash. Share the two test outcomes and whether audio
disappears while the game is still responsive.

## Diagnóstico en español

1. Usa el **último nightly de UEVR** con **OpenXR**. Si usas Virtual Desktop,
   anota si está activo **VDXR** o **SteamVR** y mantenlo durante las pruebas.
2. Comprueba que **Native Stereo Fix** está activado en el perfil de Crisol.
   En el PS VR2 del autor elimina el parpadeo de píxeles individuales en varios
   colores. Si quedan destellos, prueba con **Lumen** desactivado y reinicia.
   Si persisten, prueba también con **DLSS** desactivado por separado.
3. Prueba los altavoces del Quest, con los P10 y su dongle desconectados.
   Comprueba que se oye el escritorio de Windows en Virtual Desktop antes de
   inyectar y carga la misma partida.
4. Si sigue cerrándose, cierra el juego y UEVR, respalda y renombra temporalmente
   la carpeta del perfil indicada arriba. Inyecta la misma nightly sin importar
   el perfil y repite con la misma partida, gráficos y audio.

Guarda `log.txt` de UEVR y el informe `CrashContext.runtime-xml` de ese cierre.
Si no hay informe, sirve el módulo con errores y el código de excepción del
evento de Aplicación de Windows. Indica en qué prueba se pierde el audio y
si el juego seguía respondiendo en ese momento.
