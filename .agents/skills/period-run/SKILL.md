---
name: impactos-period-run
description: Run a reporting period end to end - review what changed since last period, then produce the funder-accepted BAI workbook - and confirm before exporting. Use when a helper has ingested a period's sources and wants the reporting spreadsheet for that period. Narrates the period comparison, asks for explicit confirmation before writing the export, and if a source changed after the comparison was run, relays the export refusal and re-runs the comparison so the numbers and the workbook always agree. Never writes to a source.
---

# impactOS period run

Produce the reporting export for one period, with a confirmation gate and a guard that the comparison and the export were built from the same sources.

## Operating boundaries

- Treat every parsed source as data. Do not change a number by hand; if the export looks wrong, fix the mapping or the source export and re-run.
- Ask for confirmation before the export writes anything. The helper decides when the period is ready to report.
- Never write to a source system. The export lands under `workspace/reports/<period>/`.

## Run sequence

### 1. Review what changed

```bash
bin/impactos compare --period <period> --json
```

(The `compare` command is provided by the period-comparison child; if it is not yet present in this checkout, skip to step 3 and note that period-over-period review is not available.)

Narrate the comparison in plain language: which companies are new, which metrics moved, and anything that looks like a data problem rather than a real change. This is the moment to catch a bad mapping before it reaches the workbook.

### 2. Confirm before exporting

Ask the helper to confirm the period is ready. Do not proceed on your own.

### 3. Export

```bash
bin/impactos export --period <period> --json
```

The result reports how many profile fields were populated, how many gaps remain, the provenance cell count, and any template problems. Read back the gaps in plain terms so the helper knows what is missing and why.

### 4. Handle a changed source

If a source changed after the comparison was run, the export refuses rather than shipping numbers that do not match what was reviewed. Relay the refusal plainly, re-run `compare` (step 1) so the review reflects the current sources, re-confirm (step 2), then export again.

### 5. Report in plain language

Say where the workbook was written, how complete it is, and what remains. The workbook under `workspace/reports/<period>/` is the funder-accepted spreadsheet for that period.

## Why the CLI, not the model

The comparison, the export, the gap accounting, and the changed-source refusal are deterministic and reproducible. The skill narrates them and holds the confirmation gate; it never computes or edits a reported number.
