#!/usr/bin/env python3
"""Package the verified UEVR ZIP and Windows-only Fractal tools; no deployment."""
from __future__ import annotations

import hashlib
import importlib.util
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
NAME = "Crisol-Fractal-Testkit.zip"
PROFILE = "CRToiPrototype-Win64-Shipping.zip"


def build() -> tuple[Path, str]:
    profile = DIST / PROFILE
    digest = hashlib.sha256(profile.read_bytes()).hexdigest()
    checksums = (DIST / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    if checksums.count(f"{digest}  {PROFILE}") != 1:
        raise RuntimeError("Build and verify the UEVR profile before the testkit")
    sources = {
        profile: PROFILE,
        ROOT / "tools/Collect-FractalLogs.ps1": "tools/Collect-FractalLogs.ps1",
        ROOT / "tools/Install-SenseBindings.ps1": "tools/Install-SenseBindings.ps1",
        ROOT / "profile/steamvr/crisol_sense_openxr.json": "profile/steamvr/crisol_sense_openxr.json",
        ROOT / "docs/CORSARIO_FRACTAL.md": "CORSARIO_FRACTAL.md",
        ROOT / "profile/PRUEBA_OTRO_PC.txt": "PRUEBA_OTRO_PC.txt",
        ROOT / "LICENSE": "LICENSE",
        ROOT / "UEVRLIB_LICENSE": "UEVRLIB_LICENSE",
        ROOT / "THIRD_PARTY_NOTICES.md": "THIRD_PARTY_NOTICES.md",
    }
    readme_files = (ROOT / "docs/TESTKIT_FRACTAL.txt", ROOT / "profile/steamvr/README.txt")
    snapshot = {path: path.read_bytes() for path in (*sources, *readme_files)}
    entries = {name: snapshot[path] for path, name in sources.items()}
    entries["README.txt"] = b"\n".join(snapshot[path] for path in readme_files)
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in sorted(entries.items()):
            info = ZipInfo(name, date_time=(2026, 11, 14, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o644 << 16
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, content, compresslevel=9)
    payload = buffer.getvalue()
    spec = importlib.util.spec_from_file_location("crisol_export", ROOT / "tools/export_test_build.py")
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)
    exporter.validate_zip(BytesIO(payload), package="testkit")
    if any(path.read_bytes() != content for path, content in snapshot.items()):
        raise RuntimeError("Sources changed during packaging; retry after integration")
    output = DIST / NAME
    pending = output.with_suffix(".zip.tmp")
    pending.write_bytes(payload)
    pending.replace(output)
    kit_digest = hashlib.sha256(payload).hexdigest()
    (DIST / "SHA256SUMS.txt").write_text(
        f"{digest}  {PROFILE}\n{kit_digest}  {NAME}\n", encoding="utf-8")
    return output, kit_digest


if __name__ == "__main__":
    output, digest = build()
    print(f"Fractal testkit: {output} ({output.stat().st_size:,} bytes)")
    print(f"SHA256: {digest}")
