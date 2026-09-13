#!/usr/bin/env python3
"""Create, lint and conservatively format the write-adr Markdown profile."""
import argparse
import html
import os
import tempfile
from datetime import date
from pathlib import Path
import re
import sys

STATUSES = ('Proposed', 'Accepted', 'Rejected', 'Deprecated', 'Superseded')
SECTIONS = ('Context', 'Decision', 'Consequences')
KEYS = ('status', 'proposed-on', 'superseded-by')
FILENAME = re.compile(r'ADR-([0-9]{3,})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md\Z')
TITLE = re.compile(r'ADR-([0-9]{3,}): (\S.*)\Z')
HEADING = re.compile(r'^(#{1,6})[ \t]+(.+?)\s*$')
FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')
PLACEHOLDER = re.compile(r'\{\{(?:id|title|proposed_on|context|problem|options|decision|consequences)\}\}')


class Invalid(ValueError):
    pass


def valid_number(value):
    return int(value) > 0 and value == '%03d' % int(value)


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


def frontmatter(lines):
    if not lines or lines[0] != '---':
        raise Invalid('E_FRONTMATTER: expected YAML front matter at the start; migrate legacy Status sections explicitly')
    try:
        end = lines.index('---', 1)
    except ValueError:
        raise Invalid('E_FRONTMATTER: missing closing --- delimiter')
    fields = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        match = re.fullmatch(r'([a-z][a-z-]*):[ \t]+(.+?)[ \t]*', line)
        if not match or match[1] not in KEYS or match[1] in fields:
            raise Invalid('E_METADATA: expected unique supported keys at column one')
        key, value = match[1], match[2]
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise Invalid('E_METADATA: unmatched scalar quotes')
            value = value[1:-1]
        # Deliberately limited YAML scalar subset: no comments, escapes, nested
        # collections, aliases, tags, or multiline values. Semantic checks follow.
        if not re.fullmatch(r'[A-Za-z0-9./_-]+(?: +[A-Za-z0-9./_-]+)*', value):
            raise Invalid('E_METADATA: expected a nonempty plain or simply quoted scalar')
        fields[key] = value
    if not all(key in fields for key in KEYS[:2]):
        raise Invalid('E_METADATA: status and proposed-on are required')
    return fields, lines[end + 1:]


def parse(text):
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    fields, lines = frontmatter(lines)
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
    if len(major) != 4 or major[0][1] != 1 or [(h[1], h[2]) for h in major[1:]] != [(2, s) for s in SECTIONS]:
        raise Invalid('E_STRUCTURE: expected one H1 then H2 Context, Decision, Consequences in order')
    if any('<!--' in lines[h[0]] for h in major):
        raise Invalid('E_STRUCTURE: put comments in section bodies, not on structural headings')
    first = major[0][0]
    if any(line.strip() for line in lines[:first]) or any(line.strip() for line in lines[first + 1:major[1][0]]):
        raise Invalid('E_STRUCTURE: only whitespace is allowed before title or between title and Context')
    title = major[0][2]
    if not TITLE.fullmatch(title):
        raise Invalid('E_TITLE: expected # ADR-NNN: title')
    sections = {}
    for offset, (start, _, label) in enumerate(major[1:], 1):
        end = major[offset + 1][0] if offset + 1 < len(major) else len(lines)
        sections[label] = strip_edges(lines[start + 1:end])
    for label in SECTIONS:
        body = re.sub(r'<!--.*?-->', '', sections[label], flags=re.S)
        body = re.sub(r'^#{3,6}[ \t]+.*$', '', body, flags=re.M)
        if not body.strip():
            raise Invalid('E_EMPTY: ' + label + ' needs content')
    if PLACEHOLDER.search(text):
        raise Invalid('E_PLACEHOLDER: fill the template placeholders')
    return title, fields, sections


def canonical(parsed):
    title, fields, sections = parsed
    metadata = '\n'.join(key + ': ' + ('"' + fields[key] + '"' if key == 'proposed-on' else fields[key]) for key in KEYS if key in fields)
    parts = ['---\n' + metadata + '\n---', '# ' + title]
    for label in SECTIONS:
        parts.extend(('## ' + label, sections[label]))
    return '\n\n'.join(parts) + '\n'


