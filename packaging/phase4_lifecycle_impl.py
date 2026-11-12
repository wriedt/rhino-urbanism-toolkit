import json
from pathlib import Path
import sys
import Rhino
import System
import scriptcontext as sc
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/phase4-validation'
report = {}
for name in ['Rhino.UI.ThemeSettings', 'Rhino.ApplicationSettings.AppearanceSettings']:
    t = System.Type.GetType(name+', RhinoCommon')
    if t:
        report[name] = [str(m) for m in t.GetMethods() if any(k in m.Name.lower() for k in ['theme','color','mode','default'])]
report['dark'] = Rhino.Runtime.HostUtils.RunningInDarkMode
report['windows_version'] = str(System.Environment.OSVersion.VersionString)
report['is_64_bit'] = System.Environment.Is64BitProcess
report['commands'] = [n for n in Rhino.Commands.Command.GetCommandNames(True,False) if n.startswith('RUT')]
report['active_objects'] = len(list((globals().get('__rhino_doc__') or sc.doc).Objects))
report['modules'] = {name:getattr(m,'__file__',None) for name,m in sys.modules.items()
                     if name in ['pushpull_mixed','shape_builder_leftovers']}
(OUT/'lifecycle-probe.json').write_text(json.dumps(report,indent=2))
Rhino.ApplicationSettings.AppearanceSettings.SetToLightMode()
