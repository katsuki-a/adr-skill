import contextlib
from datetime import date
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/write-adr/scripts/adr.py'
spec = importlib.util.spec_from_file_location('adr', SCRIPT)
adr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adr)
TODAY = '2026-09-13'


def document(status='Proposed', proposed='2026-09-01', body='理由を記録する。', number='0001'):
    return ('# ' + number + '. 採用方針\n\n## Status\n\nStatus: ' + status + '\nProposed-on: ' + proposed
            + '\n\n## Context\n\n' + body + '\n\n## Decision\n\n標準ライブラリを採用する。\n\n## Consequences\n\n依存は減るが対応形式を限定する。\n')


class ADRTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.path = self.directory / '0001-policy.md'
        self.path.write_text(document(), encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, command='lint', paths=None, *options):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            result = adr.main([command, *(paths or [str(self.path)]), '--today', TODAY, *options])
        return result, out.getvalue()

    def write(self, content):
        self.path.write_text(content, encoding='utf-8')

    def test_valid_states_and_old_non_proposed(self):
        target = self.directory / '0002-replacement.md'
        target.write_text(document('Accepted', number='0002'), encoding='utf-8')
        for state in adr.STATUSES:
            with self.subTest(state=state):
                text = document(state, proposed='2020-01-01' if state != 'Proposed' else '2026-09-01')
                if state == 'Superseded':
                    text = text.replace('\n\n## Context', '\nSuperseded-by: 0002-replacement.md\n\n## Context')
                self.write(text)
                self.assertEqual(self.run_cli()[0], 0)

    def test_stale_boundary_and_custom_threshold(self):
        for proposed, expected in [('2026-08-15', 0), ('2026-08-14', 1), ('2026-08-13', 1)]:
            with self.subTest(proposed=proposed):
                self.write(document(proposed=proposed))
                self.assertEqual(self.run_cli()[0], expected)
        self.write(document(proposed='2026-08-14'))
        self.assertEqual(self.run_cli('lint', None, '--max-proposed-days', '31')[0], 0)
        self.assertIn('E_STALE', self.run_cli()[1])

    def test_modification_time_does_not_reset_age(self):
        self.write(document(proposed='2020-01-01') + '\n')
        before = self.path.read_bytes()
        result, output = self.run_cli('format')
        self.assertEqual(result, 1)
        self.assertIn('E_STALE', output)
        self.assertEqual(before, self.path.read_bytes())

    def test_invalid_and_future_dates(self):
        for value in ['2026-02-30', '2026-9-01', 'today', '2026-09-14']:
            with self.subTest(value=value):
                self.write(document(proposed=value))
                self.assertIn('E_DATE', self.run_cli()[1])

    def test_leap_day(self):
        self.write(document('Accepted', proposed='2024-02-29'))
        self.assertEqual(self.run_cli()[0], 0)
        self.write(document('Accepted', proposed='2025-02-29'))
        self.assertIn('E_DATE', self.run_cli()[1])

    def test_status_enum_is_case_sensitive(self):
        for state in ['proposed', 'Draft', 'Accepted.', 'Superseded by 0002']:
            self.write(document(state))
            self.assertIn('E_STATUS', self.run_cli()[1])

    def test_missing_duplicate_reordered_and_extra_headings(self):
        base = document()
        cases = [base.replace('## Context', '## Background'), base.replace('## Decision', '## Context'),
                 base.replace('## Context', '## Decision', 1), base + '\n## Notes\n\nextra\n',
                 base.replace('# 0001.', '# title\n\n# 0001.')]
        for text in cases:
            self.write(text)
            self.assertIn('E_STRUCTURE', self.run_cli()[1])

    def test_metadata_missing_duplicate_unknown_and_empty(self):
        base = document()
        for text in [base.replace('Status: Proposed\n', ''), base.replace('Status: Proposed', 'Status: Proposed\nStatus: Accepted'),
                     base.replace('Status: Proposed', 'State: Proposed'), base.replace('Status: Proposed', 'Status:')]:
            self.write(text)
            self.assertIn('E_METADATA', self.run_cli()[1])

    def test_empty_or_comment_only_body(self):
        for body in ['', '<!-- explain later -->', '### Detail\n\n<!-- later -->']:
            self.write(document(body=body))
            self.assertIn('E_EMPTY', self.run_cli()[1])

    def test_template_placeholders_fail(self):
        self.write(document(body='{{context}}'))
        self.assertIn('E_PLACEHOLDER', self.run_cli()[1])

    def test_fences_comments_and_hard_breaks_preserved(self):
        for fence in ['```', '~~~~']:
            body = ('行末の改行  \n次の行\n\n' + fence + 'md\n## Decision\nStatus: Nope\n   \n' + fence
                    + '\n\n<!--\n## Context\n-->\n\n### 詳細\n\n補足。')
            canonical = document(body=body)
            self.write(canonical.replace('## Status\n\n', '## Status\n\n\n').replace('Status: Proposed', 'Status:   Proposed'))
            self.assertEqual(self.run_cli('format')[0], 0)
            self.assertEqual(self.path.read_text(encoding='utf-8'), canonical)

    def test_unclosed_fence_or_comment_refuses_mutation(self):
        for body in ['```python\nprint(1)', '<!-- unfinished']:
            self.write(document(body=body))
            before = self.path.read_bytes()
            self.assertIn('E_MARKDOWN', self.run_cli('format')[1])
            self.assertEqual(before, self.path.read_bytes())

    def test_format_check_readonly_and_idempotent(self):
        expected = document()
        raw = expected.replace('## Status', '##   Status ###').replace('Status: Proposed\nProposed-on: 2026-09-01', 'Proposed-on: 2026-09-01\nStatus:   Proposed').replace('\n', '\r\n').encode()
        self.path.write_bytes(raw)
        self.assertEqual(self.run_cli('format', None, '--check')[0], 1)
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(self.run_cli('format')[0], 0)
        self.assertEqual(self.path.read_bytes(), expected.encode())
        before_mtime = self.path.stat().st_mtime_ns
        self.assertIn('0 formatted', self.run_cli('format')[1])
        self.assertEqual(self.path.stat().st_mtime_ns, before_mtime)
        self.assertEqual(self.run_cli()[0], 0)

    def test_replacement_missing_self_traversal_and_unexpected(self):
        for replacement in ['', '0001-policy.md', '../0002-next.md', '0002-missing.md']:
            text = document('Superseded')
            if replacement:
                text = text.replace('\n\n## Context', '\nSuperseded-by: ' + replacement + '\n\n## Context')
            self.write(text)
            self.assertIn('E_REPLACEMENT', self.run_cli()[1])
        self.write(document().replace('\n\n## Context', '\nSuperseded-by: 0002-next.md\n\n## Context'))
        self.assertIn('E_REPLACEMENT', self.run_cli()[1])

    def test_filename_and_duplicate_numbers(self):
        self.write(document(number='0002'))
        self.assertIn('E_FILENAME', self.run_cli()[1])
        self.write(document())
        second = self.directory / '0001-another.md'
        second.write_text(document(), encoding='utf-8')
        self.assertIn('E_DUPLICATE', self.run_cli(paths=[str(self.directory)])[1])

    def test_directory_scanning_includes_malformed_filename(self):
        (self.directory / 'README.md').write_text('# Readme', encoding='utf-8')
        self.assertEqual(self.run_cli(paths=[str(self.directory)])[0], 0)
        (self.directory / 'wrong.md').write_text(document(), encoding='utf-8')
        self.assertIn('E_FILENAME', self.run_cli(paths=[str(self.directory)])[1])

    def test_empty_directory_missing_path_and_invalid_utf8(self):
        empty = self.directory / 'empty'
        empty.mkdir()
        self.assertEqual(self.run_cli(paths=[str(empty)])[0], 2)
        self.assertEqual(self.run_cli(paths=[str(empty / 'missing.md')])[0], 1)
        self.path.write_bytes(b'\xff')
        self.assertIn('E_INPUT', self.run_cli()[1])

    def test_output_capped_but_all_files_checked(self):
        for i in range(2, 25):
            (self.directory / ('%04d-policy.md' % i)).write_text(document('Wrong', number='%04d' % i), encoding='utf-8')
        result, output = self.run_cli('lint', [str(self.directory)], '--max-errors', '2')
        self.assertEqual(result, 1)
        self.assertEqual(output.count('E_STATUS'), 2)
        self.assertIn('24 file(s), 23 error(s)', output)
        self.assertIn('21 more errors', output)

    def test_new_expands_template_and_does_not_overwrite(self):
        before = self.path.read_bytes()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = adr.main(['new', '--directory', str(self.directory), '--slug', 'new-policy', '--title', '新しい方針', '--today', TODAY])
        self.assertEqual(result, 0)
        new = self.directory / '0002-new-policy.md'
        self.assertTrue(new.exists())
        self.assertEqual(before, self.path.read_bytes())
        content = new.read_text(encoding='utf-8')
        self.assertIn('Status: Proposed', content)
        self.assertIn('{{context}}', content)
        for key, value in [('context', '背景'), ('decision', '提案と理由'), ('consequences', '利点と欠点')]:
            content = content.replace('{{' + key + '}}', value)
        new.write_text(content, encoding='utf-8')
        self.assertEqual(self.run_cli(paths=[str(new)])[0], 0)

    def test_new_rejects_path_and_multiline_title(self):
        for slug, title in [('../escape', 'Title'), ('ok', 'a\n## Context'), ('ok', 'Title ###')]:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(adr.main(['new', '--directory', str(self.directory), '--slug', slug, '--title', title]), 2)

    def test_symlink_is_not_modified(self):
        link = self.directory / '0002-link.md'
        link.symlink_to(self.path)
        before = self.path.read_bytes()
        self.assertIn('E_INPUT', self.run_cli('format', [str(link)])[1])
        self.assertEqual(self.path.read_bytes(), before)

    def test_unsupported_markdown_refused_without_data_loss(self):
        for text in [document(body='A heading\n==='), document(body='<div>\nbody\n</div>'),
                     document().replace('## Context', '## Context <!-- valuable comment -->')]:
            self.write(text)
            before = self.path.read_bytes()
            self.assertEqual(self.run_cli('format')[0], 1)
            self.assertEqual(self.path.read_bytes(), before)

    def test_real_process_exit_codes(self):
        result = subprocess.run([sys.executable, str(SCRIPT), 'lint', str(self.path), '--today', TODAY], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, str(SCRIPT), 'lint', str(self.path), '--max-proposed-days', '0'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main()
