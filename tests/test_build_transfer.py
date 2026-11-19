"""Behavioral checks for publishing an explicitly bounded build snapshot."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
from zipfile import ZipFile, ZipInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_transfer", ROOT / "tools/export_test_build.py")
transfer = importlib.util.module_from_spec(spec)
if spec.loader and spec.origin and Path(spec.origin).exists():
    spec.loader.exec_module(transfer)


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "repo"
    (root / "dist").mkdir(parents=True)
    (root / "profile").mkdir()
    with ZipFile(root / "dist" / "CRToiPrototype-Win64-Shipping.zip", "w") as archive:
        archive.writestr("config.txt", "VR_RenderingMethod=0\n")
        archive.writestr("scripts/hands.lua", "return {}")
        archive.writestr("uobjecthook/17456386621128916574_mc_state.json", '{}')
    update_hash(root)
    (root / "profile/PRUEBA_OTRO_PC.txt").write_text("Cerrar juego antes de importar.", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git/secret").write_text("do not export")
    (root / "dist/unrelated.zip").write_bytes(b"not selected")
    return root


def update_hash(root):
    name = "CRToiPrototype-Win64-Shipping.zip"
    digest = hashlib.sha256((root / "dist" / name).read_bytes()).hexdigest()
    (root / "dist/SHA256SUMS.txt").write_text(f"{digest}  {name}\n")


def publish(workspace, tmp_path, **kwargs):
    assert hasattr(transfer, "export_build"), "export_build must publish validated snapshots"
    return transfer.export_build(workspace, tmp_path / "Builds", **kwargs)


def test_exports_only_named_artifacts_and_manifest_hashes(workspace, tmp_path):
    manifest_path = publish(workspace, tmp_path)
    manifest = json.loads(manifest_path.read_text())
    assert manifest_path == tmp_path / "Builds/Crisol/latest.json"
    release = manifest_path.parent / manifest["release"]
    assert {p.name for p in release.iterdir()} == {
        "CRToiPrototype-Win64-Shipping.zip", "SHA256SUMS.txt", "PRUEBA_OTRO_PC.txt"
    }
    for name, item in manifest["files"].items():
        content = (release / name).read_bytes()
        assert hashlib.sha256(content).hexdigest() == item["sha256"]
        assert len(content) == item["bytes"]


def test_bad_hash_preserves_previous(workspace, tmp_path):
    latest = publish(workspace, tmp_path)
    previous = latest.read_bytes()
    (workspace / "dist/SHA256SUMS.txt").write_text("0" * 64 + "  CRToiPrototype-Win64-Shipping.zip\n")
    with pytest.raises(ValueError, match="SHA256"):
        publish(workspace, tmp_path)
    assert latest.read_bytes() == previous


@pytest.mark.parametrize("checksum_name", ["SHA256SUMS.txt", "Crisol-Fractal-Testkit.sha256"])
@pytest.mark.parametrize("unsafe_entry", ["extra", "symlink"])
def test_explicit_testkit_selection_validates_inner_profile(workspace, tmp_path, checksum_name, unsafe_entry):
    kit = workspace / "dist/Crisol-Fractal-Testkit.zip"
    profile = workspace / "dist/CRToiPrototype-Win64-Shipping.zip"
    with ZipFile(kit, 'w') as archive:
        archive.write(profile, profile.name)
        archive.writestr('tools/Collect-FractalLogs.ps1', '# diagnostic collector')
        archive.writestr('tools/Install-SenseBindings.ps1', '# native installer')
        archive.writestr('profile/steamvr/crisol_sense_openxr.json', '{"bindings":{}}')
        archive.writestr('README.md', 'Importar con el juego cerrado.')
    digest = hashlib.sha256(kit.read_bytes()).hexdigest()
    checksum = workspace / "dist" / checksum_name
    checksum.write_text(checksum.read_text() + f"{digest}  {kit.name}\n" if checksum.exists() else f"{digest}  {kit.name}\n")
    latest = publish(workspace, tmp_path, package="testkit", checksum_name=checksum_name)
    manifest = json.loads(latest.read_text())
    assert set(manifest['files']) == {kit.name, checksum_name, 'PRUEBA_OTRO_PC.txt'}
    previous = latest.read_bytes()
    with ZipFile(kit, 'a') as archive:
        if unsafe_entry == 'extra':
            archive.writestr('tools/steal-credentials.ps1', 'unexpected')
        else:
            link = ZipInfo('LEEME.txt')
            link.create_system = 3
            link.external_attr = 0o120777 << 16
            archive.writestr(link, '../../outside/instructions.txt')
    checksum.write_text(f"{hashlib.sha256(kit.read_bytes()).hexdigest()}  {kit.name}\n")
    with pytest.raises(ValueError):
        publish(workspace, tmp_path, package="testkit", checksum_name=checksum_name)
    assert latest.read_bytes() == previous


@pytest.mark.parametrize("failure", ["source", "copy", "manifest", "corrupt"])
def test_failed_transfer_preserves_previous(workspace, tmp_path, monkeypatch, failure):
    latest = publish(workspace, tmp_path)
    previous = latest.read_bytes()
    old_release = json.loads(previous)["release"]
    real_copy = shutil.copyfile
    real_replace = transfer.os.replace

    def copy(source, destination):
        result = real_copy(source, destination)
        if failure == "source":
            Path(source).write_bytes(Path(source).read_bytes() + b"changed")
        if failure == "copy":
            raise OSError("injected copy failure")
        if failure == "corrupt":
            Path(destination).write_bytes(b"broken copy")
        return result

    def replace(source, destination):
        if Path(destination).name == "latest.json":
            raise OSError("injected manifest failure")
        return real_replace(source, destination)

    monkeypatch.setattr(transfer.shutil, "copyfile", copy)
    if failure == "manifest":
        monkeypatch.setattr(transfer.os, "replace", replace)
    with pytest.raises((OSError, ValueError, RuntimeError)):
        publish(workspace, tmp_path)
    assert latest.read_bytes() == previous
    assert (latest.parent / old_release / "CRToiPrototype-Win64-Shipping.zip").is_file()
    assert not list(latest.parent.glob(".pending-*"))


@pytest.mark.parametrize("project", ["../escape", "a/b", "a\\b", ".git", "C:bad", "CON", "Crisol."])
def test_project_traversal_is_rejected(workspace, tmp_path, project):
    with pytest.raises(ValueError):
        publish(workspace, tmp_path, project=project)


def test_destination_cannot_be_workspace(workspace):
    assert hasattr(transfer, "export_build")
    with pytest.raises(ValueError):
        transfer.export_build(workspace, workspace / "Builds")


@pytest.mark.parametrize("member", ["../escape.txt", "saves/save.json", ".git/config", "game.exe", "scripts/token.txt"])
def test_unsafe_zip_is_rejected(workspace, tmp_path, member):
    with ZipFile(workspace / "dist/CRToiPrototype-Win64-Shipping.zip", "a") as archive:
        archive.writestr(member, "unwanted")
    update_hash(workspace)
    with pytest.raises(ValueError):
        publish(workspace, tmp_path)


def test_source_junction_cannot_escape_workspace(workspace, tmp_path):
    import subprocess
    outside = tmp_path / "outside"
    shutil.move(str(workspace / "dist"), outside)
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(workspace / "dist"), str(outside)], capture_output=True)
    if result.returncode:
        pytest.skip("junction creation unavailable")
    try:
        with pytest.raises(ValueError):
            publish(workspace, tmp_path)
    finally:
        (workspace / "dist").rmdir()


def test_collector_bounded_backup_and_no_credential_files(tmp_path):
    import subprocess
    profile = tmp_path / "profile"
    steam = tmp_path / "Steam"
    game = tmp_path / "GameLogs"
    output = tmp_path / "Diagnostics"
    for path in (profile / "scripts", steam / "logs", steam / "config", game):
        path.mkdir(parents=True)
    (profile / "config.txt").write_text("VR_AimMethod=1\npassword=do-not-include")
    (profile / "scripts/hands.lua").write_text("return {}")
    (profile / "scripts/libs/config").mkdir(parents=True)
    (profile / "scripts/libs/config/hands_config.lua").write_text("return {}")
    (profile / "uobjecthook").mkdir()
    (profile / "uobjecthook/123_mc_state.json").write_text('{}')
    (profile / "credentials.json").write_text('secret')
    (steam / "config/loginusers.vdf").write_text('credential')
    (steam / "config/steamvr.vrsettings").write_text('{"steamvr":{"renderTargetMultiplier":1}}')
    (steam / "config/input").mkdir()
    (steam / "config/input/steam.app.1790930_knuckles.json").write_text('{"bindings":{}}')
    (steam / "config/openxr").mkdir()
    (steam / "config/openxr/steam.app.1790930_knuckles.json").write_text('{"category":"openxr","bindings":{}}')
    (steam / "config/openxr/steam.app.999999_other.json").write_text('{"unrelated":true}')
    (steam / "logs/vrserver.txt").write_text("server latest\n")
    (steam / "logs/vrclient_CRToiPrototype-Win64-Shipping.txt").write_text("XR client latest\n")
    (steam / "logs/xrclient_CRToiPrototype-Win64-Shipping.txt").write_text("OpenXR client latest\n")
    (steam / "logs/vrclient_other-game.txt").write_text("unrelated")
    (game / "Crisol.log").write_text("game latest\n")
    result = subprocess.run([
        "powershell", "-NoProfile", "-File", str(ROOT / "tools/Collect-FractalLogs.ps1"),
        "-ProfilePath", str(profile), "-SteamPath", str(steam), "-GameLogPath", str(game),
        "-Destination", str(output),
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    archives = list(output.glob("*.zip"))
    assert len(archives) == 1
    with ZipFile(archives[0]) as archive:
        names = archive.namelist()
        assert "manifest.json" in names
        assert "profile/config.txt" in names
        assert "profile/scripts/hands.lua" in names
        assert "profile/scripts/libs/config/hands_config.lua" in names
        assert "profile/uobjecthook/123_mc_state.json" in names
        assert "steam/logs/vrserver.txt" in names
        assert "steam/logs/vrclient_CRToiPrototype-Win64-Shipping.txt" in names
        assert "steam/logs/xrclient_CRToiPrototype-Win64-Shipping.txt" in names
        assert "steam/bindings/steam.app.1790930_knuckles.json" in names
        assert "steam/bindings/openxr/steam.app.1790930_knuckles.json" in names
        assert not any("999999" in name for name in names)
        assert "game/logs/Crisol.log" in names
        combined = b"".join(archive.read(n) for n in names)
        assert b"do-not-include" not in combined
        assert not any("loginusers" in n or "credentials" in n or "other-game" in n for n in names)
        manifest = json.loads(archive.read("manifest.json").decode("utf-8-sig"))
        for item in manifest["files"]:
            assert hashlib.sha256(archive.read(item["archive_path"])).hexdigest() == item["sha256"]
    # A second capture keeps the previous backup, and missing sources are reported.
    shutil.rmtree(profile)
    again = subprocess.run(result.args, capture_output=True, text=True)
    assert again.returncode == 0, again.stdout + again.stderr
    assert len(list(output.glob("*.zip"))) == 2


def test_collector_tail_limits_and_whatif(tmp_path):
    import subprocess
    profile = tmp_path / "profile"
    logs = tmp_path / "logs"
    output = tmp_path / "output"
    profile.mkdir()
    logs.mkdir()
    (profile / "config.txt").write_bytes(b"x" * (1024 * 1024 + 1))
    (logs / "game.log").write_text("old-" * 2000 + "last-message")
    command = [
        "powershell", "-NoProfile", "-File", str(ROOT / "tools/Collect-FractalLogs.ps1"),
        "-ProfilePath", str(profile), "-SteamPath", str(tmp_path / "missing-steam"),
        "-GameLogPath", str(logs), "-Destination", str(output), "-LogTailKiB", "1",
    ]
    preview = subprocess.run(command + ["-WhatIf"], capture_output=True, text=True)
    assert preview.returncode == 0, preview.stdout + preview.stderr
    assert not output.exists()
    capture = subprocess.run(command, capture_output=True, text=True)
    assert capture.returncode == 0, capture.stdout + capture.stderr
    with ZipFile(next(output.glob("*.zip"))) as archive:
        assert "profile/config.txt" not in archive.namelist()
        tail = archive.read("game/logs/game.log")
        assert len(tail) <= 1024
        assert tail.endswith(b"last-message")
        manifest = json.loads(archive.read("manifest.json").decode("utf-8-sig"))
        assert any("oversized" in note for note in manifest["notes"])
        assert manifest["files"][0]["tail_only"] is True


def test_collector_large_tail_keeps_newest_message(tmp_path):
    import subprocess
    logs = tmp_path / 'logs'
    logs.mkdir()
    (logs / 'game.log').write_bytes(b'x' * (3 * 1024 * 1024) + b'NEWEST-MESSAGE')
    result = subprocess.run([
        'powershell', '-NoProfile', '-File', str(ROOT / 'tools/Collect-FractalLogs.ps1'),
        '-ProfilePath', str(tmp_path / 'missing-profile'), '-SteamPath', str(tmp_path / 'missing-steam'),
        '-GameLogPath', str(logs), '-Destination', str(tmp_path / 'out'), '-LogTailKiB', '2048',
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    with ZipFile(next((tmp_path / 'out').glob('*.zip'))) as archive:
        assert archive.read('game/logs/game.log').endswith(b'NEWEST-MESSAGE')


def test_destination_junction_is_rejected_without_is_junction_api(workspace, tmp_path, monkeypatch):
    import subprocess
    output = tmp_path / 'Builds'
    output.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    junction = output / 'Crisol'
    result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(outside)], capture_output=True)
    if result.returncode:
        pytest.skip('junction creation unavailable')
    monkeypatch.setattr(type(junction), 'is_junction', lambda self: False)
    try:
        with pytest.raises(ValueError):
            publish(workspace, tmp_path)
        assert not list(outside.iterdir())
    finally:
        junction.rmdir()


@pytest.mark.parametrize("option", ["-WhatIf", "-DryRun"])
def test_share_preview_does_not_invoke_mutating_cmdlets(option):
    import subprocess
    # Shadow all mutators with failures: preview must never call any of them.
    script = ROOT / "tools/Setup-BuildShare.ps1"
    command = (
        "$env:COMPUTERNAME = 'CORSARIO'; "
        # Preview must also work before the dedicated root exists. Do not
        # inspect the developer's real Builds directory in a unit test.
        "function Test-Path { return $false }; "
        "function New-SmbShare { throw 'MUTATION' }; "
        "function New-NetFirewallRule { throw 'MUTATION' }; "
        "function Set-Acl { throw 'MUTATION' }; "
        "function New-Item { throw 'MUTATION' }; "
        f"& '{script}' {option}"
    )
    result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PREVIEW ONLY" in result.stdout
    assert "Other existing firewall rules are left untouched" in result.stdout


def test_share_preflight_rejects_nested_junction(tmp_path):
    import subprocess
    tree = tmp_path / 'Builds'
    project = tree / 'Crisol'
    project.mkdir(parents=True)
    outside = tmp_path / 'outside'
    outside.mkdir()
    junction = project / 'leak'
    result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(outside)], capture_output=True)
    if result.returncode:
        pytest.skip('junction creation unavailable')
    try:
        script_literal = str(ROOT / 'tools/Setup-BuildShare.ps1').replace("'", "''")
        tree_literal = str(tree).replace("'", "''")
        # Load the real preflight function without executing share setup on
        # the host. All filesystem traversal stays inside this test's tree.
        command = f"""
            $ErrorActionPreference = 'Stop'
            $tokens = $null; $errors = $null
            $ast = [Management.Automation.Language.Parser]::ParseFile(
                '{script_literal}', [ref]$tokens, [ref]$errors)
            $definition = $ast.Find({{ param($node)
                $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
                $node.Name -eq 'Assert-BuildTree'
            }}, $true)
            . ([scriptblock]::Create($definition.Extent.Text))
            try {{ Assert-BuildTree '{tree_literal}'; exit 0 }}
            catch {{ Write-Output $_; exit 3 }}
        """
        check = subprocess.run(['powershell', '-NoProfile', '-Command', command], capture_output=True, text=True)
        assert check.returncode == 3, check.stdout + check.stderr
        assert 'Unsafe descendant' in check.stdout
    finally:
        junction.rmdir()
