---
status: Accepted
proposed-on: "2026-09-13"
---

# ADR-001: Use front matter for ADR metadata

## Context

### Problem to Solve

ADR status, proposal start date, and replacement references describe the record's lifecycle. Keeping them in a `## Status` section places document metadata alongside the reasoning and requires tools to locate that section before extracting fields.

We need a clear metadata boundary while retaining fast, deterministic validation, a small skill prompt, and a Python standard-library-only runtime. The proposal start date must survive edits so that stale proposals remain detectable.

### Considered Options and Trade-offs

| Option | Benefits | Costs and limitations |
| --- | --- | --- |
| Keep the Markdown Status section | Already implemented; visible as ordinary Markdown; no migration needed. | Mixes metadata with reasoning and requires support for our custom section layout. |
| Use front matter with a restricted YAML schema | Separates lifecycle fields from the body; exposes a conventional boundary to other tools; keeps parsing small and dependency-free. | Requires an explicit syntax contract and migration; some renderers hide metadata; does not support arbitrary YAML. |
| Use front matter with a general YAML parser | Supports richer metadata and more YAML authoring styles. | Adds a runtime dependency and schema/serialization decisions that are unnecessary for three scalar fields. |

The current Status section is already structured, so moving it does not by itself promise a large speed or token reduction. The main gains are separation of concerns and a conventional metadata location. [MADR makes a similar placement decision](https://adr.github.io/madr/decisions/0013-use-yaml-front-matter-for-meta-data.html), while noting rendering limitations.

## Decision

Use a restricted YAML front-matter block at the beginning of every ADR. Store required `status` and `proposed-on` fields there, plus `superseded-by` when the status is Superseded. Remove the Status section from the body; retain Context, Decision, and Consequences.

Accept unique, supported lowercase keys and simple scalar strings, either unquoted or enclosed in matching single or double quotes. Reject comments, escapes, empty values, unknown keys, collections, multiline values, tags, anchors, and aliases. The formatter orders the keys, double-quotes the date, and emits status and replacement filenames without quotes. This is a documented YAML subset, not a general YAML implementation.

Preserve the five status values and the existing proposal-age rule: a Proposed record fails when its age reaches the configured limit, which defaults to 30 calendar days. Keep `proposed-on` as the proposal start date rather than an update timestamp. Unlike this field, [MADR 4.0.0's date field](https://github.com/adr/madr/blob/4.0.0/template/adr-template.md) denotes the last update.

Require explicit migration of legacy Status sections, preserving their values and dates. Do not auto-convert unrelated documents or maintain duplicate metadata locations.

## Consequences

The authoring template now separates lifecycle metadata from the problem, options, decision, and resulting effects. The runtime remains dependency-free, and metadata parsing has a clear boundary.

Existing ADRs using the old Status section fail validation until explicitly migrated. The repository's comparison fixture is migrated with this change. External ADRs are not modified automatically.

The restricted schema needs deliberate extension if richer metadata becomes necessary. A renderer may hide front matter, so any future publishing integration must make lifecycle status visible to readers. A conventional metadata block alone does not guarantee interoperability with another tool's field names or status definitions.

Validation still cannot establish real agreement, detect falsified proposal dates, or evaluate architectural reasoning. Full lint still reads the body. Speed and input cost must be measured rather than inferred from the new layout; short or already-loaded ADRs may remain cheaper to read directly.

Verification covers scalar syntax, duplicate and unknown keys, missing delimiters, legacy-format rejection, unchanged date semantics, body preservation, and formatter idempotence. The CLI also validates this ADR. [The benchmark](../../reports/benchmark.json) records local measurements, not an LLM billing or quality guarantee.
