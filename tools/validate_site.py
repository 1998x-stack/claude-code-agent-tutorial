#!/usr/bin/env python3
"""Offline checks for canonical HTML chapters, local links and standalone SVG."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse, unquote
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'
errors = []
class Doc(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.h1, self.ids = [], 0, set()
    def handle_starttag(self, tag, pairs):
        a = dict(pairs)
        if tag == 'h1': self.h1 += 1
        if a.get('id'):
            if a['id'] in self.ids: errors.append('duplicate id ' + a['id'])
            self.ids.add(a['id'])
        for field in ('href', 'src'):
            if a.get(field): self.links.append(a[field])
        if tag == 'img' and not a.get('alt'):
            errors.append('image missing alt')
pages = list(SITE.rglob('*.html'))
for file in pages:
    obj = Doc()
    obj.feed(file.read_text(encoding='utf8'))
    if file == SITE / 'index.html' or (file.parent == SITE / 'chapters' and re.fullmatch(r'\d{2}\.html', file.name)):
        if obj.h1 != 1: errors.append(str(file) + ' H1 count ' + str(obj.h1))
    for link in obj.links:
        ref = urlparse(link)
        if ref.scheme or ref.netloc or link.startswith(('#', 'data:', 'mailto:', 'javascript:')): continue
        if not ref.path or ref.path.startswith('/'): continue
        dest = (file.parent / unquote(ref.path)).resolve()
        if dest != SITE and SITE not in dest.parents:
            errors.append(f'{file}: link escapes site {link}')
        elif not dest.exists():
            errors.append(f'{file}: missing link {link}')
for n in range(1, 29):
    if not (SITE / 'chapters' / f'{n:02}.html').is_file(): errors.append(f'missing chapter {n:02}')
svgs = list(SITE.rglob('*.svg'))
for file in svgs:
    try:
        root = ET.parse(file).getroot()
        if not root.get('viewBox'): errors.append(f'{file}: no viewBox')
        if not root.find('{http://www.w3.org/2000/svg}title') is not None:
            errors.append(f'{file}: missing title')
        if root.find('{http://www.w3.org/2000/svg}desc') is None:
            errors.append(f'{file}: missing desc')
    except ET.ParseError as err:
        errors.append(f'{file}: XML error {err}')
if errors:
    print('\n'.join('ERROR ' + item for item in errors))
    sys.exit(1)
print(f'PASS: {len(pages)} HTML pages, {len(svgs)} SVGs, 28 canonical chapters')
