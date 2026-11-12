"""Apply RUT's visible toolbar title/categories to the built RUI and Yak."""
import copy
import json
from pathlib import Path
import re
import sys
import uuid
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = json.loads((Path(__file__).with_name('toolbar_layout.json')).read_text())
NAMESPACE = uuid.UUID('6ac6211b-d98c-47f5-95c0-5a542d379a2c')


def label(parent, value):
    ET.SubElement(ET.SubElement(parent, 'text'), 'locale_1033').text = value


def finish(folder):
    folder = Path(folder).resolve()
    rui = folder / 'rhino-urbanism-toolkit.rui'
    original = rui.read_text(encoding='utf-8-sig')
    tree = ET.ElementTree(ET.fromstring(original))
    root = tree.getroot()
    # Rhino 8 caches a file's toolbar definitions by its RUI identity. Give this
    # new layout its own stable UI identity while retaining the plugin binding
    # and every existing command/macro ID.
    root.set('guid', str(uuid.uuid5(NAMESPACE, 'toolbar-layout:single-spacers-v1')))
    buttons = {item.findtext('text/locale_1033'): copy.deepcopy(item)
               for item in root.findall('./tool_bars/tool_bar/tool_bar_item')
               if item.find('left_macro_id') is not None}
    grouped = [c for category in LAYOUT['categories'] for c in category['commands']]
    if len(set(grouped)) != len(grouped) or set(grouped) != set(buttons):
        raise ValueError('Toolbar categories must cover every built command exactly once.')
    group = root.find('./tool_bar_groups/tool_bar_group')
    group_guid = str(uuid.uuid5(NAMESPACE, 'toolbar-group:single-spacers-v1'))
    for attribute in ('guid', 'dock_bar_guid32', 'dock_bar_guid64', 'active_tool_bar_group'):
        group.set(attribute, group_guid)
    group.find('text/locale_1033').text = LAYOUT['display_name']
    group.set('hide_single_tab', 'False')
    for old in list(group.findall('tool_bar_group_item')):
        group.remove(old)
    bars = root.find('tool_bars')
    bars.clear()
    guid = str(uuid.uuid5(NAMESPACE, 'toolbar:single-spacers-v1'))
    entry = ET.SubElement(group, 'tool_bar_group_item',
                          {'guid': guid, 'major_version': '1', 'minor_version': '1'})
    label(entry, LAYOUT['display_name'])
    ET.SubElement(entry, 'tool_bar_id').text = guid
    bar = ET.SubElement(bars, 'tool_bar', {'guid': guid,
        'bitmap_id': str(NAMESPACE), 'item_display_style': 'control_only'})
    label(bar, LAYOUT['display_name'])
    for index, category in enumerate(LAYOUT['categories']):
        if index:
            ET.SubElement(bar, 'tool_bar_item', {
                'guid': str(uuid.uuid5(NAMESPACE, 'toolbar-separator:' + category['name'])),
                'button_style': 'spacer'})
        for command in category['commands']:
            bar.append(buttons[command])
    placement = group.find('dock_bar_info')
    if placement is not None:
        placement.set('mru_width', '600')
        placement.set('float_size', '600,80')
        placement.set('float_point', '100,200')
    # Replace only layout sections so approved SVG markup stays byte-for-byte
    # unchanged; serializing the whole document rewrites SVG namespaces.
    modified = re.sub(r'(<RhinoUI\b[^>]*\bguid=")[^"]+("\s+plug_in_guid=)',
                      lambda m: m.group(1) + root.get('guid') + m.group(2), original, count=1)
    for tag in ('tool_bar_groups', 'tool_bars'):
        element = root.find(tag)
        ET.indent(element, space='  ')
        modified, count = re.subn(r'<' + tag + r'>.*?</' + tag + r'>',
            lambda match: ET.tostring(element, encoding='unicode'), modified, flags=re.S)
        if count != 1:
            raise ValueError('Expected one ' + tag + ' layout section.')
    rui.write_text(modified, encoding='utf-8')
    # Existing Rhino workspaces may retain an older plugin-bound RUI. Supply a
    # standalone toolbar with the same IDs for an explicit UI refresh.
    standalone = re.sub(r' plug_in_guid="[^"]+"', '', modified)
    fallback = folder / 'RUT.rui'
    fallback.write_text(standalone, encoding='utf-8')
    # Update only the toolbar member; preserve the assembly, manifest and help.
    packages = list(folder.glob('*-rh8_36-win.yak'))
    package = max(packages, key=lambda p: p.stat().st_mtime_ns)
    temporary = package.with_suffix('.yak.tmp')
    with zipfile.ZipFile(package) as source, zipfile.ZipFile(temporary, 'w') as target:
        for entry in source.infolist():
            # Do not ship the experimental native-container import file.
            if entry.filename == 'RUT.rhc':
                continue
            if entry.filename == fallback.name:
                continue
            target.writestr(entry, rui.read_bytes() if entry.filename == rui.name else source.read(entry))
        target.writestr(fallback.name, fallback.read_bytes())
    temporary.replace(package)
    print('Applied single toolbar and standalone toolbar fallback to RUI and Yak.')


if __name__ == '__main__':
    finish(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'build/rh8_36-win')
