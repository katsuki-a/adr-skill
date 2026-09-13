#!/usr/bin/env python3
"""Measure real CLI startup + scans and optional o200k_base input-token proxies."""
import argparse
from datetime import date
import importlib.util
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/write-adr'
SCRIPT = SKILL / 'scripts/adr.py'


def run(command):
    start = time.perf_counter()
    result = subprocess.run([sys.executable, '-B', str(SCRIPT), *command], capture_output=True, text=True, check=True)
    return (time.perf_counter() - start) * 1000, result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--repeats', type=int, default=7)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('--repeats must be positive')
    sample = (ROOT / 'tests/fixtures/ADR-001-use-standard-library.md').read_text(encoding='utf-8')
    report = {'measured_on': date.today().isoformat(), 'python': platform.python_version(),
              'platform': platform.platform(), 'repeats': args.repeats,
              'method': 'New Python process each time; sequential scans; OS filesystem cache not cleared; no LLM calls.',
              'timing': {}, 'index_timing': {}, 'format_with_index_timing': {}}
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        for count in (1, 100, 1000):
            folder = work / str(count)
            folder.mkdir()
            for n in range(1, count + 1):
                (folder / ('ADR-%03d-example.md' % n)).write_text(sample.replace('# ADR-001:', '# ADR-%03d:' % n, 1), encoding='utf-8')
            values, outputs = zip(*(run(['lint', str(folder), '--today', '2026-09-13']) for _ in range(args.repeats)))
            report['timing'][str(count)] = {'median_ms': round(statistics.median(values), 3), 'max_ms': round(max(values), 3), 'stdout_bytes': len(outputs[0].encode())}
            for key, command in [('index_timing', ['index', str(folder)]), ('format_with_index_timing', ['format', str(folder / 'ADR-001-example.md')])]:
                values, outputs = zip(*(run([*command, '--today', '2026-09-13']) for _ in range(args.repeats)))
                report[key][str(count)] = {'median_ms': round(statistics.median(values), 3), 'max_ms': round(max(values), 3), 'stdout_bytes': len(outputs[0].encode())}

        created = []
        formatted = []
        for n in range(args.repeats):
            new_dir = work / ('new-%d' % n)
            ms, output = run(['new', '--directory', str(new_dir), '--slug', 'example', '--title', 'ADR検証方式'])
            created.append(ms)
            draft = new_dir / 'ADR-001-example.md'
            draft.write_text(sample.replace('## Context\n\n', '## Context\n\n\n'), encoding='utf-8')
            ms, format_output = run(['format', str(draft), '--today', '2026-09-13'])
            formatted.append(ms)
        report['authoring_cli_ms'] = {'new_median': round(statistics.median(created), 3), 'format_and_lint_median': round(statistics.median(formatted), 3)}
    # No dependency required. Install tiktoken only in a separate measurement environment.
    if importlib.util.find_spec('tiktoken'):
        import tiktoken
        enc = tiktoken.get_encoding('o200k_base')
        tokens = lambda text: len(enc.encode(text))
        short = '# 0001. SQLiteを採用する\n\n## Status\n\nAccepted\n\n## Context\n\n単一プロセスで少量のデータを永続化したい。\n\n## Decision\n\n管理するサービスを増やさないためSQLiteを使う。\n\n## Consequences\n\n配備は簡単になるが、複数ノードの同時書き込みには向かない。\n'
        # Same final ADR output and decision-specific context are excluded from both sides.
        # The command argument texts approximate a short-path new + format invocation.
        template = (SKILL / 'assets/adr.md').read_text().replace('{{id}}', 'ADR-001').replace('{{title}}', 'ADR検証方式').replace('{{proposed_on}}', '2026-09-13')
        command_text = "python3 scripts/adr.py new --directory docs/adr --slug example --title 'ADR検証方式'\npython3 scripts/adr.py format docs/adr/ADR-001-example.md"
        components = {'skill': tokens((SKILL / 'SKILL.md').read_text()), 'generated_template_and_path': tokens('docs/adr/ADR-001-example.md\n' + template), 'validation_stdout': tokens(format_output), 'command_text': tokens(command_text)}
        total = sum(components.values())
        report['input_proxy'] = {'encoding': 'o200k_base (proxy, not a claim about the active model tokenizer)', 'components': components, 'skill_flow_total': total, 'comparison': {}}
        for name, text in [('short_adr', short), ('fixture_adr', sample)]:
            size = tokens(text)
            report['input_proxy']['comparison'][name] = {'one_existing_adr': size, 'three_existing_adrs': size * 3, 'ten_existing_adrs': size * 10, 'break_even_records': math.ceil(total / size)}
        report['input_proxy']['limitations'] = 'Not billing or an LLM quality/latency A/B test. Excludes transport wrappers, cache pricing, common decision context/output; long paths and failures add tokens. Small or already-loaded ADR baselines can be cheaper.'
    else:
        report['input_proxy'] = {'available': False, 'reason': 'tiktoken is optional and absent'}
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding='utf-8')
    print(rendered, end='')


if __name__ == '__main__':
    main()
