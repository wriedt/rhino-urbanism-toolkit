param(
    [string]$PythonExe = 'python',
    [string]$RhinoCodeExe = 'C:\Program Files\Rhino 8\System\RhinoCode.exe',
    [string]$Version
)
$ErrorActionPreference='Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    if(-not $Version){$Version=(Get-Content "$PSScriptRoot/release.json" -Raw | ConvertFrom-Json).version}
    & $PythonExe packaging/prepare.py
    if($LASTEXITCODE -ne 0){throw 'Preparing the project failed.'}
    & $RhinoCodeExe project build ./rhino-urbanism-toolkit.rhproj --buildversion $Version --buildtarget 8.36-win
    if($LASTEXITCODE -ne 0){throw 'Rhino plugin build failed.'}
    & $PythonExe packaging/finish_toolbar.py
    if($LASTEXITCODE -ne 0){throw 'Applying the toolbar layout failed.'}
    & "$PSScriptRoot/Verify-Build.ps1"
} finally { Pop-Location }