def validate(path, parsed, today, maximum):
    title, fields, _ = parsed
    errors = []
    filename = FILENAME.fullmatch(path.name)
    if not filename or not valid_number(filename[1]) or filename[1] != TITLE.fullmatch(title)[1]:
        errors.append('E_FILENAME: expected ADR-NNN-slug.md with a canonical positive, title-matching number')
    status = fields['status']
    if status not in STATUSES:
        errors.append('E_STATUS: expected ' + ', '.join(STATUSES))
    try:
        proposed = iso_date(fields['proposed-on'])
        age = (today - proposed).days
        if age < 0:
            errors.append('E_DATE: proposed-on cannot be in the future')
        elif status == 'Proposed' and age >= maximum:
            errors.append('E_STALE: Proposed for %d days (limit %d); review decision, do not reset date' % (age, maximum))
    except ValueError:
        errors.append('E_DATE: proposed-on must be a real YYYY-MM-DD date')
    replacement = fields.get('superseded-by')
    if status == 'Superseded':
        if not replacement or not FILENAME.fullmatch(replacement) or not valid_number(FILENAME.fullmatch(replacement)[1]):
            errors.append('E_REPLACEMENT: Superseded requires superseded-by: ADR-NNN-slug.md')
        else:
            target = path.parent / replacement
            if target.resolve() == path.resolve() or not target.is_file() or target.is_symlink():
                errors.append('E_REPLACEMENT: replacement must be another existing sibling ADR file')
    elif replacement is not None:
        errors.append('E_REPLACEMENT: superseded-by is only allowed for Superseded')
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


INDEX_START = '<!-- adr-index:start -->'
INDEX_END = '<!-- adr-index:end -->'


def index_header(path, today):
    if path.is_symlink():
        raise Invalid('E_INDEX: symbolic-link ADR files are not supported: ' + str(path))
    lines, delimiters = [], 0
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            line = line.rstrip('\r\n')
            lines.append(line)
            if line == '---':
                delimiters += 1
            elif delimiters >= 2 and line.strip():
                break
    fields, body = frontmatter(lines)
    heading = next((line for line in body if line.strip()), '')
    if not heading.startswith('# ') or '<!--' in heading:
        raise Invalid('E_INDEX: expected an ADR title after front matter: ' + str(path))
    title = re.sub(r'[ \t]+#+[ \t]*$', '', heading[2:]).strip()
    if not TITLE.fullmatch(title):
        raise Invalid('E_INDEX: expected # ADR-NNN: title: ' + str(path))
    parsed = title, fields, {}
    errors = validate(path, parsed, today, sys.maxsize)
    if errors:
        raise Invalid('E_INDEX: ' + str(path) + ': ' + '; '.join(errors))
    return parsed


def table_cell(value):
    value = html.escape(value, quote=False).replace('|', '&#124;')
    return re.sub(r'([\\`*_{}\[\]])', r'\\\1', value)


def index_text(directory, extra=None, today=None):
    """Build the direct-child index, preserving README outside one managed block."""
    directory = Path(directory)
    today = today or date.today()
    if not directory.is_dir():
        raise Invalid('E_INDEX: directory does not exist: ' + str(directory))
    rows, seen = [], set()
    for path in sorted(directory.glob('*.md')):
        if path.name.lower() == 'readme.md' or path.name.startswith('.'):
            continue
        title, fields, _ = index_header(path, today)
        rows.append((path, title, fields))
    if extra:
        rows.append(extra)
    rows.sort(key=lambda row: int(TITLE.fullmatch(row[1])[1]))
    rendered = [INDEX_START, '| ID | Title | Status | Proposed on | Superseded by |',
                '| --- | --- | --- | --- | --- |']
    for path, title, fields in rows:
        match = TITLE.fullmatch(title)
        number = int(match[1])
        if number in seen:
            raise Invalid('E_INDEX: duplicate ADR number in ' + str(directory))
        seen.add(number)
        replacement = fields.get('superseded-by')
        target = ('[ADR-%s](%s)' % (FILENAME.fullmatch(replacement)[1], replacement)) if replacement else '—'
        rendered.append('| [ADR-%s](%s) | %s | %s | %s | %s |' % (
            match[1], path.name, table_cell(match[2]), fields['status'], fields['proposed-on'], target))
    rendered.append(INDEX_END)
    block = '\n'.join(rendered)
    readme = directory / 'README.md'
    if readme.is_symlink():
        raise Invalid('E_INDEX: symbolic-link README is not supported: ' + str(readme))
    # Avoid creating a second README on case-sensitive filesystems.
    if any(p.name.lower() == 'readme.md' and p.name != 'README.md' for p in directory.iterdir()):
        raise Invalid('E_INDEX: rename the existing readme to README.md: ' + str(directory))
    current = readme.read_bytes().decode('utf-8') if readme.exists() else '# Architecture Decision Records\n'
    starts = list(re.finditer(r'^' + re.escape(INDEX_START) + r'\r?$', current, re.M))
    ends = list(re.finditer(r'^' + re.escape(INDEX_END) + r'\r?$', current, re.M))
    if not starts and not ends and 'adr-index:' not in current:
        result = current + ('' if current.endswith('\n') else '\n') + '\n' + block + '\n'
    elif len(starts) == len(ends) == 1 and starts[0].start() < ends[0].start() and current.count('adr-index:') == 2:
        result = current[:starts[0].start()] + block + current[ends[0].end():]
    else:
        raise Invalid('E_INDEX: malformed or duplicate managed-block markers: ' + str(readme))
    return readme, result.encode('utf-8'), len(rows)


