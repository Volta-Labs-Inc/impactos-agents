# impactOS Agents

Canonical agent instructions for this folder. `CLAUDE.md` is a generated pointer here.

## What this project is

A helper-first starter for incubators and accelerators: a storage-independent data contract (the impactOS data types plus a direct-beneficiary reporting profile), a deterministic command-line tool the agent drives, and harness-portable skills so a non-technical helper can inventory where an organisation's data lives, choose per data type whether it stays in existing systems or moves to an optional store, and produce the funder-accepted spreadsheet every reporting period. Built for organisations other than Volta; not a version of Volta's impactOS, Coach OS, Founder OS or ImpactOS Multi Tenant.

- Product contract: Linear VOL-250 in project "impactOS Agents". Linear owns scope and decisions; GitHub owns the delivery contract.
- Estate analysis and the grilled decisions: `docs/estate-analysis-2026-09-16.md`.
- Reference export: `docs/BAI_Metrics_Data_Collection_Template_v5.xlsx` (one approved configuration of the reporting profile, not the goal).

## Standing rules

- The command-line tool stays deterministic: no language-model calls, no model credentials. Judgment lives in skills that run in the harness.
- Never write to a source system (HubSpot, Airtable, spreadsheets). Read exports only.
- Never infer demographics, company type or funding amounts; leave unset and flag for a person.
- Source exports, generated reports, interview state and provenance records live outside version control (`workspace/`, `exports/`, `reports/` are ignored). The repository holds mappings, operating notes, the source map, the guidance document and skills only.
- No funder agreement text in this repository; anchor to the cited public frameworks.
- Read and maintain `time-tracker.json` when the project's identity, workspace or billing boundary changes. It is local and private and is never committed.

## Adversarial review of generated outputs

No generated analytical output (numbers, rankings, scores, maps, model results) is a finding until it survives an adversarial review: a fresh pass, separate from whoever produced the output, whose job is to refute it rather than confirm it. The bar is that every claim is backed by empirical evidence an independent re-run can regenerate.

1. **Determinism is verified, not assumed.** The reviewer re-runs the analysis from its stated inputs. Identical inputs and code must produce identical outputs. Unseeded randomness, unpinned dependencies, and order-dependent steps are findings to fix before the result means anything.

2. **Every number must reproduce.** Each figure, rank, and claim regenerates from the shipped data and code. A claim that does not reproduce is withdrawn, not softened.

3. **Provenance travels with the output.** Inputs, code version, parameters, and pass/fail criteria are recorded with the result so an independent re-run needs nothing from the author. If reproducing it requires asking the author how, the output is not done.

4. **"Looks right" is not a review result.** The review concludes with one of: re-ran and matched, did not reproduce so withdrawn or corrected, or a named blocker. A check that could not have failed is not evidence of anything.
