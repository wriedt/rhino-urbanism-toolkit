#! python 3
import json
from pathlib import Path
import Rhino
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'work/phase4-validation'
report = {
    'rut_registered_commands': [n for n in Rhino.Commands.Command.GetCommandNames(True,False) if n.startswith('RUT')],
    'installed_rhp_files': [str(p) for p in (OUT/'packages').rglob('*.rhp')],
    'active_manifest_exists': (OUT/'packages/rhino-urbanism-toolkit/manifest.txt').exists(),
}
(OUT/'uninstall.json').write_text(json.dumps(report,indent=2))