def write_index(readme, content):
    if readme.exists() and readme.read_bytes() == content:
        return False
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=readme.parent, prefix='.adr-index-', delete=False) as stream:
            temporary = Path(stream.name)
            os.fchmod(stream.fileno(), readme.stat().st_mode & 0o777 if readme.exists() else 0o644)
            stream.write(content)
        os.replace(temporary, readme)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return True


def index_command(args):
    readme, content, count = index_text(args.directory, today=args.today)
    if args.check:
        if not readme.exists() or readme.read_bytes() != content:
            print('E_INDEX: out-of-date or missing index: ' + str(readme))
            return 1
    else:
        write_index(readme, content)
    print('%d ADR(s) indexed: %s' % (count, readme))
    return 0


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
    if args.command == 'format':
        for directory in sorted({p.parent for p in files}, key=str):
            try:
                readme, content, _ = index_text(directory, today=args.today)
                if args.check:
                    if not readme.exists() or readme.read_bytes() != content:
                        raise Invalid('E_INDEX: out-of-date or missing index: ' + str(readme))
                else:
                    write_index(readme, content)
            except (OSError, UnicodeError, Invalid) as exc:
                count += 1
                if shown < args.max_errors:
                    print(str(exc))
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
    numbers = [int(m[1]) for p in directory.iterdir() if (m := re.match(r'^(?:ADR-)?([0-9]+)[-.]', p.name))]
    number = 'ADR-%03d' % (max(numbers, default=0) + 1)
    path = directory / (number + '-' + args.slug + '.md')
    template = Path(__file__).resolve().parent.parent / 'assets' / 'adr.md'
    content = template.read_text(encoding='utf-8')
    for key, value in (('id', number), ('title', title), ('proposed_on', args.today.isoformat())):
        content = content.replace('{{' + key + '}}', value)
    fields = {'status': 'Proposed', 'proposed-on': args.today.isoformat()}
    readme, index, _ = index_text(directory, extra=(path, number + ': ' + title, fields), today=args.today)
    with path.open('x', encoding='utf-8', newline='\n') as output:
        output.write(content)
    try:
        write_index(readme, index)
    except OSError as exc:
        raise Invalid('ADR created at %s; index update failed: %s' % (path, exc))
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
    index = commands.add_parser('index', help='update the direct-child ADR table in README.md')
    index.add_argument('directory', nargs='?', default='docs/adr')
    index.add_argument('--today', type=iso_date, default=date.today())
    index.add_argument('--check', action='store_true', help='fail if the table is missing or outdated, without writing')
    new = commands.add_parser('new')
    new.add_argument('--directory', default='docs/adr')
    new.add_argument('--slug', required=True)
    new.add_argument('--title', required=True)
    new.add_argument('--today', type=iso_date, default=date.today())
    args = parser.parse_args(argv)
    try:
        if args.command == 'new':
            return create(args)
        if args.command == 'index':
            return index_command(args)
        return check(args)
    except (OSError, UnicodeError, Invalid) as exc:
        print('E_INPUT: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
