param([string]$BuildFolder = 'build/rh8_36-win')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$folder = [IO.Path]::GetFullPath((Join-Path $root $BuildFolder))
$project = Get-Content (Join-Path $root 'rhino-urbanism-toolkit.rhproj') -Raw | ConvertFrom-Json
$inventory = Get-Content (Join-Path $root 'build/stage/inventory.json') -Raw | ConvertFrom-Json
[xml]$rui = Get-Content (Join-Path $folder 'rhino-urbanism-toolkit.rui') -Raw
[xml]$fallback = Get-Content (Join-Path $folder 'RUT.rui') -Raw
$checks = [Collections.Generic.List[string]]::new()
function Check($condition, $name) {
    if (-not $condition) { throw $name }
    $checks.Add($name)
}
Check ($project.codes.Count -eq 18) '18 command entries'
Check (@($project.codes | Where-Object helpUri).Count -eq 0) 'No links to developer command notes'
Check (($inventory.resources -join '|') -ceq 'LICENSE|START_HERE.txt') 'Only license and short start note are bundled'
Check ($rui.SelectNodes('//tool_bars/tool_bar/tool_bar_item[left_macro_id]').Count -eq 18) '18 toolbar buttons'
$layout=Get-Content (Join-Path $PSScriptRoot 'toolbar_layout.json') -Raw | ConvertFrom-Json
Check ($rui.RhinoUI.tool_bar_groups.tool_bar_group.text.locale_1033 -ceq $layout.display_name) 'Exact visible plugin title'
Check (@($rui.RhinoUI.tool_bars.tool_bar).Count -eq 1) 'One toolbar tab'
$bar=$rui.RhinoUI.tool_bars.tool_bar
Check ($bar.text.locale_1033 -ceq $layout.display_name) 'Exact single tab title'
Check (@($rui.RhinoUI.tool_bar_groups.tool_bar_group.tool_bar_group_item).Count -eq 1) 'One toolbar group entry'
$items=@($bar.tool_bar_item)
Check (@($items | Where-Object button_style -eq 'spacer').Count -eq 3) 'Three category separators'
$position=0
for($categoryIndex=0;$categoryIndex -lt $layout.categories.Count;$categoryIndex++){
    $category=$layout.categories[$categoryIndex]
    if($categoryIndex -gt 0){
        Check ($items[$position].button_style -eq 'spacer' -and -not $items[$position].left_macro_id) ('Separator before '+$category.name)
        $position++
    }
    $actualCommands=@(for($i=0;$i -lt $category.commands.Count;$i++){ $items[$position+$i].text.locale_1033 })
    Check (($actualCommands -join '|') -ceq ($category.commands -join '|')) ($category.name+' exact command order')
    $position+=$category.commands.Count
}
Check ($position -eq $items.Count) 'No extra toolbar items'
Check (-not $fallback.RhinoUI.plug_in_guid) 'Standalone toolbar has no plugin binding'
Check ($fallback.RhinoUI.guid -eq $rui.RhinoUI.guid) 'Standalone toolbar preserves UI identity'
Check ($fallback.RhinoUI.tool_bars.OuterXml -ceq $rui.RhinoUI.tool_bars.OuterXml) 'Standalone toolbar preserves layout'
Check ($fallback.RhinoUI.macros.OuterXml -ceq $rui.RhinoUI.macros.OuterXml) 'Standalone toolbar preserves command actions'
Check ($fallback.RhinoUI.icons.OuterXml -ceq $rui.RhinoUI.icons.OuterXml) 'Standalone toolbar preserves theme icons'
foreach ($command in $project.codes) {
    $macro = @($rui.RhinoUI.macros.macro_item | Where-Object guid -eq $command.id)
    Check ($macro.Count -eq 1 -and $macro[0].script -eq ('! _' + $command.title)) ($command.title + ' toolbar action')
    $icon = @($rui.RhinoUI.icons.icon | Where-Object guid -eq $command.id)
    Check ($icon.Count -eq 1 -and $icon[0].light.svg -and $icon[0].dark.svg) ($command.title + ' theme icons')
    foreach ($mode in @('light', 'dark')) {
        $expected = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($command.image.$mode.data))
        [xml]$expectedSvg = $expected
        Check ($icon[0].$mode.svg.OuterXml -eq $expectedSvg.DocumentElement.OuterXml) ($command.title + ' exact ' + $mode + ' SVG')
    }
}
$resource = Join-Path $folder 'src/rhino-urbanism-toolkit/Resources/Plugin.Data.resources'
$reader = [Resources.ResourceReader]::new($resource)
try {
    $items = $reader.GetEnumerator()
    $embedded = $null
    while ($items.MoveNext()) {
        if ($items.Key -eq 'PROJECT-DATA') {
            $embedded = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($items.Value)) | ConvertFrom-Json
        }
    }
} finally { $reader.Dispose() }
Check ($embedded.codes.Count -eq 18) '18 compiled command scripts'
$runtime = @($embedded.libraries | Where-Object { $_.type -eq 'source' })
Check ($runtime.Count -eq 1) 'One embedded Python runtime library'
$actual = @($runtime[0].library.codes | ForEach-Object title | Sort-Object)
$expected = @($inventory.runtime_files | Sort-Object)
Check (-not (Compare-Object $actual $expected)) 'Embedded library matches the runtime file allowlist'
Check ($project.settings.buildTarget.host.os -eq 'windows') 'Windows-only project target'
$yak = @(Get-ChildItem $folder -Filter '*-rh8_36-win.yak')
Check ($yak.Count -ge 1) 'Windows-tagged Yak package'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead(($yak | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName)
try {
    $names = @($zip.Entries | ForEach-Object FullName)
    $allowed = @('manifest.yml', 'rhino-urbanism-toolkit.rhp', 'rhino-urbanism-toolkit.rui', 'RUT.rui') +
        @($inventory.resources | ForEach-Object { 'shared/' + $_ })
    Check (-not (Compare-Object ($names | Sort-Object) ($allowed | Sort-Object))) 'Yak contains only plugin, toolbars, license and short start note'
    $entry=$zip.GetEntry('rhino-urbanism-toolkit.rui')
    $stream=[IO.StreamReader]::new($entry.Open())
    try {$packagedRui=$stream.ReadToEnd()} finally {$stream.Dispose()}
    Check ($packagedRui -ceq (Get-Content (Join-Path $folder 'rhino-urbanism-toolkit.rui') -Raw)) 'Yak includes the final grouped toolbar'
    $stream=[IO.StreamReader]::new($zip.GetEntry('RUT.rui').Open())
    try {$packagedFallback=$stream.ReadToEnd()} finally {$stream.Dispose()}
    Check ($packagedFallback -ceq (Get-Content (Join-Path $folder 'RUT.rui') -Raw)) 'Yak includes the checked standalone toolbar'
    foreach($name in $inventory.resources){
        $stream=[IO.StreamReader]::new($zip.GetEntry('shared/'+$name).Open())
        try {$packagedText=$stream.ReadToEnd()} finally {$stream.Dispose()}
        Check ($packagedText -ceq (Get-Content (Join-Path $root $name) -Raw)) ($name+' packaged resource matches source')
    }
} finally { $zip.Dispose() }
$report = @{passed=$checks.Count; checks=$checks; build=$folder; live_Rhino_validation='Outstanding'}
$report | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $folder 'preparation-checks.json')
Write-Output ('Passed ' + $checks.Count + ' build-content checks; live Rhino validation remains outstanding.')
