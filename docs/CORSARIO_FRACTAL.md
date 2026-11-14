# Builds locales: CORSARIO desarrolla, FRACTAL juega

Los scripts no sincronizan proyectos ni instalan perfiles remotos. El repositorio,
`.git`, partidas y juegos quedan fuera. No hay nube, tareas programadas ni envío
automático de diagnósticos. El juego puede seguir abierto durante la exportación;
para importar el perfil en FRACTAL hay que cerrarlo junto con UEVR.

## 1. Exportar desde CORSARIO (sin administrador)

Desde `E:\Proyectos\crisol`, genera y verifica la entrega antes de exportarla:

```powershell
python tools\build_release.py
python tools\build_testkit.py
python tools\export_test_build.py --package testkit
```

El último comando valida `dist\Crisol-Fractal-Testkit.zip` contra
`dist\SHA256SUMS.txt` y copia exclusivamente ese ZIP, el checksum y
`profile\PRUEBA_OTRO_PC.txt` a `E:\Builds\Crisol\<fecha-UTC-id>\`.
No ejecuta el constructor por su cuenta: puede exportar un ZIP anterior si aún
no se ha construido el nuevo. La fecha de `latest.json` es de **exportación**.

La copia se hace en una carpeta temporal del destino y se vuelve a verificar.
Si cambian las fuentes, falla una copia o un hash, `latest.json` conserva la
entrega anterior. Las entregas anteriores se mantienen; no hay borrado automático.
Solo tras validar los tres archivos se renombra la carpeta y se sustituye el
manifiesto mediante renombrado atómico. Esto protege frente a fallos de la
operación; no pretende garantizar recuperación ante un corte de alimentación.

Si E:\Builds no permite escribir, usar explícitamente y comunicar este destino:

```powershell
python tools\export_test_build.py --destination E:\Proyectos\Builds
```

`--project Crisol` es el nombre estable de carpeta, nunca una versión. Para otro
proyecto se puede reutilizar la estructura de entregas, pero hay que adaptar y
revisar primero la lista explícita `ARTIFACTS` y la validación del ZIP; este
exportador está acotado al perfil de Crisol y no acepta carpetas arbitrarias.

### Testkit de FRACTAL con instalador nativo

Cuando el constructor haya terminado y verificado `dist\Crisol-Fractal-Testkit.zip`:

```powershell
python tools\export_test_build.py --package testkit
# Si el constructor usa un sidecar dedicado en lugar de SHA256SUMS.txt:
python tools\export_test_build.py --package testkit --checksum-name Crisol-Fractal-Testkit.sha256
```

El checksum debe contener exactamente una entrada válida para el ZIP seleccionado;
`SHA256SUMS.txt` puede contener además el hash del perfil. La entrega sigue teniendo
solo **un ZIP, su checksum y PRUEBA_OTRO_PC.txt**, además de `latest.json` en la raíz
del proyecto. `--package testkit` selecciona un nombre fijo, no cualquier ZIP.
El exportador no construye ni modifica el testkit. Para exportar únicamente
el perfil importable, se puede usar `python tools\export_test_build.py`.

El testkit admite el ZIP UEVR interior, `tools/Collect-FractalLogs.ps1`, el opcional
`tools/Install-SenseBindings.ps1`, `profile/steamvr/crisol_sense_openxr.json` (o
`steamvr/crisol_sense_openxr.json`), README/instrucciones y avisos de licencia.
Se rechazan otras entradas y también se valida el perfil ZIP interior. El binding
nativo de SteamVR se activa **fuera de Import Config de UEVR** siguiendo el README
del kit y su instalador PowerShell. FRACTAL no necesita Python para estos scripts.

## 2. Único paso pendiente de administrador en CORSARIO

La sesión actual no es administradora. **No se ha creado la compartición ni
modificado el firewall.** Vista previa sin permisos de administrador:

```powershell
.\tools\Setup-BuildShare.ps1 -WhatIf
# Equivalente: .\tools\Setup-BuildShare.ps1 -DryRun
```

La vista previa valida rutas y muestra el plan; las comprobaciones de conflictos
SMB/firewall y permisos reales se hacen en la ejecución administradora. El script
sale antes de invocar cualquier cmdlet de escritura en ambos modos de vista previa.

Después de revisar el archivo, el usuario abre **PowerShell como administrador**
en CORSARIO y ejecuta una vez:

```powershell
& 'E:\Proyectos\crisol\tools\Setup-BuildShare.ps1'
```

Si se eligió el destino alternativo, añadir `-SharePath E:\Proyectos\Builds`.
El script es idempotente: admite una compartición/regla propias que coincidan y
rechaza conflictos. No sustituye comparticiones preexistentes ni modifica otras
reglas del firewall. Los permisos NTFS de la raíz dedicada se fijan a Oni
(Modify), SYSTEM y Administradores (FullControl), sin permisos heredados amplios.

Publica `\\CORSARIO\ModBuilds` con acceso SMB **Read** de `CORSARIO\Oni`.
Para permitir también copiar diagnósticos de vuelta, elegir `-ShareAccess Change`
en esa primera ejecución. Cambiar posteriormente el nivel se considera conflicto
y exige revisión manual. Nunca concede Everyone, invitado o acceso anónimo.

La única regla creada permite TCP 445 entrante, `System`/`LanmanServer`, interfaz
Ethernet y perfil **Private**, desde FRACTAL `192.168.1.154` hacia CORSARIO
`192.168.1.4`. No activa grupos generales del firewall ni inicia servicios.
Si cambian las IP por DHCP o la interfaz, revisar el script antes de reutilizarlo.
Solo se comprueban conflictos con la regla propia `ModBuilds-SMB-CORSARIO-FRACTAL`.
Las demás reglas existentes se conservan y no bloquean este setup; el script no
audita ni modifica su alcance. También se rechazan
junctions/enlaces en cualquier descendiente de Builds (hasta 10 000 entradas).

Los parámetros usados están documentados en
[New-SmbShare](https://learn.microsoft.com/en-us/powershell/module/smbshare/new-smbshare?view=windowsserver2025-ps)
y [New-NetFirewallRule](https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule?view=windowsserver2025-ps).
El control de vista previa es propio porque Microsoft indica que `New-SmbShare`
no implementa correctamente su parámetro `WhatIf`.

## 3. Copiar y probar en FRACTAL

En el Explorador abrir `\\CORSARIO\ModBuilds\Crisol` e iniciar sesión como
`CORSARIO\Oni` con la contraseña de esa cuenta (no el PIN de Windows Hello).
Si el nombre no resuelve, probar `\\192.168.1.4\ModBuilds\Crisol`.
Copiar `latest.json` y la carpeta que indica `release` a una carpeta local.

Ejemplo para copiar exactamente esa entrega y verificar sus tres archivos:

```powershell
$share = '\\CORSARIO\ModBuilds\Crisol'
$latest = Get-Content -LiteralPath "$share\latest.json" -Raw | ConvertFrom-Json
# release debe ser un único nombre de carpeta generado por el exportador.
if ($latest.release -notmatch '^\d{8}T\d{12}Z-[a-f0-9]{8}$') { throw 'Manifiesto inesperado' }
$local = Join-Path $env:USERPROFILE ('Downloads\Crisol-' + $latest.release)
New-Item -ItemType Directory -Path $local | Out-Null
$names = @($latest.files.PSObject.Properties.Name)
$allowed = @('CRToiPrototype-Win64-Shipping.zip', 'Crisol-Fractal-Testkit.zip', 'SHA256SUMS.txt', 'Crisol-Fractal-Testkit.sha256', 'PRUEBA_OTRO_PC.txt')
if ($names.Count -ne 3 -or @($names | Where-Object { $_ -notin $allowed }).Count) { throw 'Archivos inesperados' }
foreach ($name in $names) {
    Copy-Item -LiteralPath (Join-Path "$share\$($latest.release)" $name) -Destination $local
    $hash = (Get-FileHash -LiteralPath (Join-Path $local $name) -Algorithm SHA256).Hash
    if ($hash -ne $latest.files.$name.sha256) { throw "Hash incorrecto: $name" }
}
```

Leer `PRUEBA_OTRO_PC.txt`: cerrar juego/UEVR, respaldar y renombrar el perfil
anterior de `%APPDATA%\UnrealVRMod\CRToiPrototype-Win64-Shipping` e importar el ZIP
con **Import Config** de UEVR. Nada de esto se ejecuta automáticamente.
Si se entregó el testkit, extraerlo localmente, leer su README e importar el ZIP
UEVR interior; el ZIP exterior no se importa en UEVR. Ejecutar el instalador
PowerShell de Sense por separado según esas instrucciones.

## 4. Recoger diagnóstico en FRACTAL (sin administrador)

Copiar `tools\Collect-FractalLogs.ps1` a FRACTAL por el medio elegido y ejecutarlo
allí. No necesita el repositorio. Ejemplo con Steam en C: y biblioteca en D:

```powershell
.\Collect-FractalLogs.ps1 -SteamPath 'C:\Program Files (x86)\Steam' `
  -SteamLibrary 'D:\SteamLibrary' `
  -GameLogPath "$env:LOCALAPPDATA\CRToiPrototype\Saved\Logs"
