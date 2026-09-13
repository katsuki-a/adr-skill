import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_adr import adr, document, TODAY


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.path = self.directory / 'ADR-001-policy.md'
        self.path.write_text(document(), encoding='utf-8')
        self.readme = self.directory / 'README.md'

    def tearDown(self):
        self.temp.cleanup()

    def run_tool(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = adr.main(list(args))
        return code, output.getvalue()

    def index(self, *options):
        return self.run_tool('index', str(self.directory), '--today', TODAY, *options)

    def test_new_updates_index_even_with_draft_placeholders(self):
        code, output = self.run_tool('new', '--directory', str(self.directory), '--slug', 'draft', '--title', 'New draft', '--today', TODAY)
        self.assertEqual(code, 0, output)
        self.assertIn('# ADR-002: New draft', output)
        self.assertIn('[ADR-002](ADR-002-draft.md) | New draft | Proposed', self.readme.read_text())
        self.assertEqual(self.index('--check')[0], 0)
        code, output = self.run_tool('lint', str(self.directory / 'ADR-002-draft.md'), '--today', TODAY)
        self.assertEqual(code, 1)
        self.assertIn('E_PLACEHOLDER', output)

    def test_format_refreshes_status_and_check_is_read_only(self):
        self.assertEqual(self.index()[0], 0)
        before = self.readme.read_bytes()
        self.path.write_text(document('Accepted'), encoding='utf-8')
        self.assertEqual(self.index('--check')[0], 1)
        self.assertEqual(self.run_tool('format', str(self.path), '--check', '--today', TODAY)[0], 1)
        self.assertEqual(self.readme.read_bytes(), before)
        self.assertEqual(self.run_tool('format', str(self.path), '--today', TODAY)[0], 0)
        self.assertIn('| Accepted |', self.readme.read_text())
        self.assertEqual(self.index('--check')[0], 0)

    def test_index_tracks_title_rename_and_deletion(self):
        self.index()
        renamed = self.directory / 'ADR-001-renamed.md'
        self.path.rename(renamed)
        renamed.write_text(document().replace('採用方針', 'Updated title'), encoding='utf-8')
        self.assertEqual(self.index('--check')[0], 1)
        self.assertEqual(self.index()[0], 0)
        self.assertIn('[ADR-001](ADR-001-renamed.md) | Updated title', self.readme.read_text())
        self.assertNotIn('policy.md', self.readme.read_text())
        renamed.unlink()
        self.assertEqual(self.index()[0], 0)
        self.assertNotIn('| [ADR-', self.readme.read_text())
        self.assertEqual(self.index('--check')[0], 0)

    def test_preserves_unmanaged_text_and_is_idempotent(self):
        original = b'# My notes\r\n\r\nKeep this hard break  \r\n'
        self.readme.write_bytes(original)
        self.assertEqual(self.index()[0], 0)
        self.assertTrue(self.readme.read_bytes().startswith(original))
        suffix = b'\n## Further notes\nKeep this too.\n'
        self.readme.write_bytes(self.readme.read_bytes() + suffix)
        self.path.write_text(document('Accepted'), encoding='utf-8')
        self.assertEqual(self.index()[0], 0)
        raw = self.readme.read_bytes()
        self.assertTrue(raw.startswith(original))
        self.assertTrue(raw.endswith(suffix))
        stamp = self.readme.stat().st_mtime_ns
        self.assertEqual(self.index()[0], 0)
        self.assertEqual(self.readme.stat().st_mtime_ns, stamp)
        self.assertEqual(raw.count(adr.INDEX_START.encode()), 1)

    def test_malformed_markers_refuse_update_and_new(self):
        for text in [adr.INDEX_START, adr.INDEX_END, adr.INDEX_END + '\n' + adr.INDEX_START,
                     adr.INDEX_START + '\n' + adr.INDEX_START + '\n' + adr.INDEX_END,
                     '<!-- adr-index:start']:
            with self.subTest(text=text):
                self.readme.write_text(text)
                before = self.readme.read_bytes()
                self.assertEqual(self.index()[0], 2)
                self.assertEqual(before, self.readme.read_bytes())
                self.assertEqual(self.run_tool('new', '--directory', str(self.directory), '--slug', 'draft', '--title', 'Draft')[0], 2)
                self.assertFalse((self.directory / 'ADR-002-draft.md').exists())

    def test_table_escapes_title_markup(self):
        title = 'A | B <img src=x> [link](x) `code` & text'
        self.path.write_text(document().replace('採用方針', title), encoding='utf-8')
        self.assertEqual(self.index()[0], 0)
        row = next(line for line in self.readme.read_text().splitlines() if line.startswith('| [ADR-'))
        self.assertEqual(row.count('|'), 6)
        self.assertIn('&#124;', row)
        self.assertIn('&lt;img src=x&gt;', row)
        self.assertIn(r'\[link\]', row)
        self.assertIn(r'\`code\`', row)
        self.assertIn('&amp; text', row)

    def test_numbers_are_sorted_numerically_and_grow_past_999(self):
        for number in (2, 10, 999, 1000):
            (self.directory / ('ADR-%03d-policy.md' % number)).write_text(document(number='%03d' % number), encoding='utf-8')
        self.assertEqual(self.index()[0], 0)
        lines = [line for line in self.readme.read_text().splitlines() if line.startswith('| [ADR-')]
        self.assertEqual([line.split(']')[0] for line in lines], ['| [ADR-001', '| [ADR-002', '| [ADR-010', '| [ADR-999', '| [ADR-1000'])
        self.assertEqual(self.run_tool('new', '--directory', str(self.directory), '--slug', 'next', '--title', 'Next')[0], 0)
        self.assertTrue((self.directory / 'ADR-1001-next.md').exists())

    def test_invalid_padding_zero_and_duplicate_ids_fail(self):
        self.index()
        before = self.readme.read_bytes()
        for number in ('000', '0001', '1'):
            path = self.directory / ('ADR-' + number + '-bad.md')
            path.write_text(document(number=number), encoding='utf-8')
            self.assertEqual(self.index()[0], 2)
            self.assertEqual(self.readme.read_bytes(), before)
            self.assertEqual(self.run_tool('lint', str(path), '--today', TODAY)[0], 1)
            path.unlink()
        (self.directory / 'ADR-001-duplicate.md').write_text(document(), encoding='utf-8')
        self.assertIn('duplicate ADR number', self.index()[1])
        self.assertEqual(self.readme.read_bytes(), before)

    def test_symlink_readme_is_not_followed(self):
        outside = self.directory / 'notes.txt'
        outside.write_text('untouched')
        self.readme.symlink_to(outside)
        self.assertEqual(self.index()[0], 2)
        self.assertEqual(outside.read_text(), 'untouched')

    def test_malformed_header_does_not_remove_rows_silently(self):
        self.index()
        before = self.readme.read_bytes()
        self.path.write_text('bad header', encoding='utf-8')
        self.assertEqual(self.index()[0], 2)
        self.assertEqual(self.readme.read_bytes(), before)

    def test_indexes_are_per_directory(self):
        nested = self.directory / 'nested'
        nested.mkdir()
        (nested / 'ADR-001-local.md').write_text(document(), encoding='utf-8')
        self.assertEqual(self.run_tool('format', str(self.directory), '--today', TODAY)[0], 0)
        self.assertEqual(self.readme.read_text().count('| [ADR-'), 1)
        self.assertEqual((nested / 'README.md').read_text().count('| [ADR-'), 1)
        self.assertNotIn('local.md', self.readme.read_text())

    def test_replacement_is_linked_and_stale_proposals_remain_visible(self):
        (self.directory / 'ADR-002-next.md').write_text(document('Accepted', number='002'), encoding='utf-8')
        self.path.write_text(document('Superseded').replace('\n---\n', '\nsuperseded-by: ADR-002-next.md\n---\n'), encoding='utf-8')
        self.assertEqual(self.index()[0], 0)
        row = next(line for line in self.readme.read_text().splitlines() if line.startswith('| [ADR-001'))
        self.assertIn('[ADR-002](ADR-002-next.md)', row)
        self.path.write_text(document(proposed='2020-01-01'), encoding='utf-8')
        self.assertEqual(self.index()[0], 0)
        self.assertIn('| Proposed | 2020-01-01 |', self.readme.read_text())

    def test_failed_atomic_replace_preserves_existing_readme(self):
        self.index()
        before = self.readme.read_bytes()
        self.path.write_text(document('Accepted'), encoding='utf-8')
        with patch.object(adr.os, 'replace', side_effect=OSError('simulated replacement failure')):
            self.assertEqual(self.index()[0], 2)
        self.assertEqual(self.readme.read_bytes(), before)
        self.assertEqual(list(self.directory.glob('.adr-index-*')), [])

    def test_index_checks_headers_without_requiring_complete_body(self):
        self.path.write_text(document().split('## Context', 1)[0] + 'Draft body', encoding='utf-8')
        self.assertEqual(self.index('--check')[0], 1)
        self.assertFalse(self.readme.exists())
        self.assertEqual(self.index()[0], 0)
        self.assertEqual(self.run_tool('lint', str(self.path), '--today', TODAY)[0], 1)
        self.assertIn('| [ADR-001]', self.readme.read_text())

    def test_metadata_validation_uses_requested_date(self):
        self.path.write_text(document(proposed='2099-01-01'), encoding='utf-8')
        code, output = self.run_tool('format', str(self.path), '--today', '2099-01-01')
        self.assertEqual(code, 0, output)
        self.assertEqual(self.run_tool('index', str(self.directory), '--today', '2099-01-01', '--check')[0], 0)


if __name__ == '__main__':
    unittest.main()
