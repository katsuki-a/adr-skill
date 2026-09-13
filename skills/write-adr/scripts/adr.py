#!/usr/bin/env python3
"""Create, lint and conservatively format the write-adr Markdown profile."""
import argparse
from datetime import date
from pathlib import Path
import re
import sys

STATUSES = ('Proposed', 'Accepted', 'Rejected', 'Deprecated', 'Superseded')
SECTIONS = ('Status', 'Context', 'Decision', 'Consequences')
KEYS = ('Status', 'Proposed-on', 'Superseded-by')
FILENAME = re.compile(r'([0-9]{4,})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md\Z')
TITLE = re.compile(r'([0-9]{4,})\. (\S.*)\Z')
HEADING = re.compile(r'^(#{1,6})[ \t]+(.+?)\s*$')
FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')
PLACEHOLDER = re.compile(r'\{\{(?:id|title|proposed_on|context|decision|consequences)\}\}')


class Invalid(ValueError):
    pass


def iso_date(value):
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        raise ValueError('expected YYYY-MM-DD')
    return date.fromisoformat(value)


def strip_edges(lines):
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return '\n'.join(lines[start:end])


def visible_lines(lines):
    """Hide fenced code and comments from structural heading recognition."""
    marker, length, comment = '', 0, False
    for line in lines:
        if marker:
            fence = FENCE.match(line)
            if fence and fence[1][0] == marker and len(fence[1]) >= length and not fence[2].strip():
                marker = ''
            yield ''
            continue
        if not comment:
            fence = FENCE.match(line)
            if fence:
                if fence[1][0] == '`' and '`' in fence[2]:
                    raise Invalid('E_MARKDOWN: backtick in fence info string')
                marker, length = fence[1][0], len(fence[1])
                yield ''
                continue
        visible = ''
        while line:
            if comment:
                _, sep, line = line.partition('-->')
                if not sep:
                    break
                comment = False
            else:
                prefix, sep, line = line.partition('<!--')
                visible += prefix
                if not sep:
                    break
                comment = True
        yield visible
    if marker or comment:
        raise Invalid('E_MARKDOWN: unclosed code fence or HTML comment')


def parse(text):
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    headings = []
    visible = list(visible_lines(lines))
    for i, line in enumerate(visible):
        if re.match(r'^ {0,3}</?[A-Za-z][A-Za-z0-9-]*(?:[ \t/>])', line):
            raise Invalid('E_MARKDOWN: raw HTML blocks are outside this profile; use Markdown or comments')
        if i and visible[i - 1].strip() and re.fullmatch(r' {0,3}(?:=+|-+)[ \t]*', line):
            raise Invalid('E_MARKDOWN: use ATX headings, not setext headings')
        match = HEADING.match(line)
        if match:
            label = re.sub(r'[ \t]+#+[ \t]*$', '', match[2]).strip()
            headings.append((i, len(match[1]), label))
    major = [h for h in headings if h[1] <= 2]
    if len(major) != 5 or major[0][1] != 1 or [(h[1], h[2]) for h in major[1:]] != [(2, s) for s in SECTIONS]:
        raise Invalid('E_STRUCTURE: expected one H1 then H2 Status, Context, Decision, Consequences in order')
    if any('<!--' in lines[h[0]] for h in major):
        raise Invalid('E_STRUCTURE: put comments in section bodies, not on structural headings')
    first = major[0][0]
    if any(line.strip() for line in lines[:first]) or any(line.strip() for line in lines[first + 1:major[1][0]]):
        raise Invalid('E_STRUCTURE: only whitespace is allowed before title or between title and Status')
    title = major[0][2]
    if not TITLE.fullmatch(title):
        raise Invalid('E_TITLE: expected # NNNN. title')
    sections = {}
    for offset, (start, _, label) in enumerate(major[1:], 1):
        end = major[offset + 1][0] if offset + 1 < len(major) else len(lines)
        sections[label] = strip_edges(lines[start + 1:end])
    fields = {}
    for line in sections['Status'].splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(':')
        key, value = key.strip(), value.strip()
        if not separator or key not in KEYS or key in fields or not value:
            raise Invalid('E_METADATA: unknown, duplicate or empty Status metadata')
        fields[key] = value
    if not all(key in fields for key in KEYS[:2]):
        raise Invalid('E_METADATA: Status and Proposed-on are required')
    for label in SECTIONS[1:]:
        body = re.sub(r'<!--.*?-->', '', sections[label], flags=re.S)
        body = re.sub(r'^#{3,6}[ \t]+.*$', '', body, flags=re.M)
        if not body.strip():
            raise Invalid('E_EMPTY: ' + label + ' needs content')
    if PLACEHOLDER.search(text):
        raise Invalid('E_PLACEHOLDER: fill the template placeholders')
    return title, fields, sections


def canonical(parsed):
    title, fields, sections = parsed
    parts = ['# ' + title, '## Status', '\n'.join(key + ': ' + fields[key] for key in KEYS if key in fields)]
    for label in SECTIONS[1:]:
        parts.extend(('## ' + label, sections[label]))
    return '\n\n'.join(parts) + '\n'


