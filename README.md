# impactOS Agents

Helper-first starter for incubators and accelerators: a storage-independent data contract, a deterministic CLI the agent drives, and harness-portable skills so a non-technical helper can inventory where an organisation's data lives, choose per data type whether it stays put or moves to an optional store, and produce the funder-accepted direct-beneficiary spreadsheet every reporting period.

**Helpers (non-technical):** start at [START-HERE.md](START-HERE.md).

Built for organisations other than Volta. Not a version of Volta's impactOS, Coach OS, Founder OS or the ImpactOS Multi Tenant project.

- Product contract: Linear [VOL-250](https://linear.app/volta/issue/VOL-250) in project [impactOS Agents](https://linear.app/volta/project/impactos-agents-42da62781968)
- Estate analysis and grilled decisions: `docs/estate-analysis-2026-09-16.md`
- Reference spreadsheet (one approved export of the reporting profile): `docs/BAI_Metrics_Data_Collection_Template_v5.xlsx`

## The `impactos` CLI

Deterministic command-line tool the skills drive. No install step: it runs on the
system Python 3.9+ with a vendored `openpyxl` (`vendor/`). It makes no network or
model calls and never writes to a source file — everything it produces lands in
the git-ignored `workspace/` tree.

```sh
bin/impactos preflight                 # interpreter, vendored openpyxl, writable workspace
bin/impactos init                      # create workspace/, config, and the pre-commit scan hook
bin/impactos parse --source EXPORT --type export --period 2026-06-30
bin/impactos apply-mapping --source PAYLOAD --mapping mappings/x.json --period 2026-06-30 --confirmed
bin/impactos export --period 2026-06-30 # profile.json, bai-v5.xlsx, gaps.md, provenance.json (+ excluded run.json)
bin/impactos check --tracked           # secret / PII scan (exit 1 on a hit; runs pre-commit and in CI)
bin/impactos state                     # JSON workspace summary for skills
```

Every command takes `--json` and returns `0` pass, `2` warnings, `1` fail. Windows
uses `bin\impactos.cmd`. Run the whole test + schema + scan gate with `make check`.
