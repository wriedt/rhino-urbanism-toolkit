param(
    [string]$Package,
    [switch]$Remove
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$testRoot = [IO.Path]::GetFullPath((Join-Path $root 'work/phase4-validation'))
$packageRoot = [IO.Path]::GetFullPath((Join-Path $testRoot 'packages'))
if (-not $packageRoot.StartsWith($testRoot + [IO.Path]::DirectorySeparatorChar)) {
    throw 'The test package directory must remain inside the phase 4 workspace.'
}
[void][Reflection.Assembly]::LoadFrom('C:\Program Files\Rhino 8\System\YamlDotNet.dll')
[void][Reflection.Assembly]::LoadFrom('C:\Program Files\Rhino 8\System\Yak.Core.dll')
$client = [Yak.YakClient]::new()
$client.PackageFolder = $packageRoot
New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null
if ($Remove) {
    $result = $client.Remove('rhino-urbanism-toolkit')
    Write-Output ('Removed from isolated test installation: ' + $result)
} else {
    if (-not $Package) {
        $Package = (Get-ChildItem (Join-Path $root 'build/rh8_36-win') -Filter '*.yak' |
                    Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
    }
    if (-not (Test-Path -LiteralPath $Package)) { throw 'Package not found.' }
    $client.Install([IO.Path]::GetFullPath($Package))
    Write-Output ('Installed local Yak into ' + $packageRoot)
}
$manifestPath = Join-Path $packageRoot 'rhino-urbanism-toolkit/manifest.txt'
$activeVersion = if (Test-Path -LiteralPath $manifestPath) { (Get-Content -LiteralPath $manifestPath -Raw).Trim() } else { $null }
$rhp = if ($activeVersion) {
    $activeFolder = Join-Path $packageRoot ('rhino-urbanism-toolkit/' + $activeVersion)
    Get-ChildItem $activeFolder -Filter '*.rhp' | Select-Object -ExpandProperty FullName
} else { @() }
@{folder=$packageRoot; active_version=$activeVersion; plugin_files=@($rhp); action=$(if($Remove){'remove'}else{'install'})} |
    ConvertTo-Json -Depth 4 | Set-Content (Join-Path $testRoot 'installation.json')