```

Los valores predeterminados apuntan al perfil UEVR de Crisol, Steam en Program
Files (x86) y logs de juego en LocalAppData. Si no coinciden, usar `-ProfilePath`,
`-GameLogPath` y opcionalmente `-UEVRLogPath` con las carpetas reales. La ubicación
de los logs del juego puede variar. No se buscan juegos en todo el disco.

Genera `Documentos\Crisol-Diagnostics\Crisol-diagnostics-<UTC-id>.zip`.
Incluye configuración y scripts del perfil, bindings OpenXR, hasta tres logs
recientes por familia (UEVR, juego, `vrserver`, `vrclient`/`xrclient` cuyo nombre contenga el
ejecutable de Crisol), `steamvr.vrsettings`, bindings guardados cuyo nombre
contenga ese ejecutable o `steam.app.1790930` y los ajustes predeterminados de SteamVR si están presentes.
Los bindings guardados con nombres opacos no se adivinan ni se recopilan en masa.
`-SteamAppId` permite indicar otro identificador explícito. La captura del perfil
incluye también `uobjecthook`, `steamvr` y las subcarpetas Lua conocidas de `libs`.

Límites por defecto: 100 archivos, 32 MiB totales, 1 MiB por configuración y cola
de 256 KiB por log. No sigue enlaces/junctions ni incluye binarios, volcados de
memoria, `loginusers.vdf`, `config.vdf` o archivos con nombres de credenciales.
El manifiesto registra hashes de los archivos exportados, tiempos originales,
recortes, censura de campos comunes de credenciales, fuentes cambiadas durante
la lectura y archivos ausentes/omitidos. Es una copia de texto UTF-8; si censura
un campo o recorta un log, no es una copia byte a byte del original. Los logs
pueden contener rutas personales: revisar el ZIP antes de compartirlo.

Cada ejecución conserva las capturas anteriores. El juego/perfil solo se lee;
puede estar abierto, en cuyo caso la captura no es una instantánea coherente del
proceso completo. `-WhatIf` no escribe nada. No envía el ZIP automáticamente.
Para guardarlo en otra carpeta, usar `-Destination 'D:\Diagnosticos'`; una ruta UNC
solo se usa cuando se proporciona explícitamente y hay permisos de escritura.

## Verificación local

```powershell
python -m pytest tests\test_build_transfer.py -q
```

Las pruebas simulan errores de copia/publicación, corrupción y cambios de fuente;
comprueban límites de rutas, junctions y entradas ZIP, hashes de exportación,
conservación de la entrega anterior, captura diagnóstica real en PowerShell 5.1
con datos de prueba y ausencia de llamadas mutadoras en las vistas previas SMB.
La creación real de la compartición y la conexión desde FRACTAL quedan pendientes
del paso administrador y de la prueba de red en los dos equipos.
