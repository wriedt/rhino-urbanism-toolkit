param([switch]$Remove)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$out=Join-Path $root 'work/phase4-validation'
$packageRoot=Join-Path ([Environment]::GetFolderPath('ApplicationData')) 'McNeel/Rhinoceros/packages/8.0'
$packageFolder=Join-Path $packageRoot 'rhino-urbanism-toolkit'
$marker=Join-Path $out 'temporary-standard-install.json'
[void][Reflection.Assembly]::LoadFrom('C:\Program Files\Rhino 8\System\YamlDotNet.dll')
[void][Reflection.Assembly]::LoadFrom('C:\Program Files\Rhino 8\System\Yak.Core.dll')
$client=[Yak.YakClient]::new()
$client.PackageFolder=$packageRoot
if($Remove){
    if(-not (Test-Path -LiteralPath $marker)){throw 'No test-owned install marker; refusing to remove anything.'}
    $saved=Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
    if($saved.folder -ne $packageFolder -or -not $saved.was_absent){throw 'Installation ownership could not be verified.'}
    $removed=$client.Remove('rhino-urbanism-toolkit')
    $saved | Add-Member -NotePropertyName removed -NotePropertyValue $removed -Force
    $saved | Add-Member -NotePropertyName folder_absent_after -NotePropertyValue (-not (Test-Path -LiteralPath $packageFolder)) -Force
    $saved | ConvertTo-Json | Set-Content -LiteralPath $marker
    Write-Output ('Temporary normal-folder installation removed: '+$removed)
}else{
    if(Test-Path -LiteralPath $packageFolder){throw 'An existing RUT package is present; refusing to change it.'}
    $package=(Get-ChildItem (Join-Path $root 'build/rh8_36-win') -Filter '*.yak' | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
    @{folder=$packageFolder;was_absent=$true;package=$package;removed=$false} | ConvertTo-Json | Set-Content -LiteralPath $marker
    $client.Install($package)
    Write-Output ('Temporary normal-folder installation created: '+$packageFolder)
}