def validate(path, parsed, today, maximum):
    title, fields, _ = parsed
    errors = []
    filename = FILENAME.fullmatch(path.name)
    if not filename or filename[1] != TITLE.fullmatch(title)[1]:
        errors.append('E_FILENAME: expected NNNN-slug.md with title-matching number')
    status = fields['Status']
    if status not in STATUSES:
        errors.append('E_STATUS: expected ' + ', '.join(STATUSES))
    try:
        proposed = iso_date(fields['Proposed-on'])
        age = (today - proposed).days
        if age < 0:
            errors.append('E_DATE: Proposed-on cannot be in the future')
        elif status == 'Proposed' and age >= maximum:
            errors.append('E_STALE: Proposed for %d days (limit %d); review decision, do not reset date' % (age, maximum))
    except ValueError:
        errors.append('E_DATE: Proposed-on must be a real YYYY-MM-DD date')
    replacement = fields.get('Superseded-by')
    if status == 'Superseded':
        if not replacement or not FILENAME.fullmatch(replacement):
            errors.append('E_REPLACEMENT: Superseded requires Superseded-by: NNNN-slug.md')
        else:
            target = path.parent / replacement
            if target.resolve() == path.resolve() or not target.is_file() or target.is_symlink():
                errors.append('E_REPLACEMENT: replacement must be another existing sibling ADR file')
    elif replacement is not None:
        errors.append('E_REPLACEMENT: Superseded-by is only allowed for Superseded')
    return errors


def collect(inputs):
    files = set()
    for name in inputs:
        path = Path(name)
        if path.is_dir():
            files.update(p for p in path.rglob('*.md') if p.name.lower() != 'readme.md' and not any(x.startswith('.') for x in p.relative_to(path).parts))
        else:
            files.add(path)
    return sorted(files, key=str)


def check(args):
    files = collect(args.paths)
    if not files:
        print('E_INPUT: no ADR Markdown files found', file=sys.stderr)
        return 2
    count = shown = changed = 0
    ids = {}
    for path in files:
        errors = []
        try:
            if path.is_symlink():
                raise Invalid('E_INPUT: symbolic-link ADR files are not supported')
            raw = path.read_bytes()
            text = raw.decode('utf-8')
            parsed = parse(text)
            errors.extend(validate(path, parsed, args.today, args.max_proposed_days))
            identity = (path.parent.resolve(), TITLE.fullmatch(parsed[0])[1])
            if identity in ids:
                errors.append('E_DUPLICATE: number also used by ' + str(ids[identity]))
            ids[identity] = path
            formatted = canonical(parsed).encode('utf-8')
            if raw != formatted:
                if args.command == 'format' and not args.check and not errors:
                    path.write_bytes(formatted)
                    changed += 1
                else:
                    errors.append('E_FORMAT: run format for canonical spacing and LF newlines')
        except (OSError, UnicodeError, Invalid) as exc:
            errors.append(str(exc) if isinstance(exc, Invalid) else 'E_INPUT: ' + str(exc))
        for error in errors:
            count += 1
            if shown < args.max_errors:
                print('%s: %s' % (path, error))
                shown += 1
    if count > shown:
        print('... %d more errors; use --max-errors to show more' % (count - shown))
    print('%d file(s), %d error(s), %d formatted' % (len(files), count, changed))
    return 1 if count else 0


def create(args):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', args.slug):
        raise Invalid('slug must use lowercase ASCII letters, digits and single hyphens')
    title = args.title.strip()
    if not title or any(ord(c) < 32 for c in title) or '{{' in title or '<!--' in title or re.search(r'\s#+$', title):
        raise Invalid('title must be one nonempty plain-text line without a trailing heading marker')
    if args.today > date.today():
        raise Invalid('new ADR date cannot be in the future')
    directory = Path(args.directory)
    directory.mkdir(parents=True, exist_ok=True)
    numbers = [int(m[1]) for p in directory.iterdir() if (m := re.match(r'^([0-9]+)[-.]', p.name))]
    number = '%04d' % (max(numbers, default=0) + 1)
    path = directory / (number + '-' + args.slug + '.md')
    template = Path(__file__).resolve().parent.parent / 'assets' / 'adr.md'
    content = template.read_text(encoding='utf-8')
    for key, value in (('id', number), ('title', title), ('proposed_on', args.today.isoformat())):
        content = content.replace('{{' + key + '}}', value)
    with path.open('x', encoding='utf-8', newline='\n') as output:
        output.write(content)
    print(str(path) + '\n' + content, end='')
    return 0


def positive(value):
    try:
        result = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('expected a positive integer')
    if result < 1:
        raise argparse.ArgumentTypeError('expected a positive integer')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('lint', 'format'):
        sub = commands.add_parser(command)
        sub.add_argument('paths', nargs='+', help='ADR files or directories (recursive; skips README.md)')
        sub.add_argument('--today', type=iso_date, default=date.today(), help='evaluation date YYYY-MM-DD (default: local today)')
        sub.add_argument('--max-proposed-days', type=positive, default=30, help='error when Proposed age >= N (default: 30)')
        sub.add_argument('--max-errors', type=positive, default=20)
        if command == 'format':
            sub.add_argument('--check', action='store_true', help='check without writing')
    new = commands.add_parser('new')
    new.add_argument('--directory', default='docs/adr')
    new.add_argument('--slug', required=True)
    new.add_argument('--title', required=True)
    new.add_argument('--today', type=iso_date, default=date.today())
    args = parser.parse_args(argv)
    try:
        return create(args) if args.command == 'new' else check(args)
    except (OSError, UnicodeError, Invalid) as exc:
        print('E_INPUT: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
