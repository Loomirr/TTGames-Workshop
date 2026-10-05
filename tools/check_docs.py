"""Check public Markdown encoding and relative file links without network access.

This checks documentation structure, not whether support claims are true.
Run manually after changing docs or packaging tools.
"""
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SKIP = {'bin', 'obj', 'dist', 'Release', '__pycache__'}


def documents():
    yield from ROOT.glob('*.md')
    yield ROOT / 'builds/README.md'
    # Locally unzipped GUI packages under builds/python are ignored scratch
    # copies, not public source documentation.
    for folder in ('docs', 'formats', 'games', 'tools'):
        for path in (ROOT / folder).rglob('*.md'):
            if not set(path.relative_to(ROOT).parts) & SKIP:
                yield path


def main():
    issues = []
    paths = list(documents())
    links = 0
    # Common UTF-8 bytes decoded as Windows-1252, sometimes twice.
    broken = re.compile(r'\ufffd|\u00c3[\u0080-\u00bf]|\u00c2[\u0080-\u00bf]|'
                        r'\u00e2[\u0080-\u00bf\u20ac\u201a\u201e\u2020\u2021\u2018\u2019\u201c\u201d\u2022\u2013\u2014\u2122]|'
                        r'\u00f0\u0178')
    for path in paths:
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeError as error:
            issues.append(f'{path.relative_to(ROOT)}: invalid UTF-8: {error}')
            continue
        for line, text in enumerate(content.splitlines(), 1):
            if broken.search(text):
                issues.append(f'{path.relative_to(ROOT)}:{line}: broken text encoding')
        content = re.sub(r'^```[^\n]*\n.*?^```[^\n]*$', '', content, flags=re.M | re.S)
        for match in re.finditer(r'!?\[[^\]\n]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+"[^"\n]*")?\s*\)', content):
            target = match.group(1).strip('<>')
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            links += 1
            resolved = (ROOT / unquote(parsed.path.lstrip('/')) if parsed.path.startswith('/')
                        else path.parent / unquote(parsed.path))
            if not resolved.exists():
                issues.append(f'{path.relative_to(ROOT)}: missing link target {target}')
    if issues:
        raise SystemExit('\n'.join(issues))
    print(f'Documentation encoding and relative-file links passed: {len(paths)} Markdown files, {links} links. '
          'Support claims and external URLs require separate review.')


if __name__ == '__main__':
    main()
