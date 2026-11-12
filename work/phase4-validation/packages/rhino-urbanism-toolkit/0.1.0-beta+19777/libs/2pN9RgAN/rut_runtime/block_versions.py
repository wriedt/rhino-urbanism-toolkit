"""Format-preserving block family plans. Pure Python; no Rhino dependencies."""
import re


def alpha_number(text):
    value = 0
    for char in text.upper():
        value = value * 26 + ord(char) - ord('A') + 1
    return value


def alpha_text(value, lower=False):
    text = ''
    while value:
        value, digit = divmod(value - 1, 26)
        text = chr(65 + digit) + text
    return text.lower() if lower else text


def strip_duplicates(name, names):
    """Strip copy words, and numeric branches only with an exact parent as evidence."""
    occupied = {n.casefold() for n in names}
    base, branches, copies = name, [], 0
    while True:
        copy = re.search(r' copy$', base, re.I)
        if copy:
            copies += 1
            base = base[:copy.start()]
            continue
        branch = re.search(r'[_ -]+([0-9]+)$', base)
        parent = base[:branch.start()] if branch else ''
        parent_has_version = re.search(r'[0-9]$|(?:^|[_ -])[A-Za-z]{1,3}$', parent)
        if branch and parent_has_version and parent.casefold() in occupied:
            branches.insert(0, int(branch.group(1)))
            base = base[:branch.start()]
            continue
        break
    return base, tuple(branches), copies


def describe(name, token, start=None):
    """An explicit token occurrence is the escape hatch for ambiguous names."""
    if not token:
        raise ValueError('Enter the version part, for example 02, A, or A01.')
    start = name.rfind(token) if start is None else start
    if start < 0 or name[start:start + len(token)] != token:
        raise ValueError('The version part must occur in the example block name.')
    match = re.fullmatch(r'([A-Za-z]*)([0-9]+)', token)
    if match:
        marker, digits = match.groups()
        kind, width, value, lower = 'number', len(digits), int(digits), False
    elif re.fullmatch(r'[A-Za-z]+', token):
        if not (token.isupper() or token.islower()):
            raise ValueError('Alphabetic versions must use consistent letter case.')
        marker, kind, width = '', 'alpha', 0
        value, lower = alpha_number(token), token.islower()
    else:
        raise ValueError('Use a numeric, alphabetic, or letter-and-number version part.')
    return dict(prefix=name[:start], suffix=name[start + len(token):], marker=marker,
                kind=kind, width=width, value=value, lower=lower, token=token,
                example=name)


def suggestions(name, names):
    base, _, _ = strip_duplicates(name, names)
    candidates = []
    # Explicit v is a formatting marker; preserve it during a family rename.
    explicit = re.search(r'[vV][0-9]+$', base)
    compound = re.search(r'(?:^|[_ -])([A-Za-z]{1,2}[0-9]+)$', base)
    trailing_number = re.search(r'[0-9]+$', base)
    trailing_alpha = re.search(r'(?:^|[_ -])([A-Za-z]{1,3})$', base)
    joined_alpha = re.search(r'(?<=[a-z])([A-Z]{1,3})$', base)
    for match, group in [(explicit, 0), (compound, 1), (trailing_number, 0),
                         (trailing_alpha, 1), (joined_alpha, 1)]:
        if match:
            try:
                spec = describe(base, match.group(group), match.start(group))
            except ValueError:
                continue
            if not any(s['prefix'] == spec['prefix'] and s['token'] == spec['token']
                       and s['suffix'] == spec['suffix'] for s in candidates):
                candidates.append(spec)
    # Interior numeric tokens are available when the last number is a dimension.
    for match in reversed(list(re.finditer(r'[0-9]+', base))):
        before, after = base[:match.start()], base[match.end():]
        if (re.search(r'[Øø×x]$', before) or re.match(r'(?:[x×][0-9]|(?:mm|cm|km|m)\b)', after, re.I)
                or (match.start() == 0 and re.match(r'D(?:[_ -]|$)', after, re.I))):
            continue
        spec = describe(base, match.group(), match.start())
        if not any(s['prefix'] == spec['prefix'] and s['token'] == spec['token'] for s in candidates):
            candidates.append(spec)
    # Do not suggest measurement tokens from the earlier terminal-number pass.
    candidates = [s for s in candidates if not (
        re.search(r'[Øø×x]$', s['prefix']) or
        re.match(r'(?:[x×][0-9]|(?:mm|cm|km|m)\b)', s['suffix'], re.I) or
        (not s['prefix'] and re.match(r'D(?:[_ -]|$)', s['suffix'], re.I)))]
    return candidates


