# Repository instructions

Respond in Japanese unless the user requests another language. Keep ADR identifiers, metadata keys, and structural headings in the format defined by this repository.

## Project context

This repository provides the `write-adr` skill and its Python CLI. Start with the relevant files rather than loading every reference:

- [Skill workflow](skills/write-adr/SKILL.md)
- [Format and CLI contract](skills/write-adr/references/format.md)
- [Architecture decisions](docs/adr/README.md)

`tests/fixtures` contains fictional records for testing and measurement, not approved project decisions.

## Implementation constraints

- Keep the CLI compatible with Python 3.9+ and the standard library only. Normal authoring, linting, formatting, and indexing must work offline without LLM calls. PyYAML and tiktoken are optional development tools, not runtime dependencies.
- Keep skill instructions short. Execute helpers instead of loading their source or all ADRs merely to reproduce a format; inspect source when changing the implementation.
- Treat the Markdown and YAML syntax as a deliberately limited profile. Keep the parser, formatter, template, references, and tests consistent when changing it. Make migrations explicit rather than silently accepting or rewriting unrelated formats.
- Preserve ADR prose, code blocks, and meaningful whitespace during formatting. Never reset `proposed-on` or change status to make a stale proposal pass validation.
- Generate README tables through the CLI. Preserve text outside the managed markers, reject malformed markers, and keep output bounded. Do not print the full index as routine tool output.

## Decision records

Use the local [write-adr skill](skills/write-adr/SKILL.md) to record architectural decisions in `docs/adr`. Use generated `ADR-001` identifiers and include the problem, considered options and trade-offs, selected option with rationale, and consequences. Mark a decision Accepted only when agreement is established; keep superseded records and their proposal dates.

`new` and `format` maintain the index. After manual metadata edits, renames, or removals, run `python3 skills/write-adr/scripts/adr.py index docs/adr`. Do not edit generated rows by hand.

## Verification

Run from the repository root after CLI, template, or format-contract changes:

```sh
python3 -B -m unittest discover -s tests -v
python3 skills/write-adr/scripts/adr.py format docs/adr tests/fixtures --check
git diff --check
```

For ADR-only edits, check the affected ADR directory with `format --check`, which also verifies its index. For prose-only changes, check links and the diff; the full test suite is unnecessary. Use the actual date for repository freshness checks and `--today` only for intentionally fixed-date test cases.

For changes affecting runtime performance or skill input size, run `python3 tools/benchmark.py`. When refreshing `reports/benchmark.json`, update the matching README figures and state the measurement conditions. Token counting requires tiktoken in an isolated development environment. Do not claim measured runtime or token proxies establish LLM billing, quality, or universal cost savings.

Commit and push only when requested. Include only changes belonging to the requested work.
