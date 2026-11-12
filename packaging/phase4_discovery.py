#! python 3
"""Do not explicitly load the plugin: verify Package Manager discovery."""
import json
from pathlib import Path
import sys
import Rhino
OUT=Path(__file__).resolve().parents[1]/'work/phase4-validation'
report={'explicit_plugin_load':False}
report['rut_aliases']=[n for n in Rhino.ApplicationSettings.CommandAliasList.GetNames() if n.upper().startswith('RUT')]
report['commands_before_dispatch']=[n for n in Rhino.Commands.Command.GetCommandNames(True,False) if n.startswith('RUT')]
before=len(Rhino.RhinoApp.CommandHistoryWindowText)
report['dispatched']=Rhino.RhinoApp.RunScript('_RUTShowAllLayers',False)
report['history']=Rhino.RhinoApp.CommandHistoryWindowText[before:]
report['module_paths']={n:getattr(m,'__file__',None) for n,m in sys.modules.items() if n in ['layer_tools','rut_runtime.rut_bootstrap']}
report['success']=(len(report['commands_before_dispatch'])==18 and not report['rut_aliases'] and bool(report['module_paths']) and 'Traceback' not in report['history'])
(OUT/'automatic-discovery.json').write_text(json.dumps(report,indent=2))