def pattern(spec):
    if spec['kind'] == 'plain':
        return re.compile(re.escape(spec['prefix']), re.I)
    token = re.escape(spec['marker']) + r'([0-9]+)' if spec['kind'] == 'number' else r'([A-Za-z]+)'
    return re.compile(re.escape(spec['prefix']) + token + re.escape(spec['suffix']), re.I)


def members(definitions, spec):
    names = [d['name'] for d in definitions]
    regex = pattern(spec)
    found = []
    for definition in definitions:
        base, branches, copies = strip_duplicates(definition['name'], names)
        match = regex.fullmatch(base)
        if not match:
            continue
        token = match.group(1) if spec['kind'] != 'plain' else ''
        value = (int(token) if spec['kind'] == 'number' else
                 alpha_number(token) if token else 0)
        found.append(dict(definition, value=value, branches=branches, copies=copies,
                          base=base, width=len(token)))
    return sorted(found, key=lambda d: (d['value'], bool(d['branches'] or d['copies']),
                                        d['branches'], d['copies'], d['name'].casefold()))


def format_name(spec, value, width=None):
    if value < 0 or (spec['kind'] == 'alpha' and value < 1):
        raise ValueError('Invalid starting version.')
    token = (spec['marker'] + str(value).zfill(width if width is not None else spec['width'])
             if spec['kind'] == 'number' else alpha_text(value, spec['lower']))
    return spec['prefix'] + token + spec['suffix']


def validate_targets(definitions, rows):
    by_id = {r['id']: r for r in rows}
    occupied = set()
    for definition in definitions:
        row = by_id.get(definition['id'])
        if row and not definition['editable']:
            raise ValueError('The family contains a linked/reference definition: ' + definition['name'])
        name = row['new'] if row else definition['name']
        if not name.strip():
            raise ValueError('Block names cannot be empty.')
        if name.casefold() in occupied:
            raise ValueError('A block already uses the proposed name: ' + name)
        occupied.add(name.casefold())


def fingerprint(definitions):
    return sorted((d['index'], d['id'], d['name'], d['editable']) for d in definitions)


def rename_plan(definitions, spec, prefix, suffix):
    family = members(definitions, spec)
    if not family:
        raise ValueError('No definitions match this family.')
    destination = dict(spec, prefix=prefix, suffix=suffix)
    family_ids = {d['id'] for d in family}
    if any(d['id'] not in family_ids for d in members(definitions, destination)):
        raise ValueError('That family name is already in use. Choose a different shared name.')
    rows = []
    for definition in family:
        # Replace only the family portions; preserve version spelling and duplicates.
        name = definition['name']
        middle = name[len(spec['prefix']):len(definition['base']) - len(spec['suffix'])
                      if spec['suffix'] else len(definition['base'])]
        duplicates = name[len(definition['base']):]
        new = prefix + middle + suffix + duplicates
        if new != name:
            rows.append(dict(index=definition['index'], id=definition['id'], old=name, new=new))
    validate_targets(definitions, rows)
    return dict(renames=rows, snapshot=fingerprint(definitions), operation='rename',
                family_count=1, members=family)


def consolidation_plan(definitions, spec, start_lowest=False):
    family = members(definitions, spec)
    if not family:
        raise ValueError('No definitions match this family.')
    start = family[0]['value'] if start_lowest else 1
    width = max([spec['width']] + [d['width'] for d in family]) if spec['kind'] == 'number' else 0
    rows = []
    for value, definition in enumerate(family, start):
        new = format_name(spec, value, width)
        if new != definition['name']:
            rows.append(dict(index=definition['index'], id=definition['id'],
                             old=definition['name'], new=new))
    validate_targets(definitions, rows)
    return dict(renames=rows, snapshot=fingerprint(definitions), operation='consolidate',
                family_count=1, members=family)


def next_version(definitions, spec, reserved=()):
    family = members(definitions, spec)
    if not family:
        raise ValueError('No definitions match this family.')
    width = max([spec['width']] + [d['width'] for d in family]) if spec['kind'] == 'number' else 0
    value = max(d['value'] for d in family) + 1
    name = format_name(spec, value, width)
    occupied = {d['name'].casefold() for d in definitions} | {n.casefold() for n in reserved}
    while name.casefold() in occupied:
        value += 1
        name = format_name(spec, value, width)
    return name
