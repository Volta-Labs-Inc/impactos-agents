# Harness parity

The impactOS skills carry all judgment; the deterministic CLI carries all
computation. For the product to behave the same for a helper in any folder-reaching
harness (Cowork, Claude Code, Codex, Cursor), each skill must issue the **same CLI
invocations** from the **same prompts**, whichever harness runs it.

This document is the checklist. It states, per skill, the prompt a helper gives and
the exact CLI invocations the skill must make in response. Child 7 (the parity run)
executes this checklist in two harnesses on the Harbourline fixture and records the
runtime evidence at the end.

The skills live once under `skills/` and are mirrored into `.claude/skills/` and
`.agents/skills/` by `scripts/sync_skills.py`; `make check` fails on drift, so every
harness reads byte-identical skills.

## Conventions

- Invocations below use `bin/impactos`. Where a harness cannot execute it, the
  equivalent is `python3 cli/run.py <same args>`; the arguments are identical.
- `--json` is used whenever the skill reads the result programmatically.
- `<period>` is the reporting period label, for example `2026-06-30`.

## preflight

| Helper prompt | Expected CLI invocations |
|---|---|
| "Set this up" / first open in a new harness | `bin/impactos preflight --json` |

Expected behaviour: exit 0 clears the helper to continue; a non-zero exit stops with
the specific fix (install Python 3.9+, move the folder to a writable location, or
re-clone for a complete `vendor/` and template).

## onboarding

| Helper prompt | Expected CLI invocations |
|---|---|
| "Let's get started onboarding <org>" | `bin/impactos init --json`, then `bin/impactos interview --action next --json` |
| Helper points at an export | `bin/impactos parse --source <file> --period <period> --json` (add `--type transcript` for transcripts) |
| Helper answers the current question | `bin/impactos interview --action answer --id <id> --value "<answer>" --json` |
| "Where did we get to?" / resuming later | `bin/impactos interview --action status --json`, then `--action next --json` |
| "Which data stays and which moves?" | `bin/impactos interview --action route --json` |
| Before committing notes or the source map | `bin/impactos check --json` |
| "Start over" | `bin/impactos interview --action reset --json` |

Expected behaviour: exactly one question per turn; resume returns the earliest
unanswered question with earlier answers intact; the route rule returns `stay`,
`store`, `conditional`, or `store_or_add_identifier` per data type, treating a source
with no stable identifier as a missing required field; owners recorded by name or role
only.

## map-source

| Helper prompt | Expected CLI invocations |
|---|---|
| "Map the companies export" | `bin/impactos parse --source <file> --period <period> --json` |
| After the helper confirms the proposed mapping | `bin/impactos check --json`, then `bin/impactos apply-mapping --source <payload> --mapping mappings/<source>.json --period <period> --confirmed --json` |

Expected behaviour: apply refuses without `--confirmed`; apply refuses and names any
mapped column removed or renamed since the mapping was written; a demographic hint in
an undeclared column is left unset and flagged, never mapped to a value.

## extract-claims

| Helper prompt | Expected CLI invocations |
|---|---|
| "Pull the facts out of this call" | `bin/impactos parse --source <file> --type transcript --period <period> --json` |
| After the helper confirms the proposed claims | `bin/impactos apply-mapping --claims --confirmed …` (provided by the CLI; store writing is a later child) |

Expected behaviour: claims typed fact/inference/assumption with a confidence and
transcript segment evidence ids; participants resolved by email; the same transcript
ingested twice is a no-op (dedup by content hash plus vendor id). This skill proposes
only.

## period-run

| Helper prompt | Expected CLI invocations |
|---|---|
| "Show me what changed this period" | `bin/impactos compare --period <period> --json` (provided by the period-comparison child) |
| After the helper confirms the period is ready | `bin/impactos export --period <period> --json` |
| A source changed after compare | relay the export refusal, re-run `compare`, re-confirm, then `export` again |

Expected behaviour: export is gated on explicit confirmation; a source changed after
compare causes export to refuse until compare is re-run.

## Runtime evidence (child 7)

Child 7 fills this in after running the checklist above in two harnesses on the
Harbourline fixture. Until then these rows are open.

| Skill | Harness A (e.g. Cowork) | Harness B (e.g. Codex) | CLI invocations matched? | Transcript link |
|---|---|---|---|---|
| preflight | pending | pending | pending | pending |
| onboarding (incl. resume across harnesses) | pending | pending | pending | pending |
| map-source | pending | pending | pending | pending |
| extract-claims | pending | pending | pending | pending |
| period-run | pending | pending | pending | pending |

Acceptance for the parity run:

- AC-01: onboarding on the fixture, first three questions are confirmations of parsed
  files, ending with a proposed first mapping.
- AC-02: the recorded routes match the rule in `operating-notes/routes.md`.
- AC-03: stop after an onboarding question in one harness, resume in another at the
  next unanswered question with answers intact.
- AC-04: a `she/her` hint in a name leaves demographics unset and flagged.
