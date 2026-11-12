"""Assemble the small beta kit; development records stay in build/work."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

from prepare import commands, HELPERS

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT/'build/rh8_36-win'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def helper(action, package_name):
    operation = f'install "%~dp0{package_name}"' if action == 'install' else 'uninstall rhino-urbanism-toolkit'
    return r'''@echo off
setlocal
if not exist "%ProgramFiles%\Rhino 8\System\Yak.exe" (
 echo Rhino 8 was not found in Program Files. See START_HERE.txt.
 pause
 exit /b 2
)
tasklist /FI "IMAGENAME eq Rhino.exe" /NH 2>nul | findstr /I /C:"Rhino.exe" >nul
if not errorlevel 1 (
 echo Save your drawings and close ALL Rhino windows, then run this helper again.
 pause
 exit /b 3
)
"%ProgramFiles%\Rhino 8\System\Yak.exe" ''' + operation + r'''
if errorlevel 1 (
 echo The operation did not complete. Keep the message above and ask for help.
 pause
 exit /b 1
)
echo Done. See START_HERE.txt for the next step.
pause
exit /b 0
'''


def build():
    package = max(BUILD.glob('*-rh8_36-win.yak'), key=lambda p: p.stat().st_mtime_ns)
    with zipfile.ZipFile(package) as z:
        manifest = z.read('manifest.yml').decode('utf-8-sig')
    version = re.search(r'^version:\s*(\S+)', manifest, re.M)[1]
    release = json.loads((ROOT/'packaging/release.json').read_text())
    checks = json.loads((BUILD/'preparation-checks.json').read_text(encoding='utf-8-sig'))
    assert checks['passed'] >= 100, 'Verify the current package before assembling the kit.'
    assert version.split('+')[0] == release['version']
    assert re.fullmatch(r'[0-9A-Za-z.+-]+', version)
    folder = ROOT/'release'/version
    assert not folder.exists(), 'Release kits are immutable; build a new candidate instead of overwriting one.'
    folder.mkdir(parents=True)
    shutil.copyfile(package, folder/package.name)
    shutil.copyfile(BUILD/'RUT.rui', folder/'RUT.rui')
    shutil.copyfile(ROOT/'LICENSE', folder/'LICENSE')
    shutil.copyfile(ROOT/'START_HERE.txt', folder/'START_HERE.txt')
    for name, action in [('Install-RUT.cmd', 'install'), ('Remove-RUT.cmd', 'uninstall')]:
        (folder/name).write_bytes(helper(action, package.name).replace('\n', '\r\n').encode('ascii'))
    # Corresponding project sources from this working tree, not an older remote
    # branch. Explicit roots exclude drawings, credentials, caches and work/.
    source_files = {ROOT/e['source'] for e in commands()}
    source_files |= {ROOT/(name+'.py') for name in HELPERS}
    source_files |= {ROOT/'rhino-urbanism-toolkit.rhproj', ROOT/'LICENSE', ROOT/'START_HERE.txt'}
    source_files |= {ROOT/'packaging'/name for name in (
        'Build.ps1', 'Verify-Build.ps1', 'prepare.py', 'finish_toolbar.py',
        'rut_bootstrap.py', 'release.json', 'toolbar_layout.json')}
    source_files |= {ROOT/'packaging/commands'/(entry['command']+'.py') for entry in commands()}
    source_files |= {p for p in (ROOT/'assets/toolbar/v1').rglob('*')
        if p.is_file() and p.suffix.lower() in {'.svg', '.json'}}
    source_name = 'RUT-'+version+'-source.zip'
    with zipfile.ZipFile(folder/source_name, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(source_files):
            relative = path.relative_to(ROOT)
            assert not set(relative.parts) & {'.git', '.codex', 'work', 'build', 'release'}
            z.write(path, 'source/'+relative.as_posix())
        z.writestr('source/BUILD.txt', 'Requires Windows, Rhino 8.36 and Python 3.\n'
            'From this folder run: packaging/Build.ps1 -PythonExe python\n')
    sums = {p.relative_to(folder).as_posix(): digest(p.read_bytes())
        for p in sorted(folder.rglob('*')) if p.is_file()}
    archive = folder.parent/('RUT-'+version+'-Windows.zip')
    assert not archive.exists()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                z.write(path, folder.name+'/'+path.relative_to(folder).as_posix())
    with zipfile.ZipFile(archive) as z:
        for name, expected in sums.items():
            assert digest(z.read(folder.name+'/'+name)) == expected, name
    report = {'version': version, 'folder': str(folder), 'archive': str(archive),
        'archive_sha256': digest(archive.read_bytes()), 'verified_files': len(sums),
        'source_files': len(source_files), 'build_checks': checks['passed'], 'published': False,
        'file_sha256': sums}
    (ROOT/'build/release-kit.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    build()
