#! python 3
"""Read-only audit. Run in Rhino's Python 3 Script Editor before package tests."""
import json
import Rhino

NAMES = (
    'IsolateLayer', 'UnisolateLayer', 'IsolateLockLayer', 'UnisolateLockLayer',
    'ShowAllLayers', 'UnlockAllLayers', 'ShowAndUnlockAllLayers',
    'ToggleLayerExpansion', 'CreateBlockVersion', 'ConsolidateBlockVersions',
    'RenameBlockFamily', 'AssignBlockLayer', 'ApplyBlockLayers',
    'ShowBlockLayers', 'QuickFloorArea', 'FloorArea', 'PushPullCurve', 'ShapeBuilder')


def audit():
    aliases = Rhino.ApplicationSettings.CommandAliasList
    existing = {name.lower(): name for name in aliases.GetNames()}
    conflicts = {}
    for suffix in NAMES:
        name = existing.get(('RUT' + suffix).lower())
        if name:
            conflicts[name] = aliases.GetMacro(name)
    print(json.dumps(conflicts, indent=2))
    print('Read-only audit: {0} matching aliases; none changed.'.format(len(conflicts)))
    return conflicts


if __name__ == '__main__':
    audit()
