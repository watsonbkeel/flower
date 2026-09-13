#!/usr/bin/env python3
from pathlib import Path
import re, sys
root = Path(__file__).resolve().parents[1] / '.agents' / 'skills'
errors = []
for path in sorted(root.glob('*/SKILL.md')):
    text = path.read_text(encoding='utf-8')
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if not m:
        errors.append(f'{path}: missing YAML frontmatter')
        continue
    fm = m.group(1)
    name = re.search(r'^name:\s*(.+)$', fm, re.M)
    desc = re.search(r'^description:\s*(.+)$', fm, re.M)
    if not name or not re.fullmatch(r'[a-z0-9-]+', name.group(1).strip()):
        errors.append(f'{path}: invalid name')
    if not desc or not desc.group(1).strip().startswith('Use when'):
        errors.append(f'{path}: description must start with Use when')
    words = len(re.findall(r"\b[\w'-]+\b", text))
    if words > 500:
        errors.append(f'{path}: {words} words > 500')
    print(f'OK {path.relative_to(root.parent.parent)} words={words}')
if errors:
    print('\n'.join(errors), file=sys.stderr)
    sys.exit(1)
print('All skill files passed static validation.')
