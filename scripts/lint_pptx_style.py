#!/usr/bin/env python3
"""Read-only OOXML checks. No rendering, network access or source modification."""
from __future__ import annotations
import argparse
import json
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile, BadZipFile

NS = {
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'rel': 'http://schemas.openxmlformats.org/package/2006/relationships',
}
def q(prefix: str, name: str) -> str:
    return '{' + NS[prefix] + '}' + name

def text(node: ET.Element) -> str:
    return ''.join(t.text or '' for t in node.iter(q('a', 't')))

def rels(z: ZipFile, part: str) -> dict:
    name = posixpath.join(posixpath.dirname(part), '_rels', posixpath.basename(part) + '.rels')
    if name not in z.namelist():
        return {}
    return {r.get('Id'): dict(r.attrib) for r in ET.fromstring(z.read(name))}

def audit(path: Path, profile: dict | None = None, expected: dict | None = None) -> dict:
    """expected keys: '<logical slide>:<shape name>:<1-based paragraph>'."""
    profile, expected = profile or {}, expected or {}
    issues, seen = [], set()
    def issue(code, slide=0, shape='', paragraph=0, level='error'):
        issues.append(dict(code=code, level=level, slide=slide, shape=shape, paragraph=paragraph))
    with ZipFile(path) as z:
        if z.testzip() is not None:
            raise ValueError('ZIP CRC check failed')
        pr = ET.fromstring(z.read('ppt/presentation.xml'))
        mapping = rels(z, 'ppt/presentation.xml')
        ids = pr.find('p:sldIdLst', NS)
        if ids is None:
            raise ValueError('Missing slide list')
        parts = []
        for sid in ids:
            relation = mapping[sid.get(q('r', 'id'))]
            target = relation['Target']
            parts.append(target.lstrip('/') if target.startswith('/') else posixpath.normpath('ppt/' + target))
        for number, part in enumerate(parts, 1):
            root, targets = ET.fromstring(z.read(part)), rels(z, part)
            for shape in root.findall('.//p:sp', NS):
                meta = shape.find('p:nvSpPr/p:cNvPr', NS)
                name = meta.get('name', '') if meta is not None else ''
                value = text(shape)
                footer = name in profile.get('reference_shape_names', ['ReferenceFooter'])
                nav = value in profile.get('navigation_labels', [])
                if name == profile.get('page_number_shape_name') and value != f'{number:02d}':
                    issue('page_number_mismatch', number, name)
                if nav or footer:
                    key = 'navigation_pt' if nav else 'reference_pt'
                    required = profile.get(key)
                    for rp in shape.findall('.//a:rPr', NS):
                        if required is not None and rp.get('sz') is not None:
                            if abs(float(rp.get('sz')) / 100 - required) > .01:
                                issue('font_size_mismatch', number, name)
                        elif required is not None:
                            issue('inherited_font_size_unchecked', number, name, level='warning')
                if not footer:
                    continue
                # A whole-shape action defeats a correctly styled journal-only text link.
                if meta is not None and any(e.tag in (q('a', 'hlinkClick'), q('a', 'hlinkMouseOver')) for e in meta.iter()):
                    issue('shape_level_reference_link', number, name)
                for pn, paragraph in enumerate(shape.findall('.//a:p', NS), 1):
                    full = text(paragraph)
                    separator = full.find('|')
                    cursor, links = 0, []
                    for run in list(paragraph):
                        if run.tag not in (q('a', 'r'), q('a', 'fld')):
                            continue
                        label = text(run)
                        rp = run.find('a:rPr', NS)
                        clicks = [] if rp is None else rp.findall('a:hlinkClick', NS)
                        hover = [] if rp is None else rp.findall('a:hlinkMouseOver', NS)
                        if hover:
                            issue('reference_mouseover_action', number, name, pn)
                        for click in clicks:
                            rid = click.get(q('r', 'id'))
                            relation = targets.get(rid, {})
                            url = relation.get('Target', '')
                            if not url:
                                issue('missing_link_target', number, name, pn)
                            if separator < 0 or cursor <= separator:
                                issue('title_or_prefix_linked', number, name, pn)
                            if re.search(r'\b(?:19|20)\d{2}\b|Reviewed Preprint|\bv\d+\b', label, re.I):
                                issue('date_or_status_linked', number, name, pn)
                            if label.strip() != label or re.search(r'[.,;，。；]$', label):
                                issue('extra_space_or_punctuation_linked', number, name, pn)
                            if rp is not None and rp.get('u') not in (None, 'none'):
                                issue('underlined_reference_link', number, name, pn)
                            if rp is not None and rp.get('b') not in ('1', 'true'):
                                issue('reference_bold_not_explicit', number, name, pn, 'warning')
                            if links and links[-1]['end'] == cursor and links[-1]['url'] == url:
                                links[-1]['text'] += label
                                links[-1]['end'] += len(label)
                            else:
                                links.append(dict(text=label, url=url, end=cursor + len(label)))
                        cursor += len(label)
                    identifier = f'{number}:{name}:{pn}'
                    if identifier in expected:
                        seen.add(identifier)
                        actual = [dict(text=l['text'], url=l['url']) for l in links]
                        if actual != expected[identifier]:
                            issue('citation_map_mismatch', number, name, pn)
        for key in expected.keys() - seen:
            issue('citation_map_location_missing', shape=key)
        if profile.get('forbid_embedded_fonts') and any(n.startswith('ppt/fonts/') for n in z.namelist()):
            issue('embedded_font_present')
    return dict(slide_count=len(parts), errors=sum(i['level'] == 'error' for i in issues),
                warnings=sum(i['level'] == 'warning' for i in issues), issues=issues,
                scope='OOXML only; rendering, factual accuracy and inherited styles require separate review')

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pptx', type=Path)
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--citation-map', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        load = lambda p: json.loads(p.read_text(encoding='utf-8')) if p else {}
        report = audit(args.pptx, load(args.profile), load(args.citation_map))
        result = json.dumps(report, ensure_ascii=False, indent=2)
        if args.output:
            if args.output.resolve() == args.pptx.resolve():
                raise ValueError('Output must not overwrite the input PPTX')
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(result + '\n', encoding='utf-8')
        else:
            print(result)
        return 1 if report['errors'] else 0
    except (OSError, ValueError, KeyError, TypeError, BadZipFile, ET.ParseError) as exc:
        print(f'Cannot inspect PPTX: {exc}', file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
