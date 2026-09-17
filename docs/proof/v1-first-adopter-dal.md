# v1 first-adopter proof — Dal Innovates (file route)

**Date:** 2026-09-17 · **Helper:** recorded via `impactos access grant --scope helper` · **Route:** file route (no store)

This records the v1 milestone proof against a real adopter's data. No adopter personal
data is stored in this repository: the exports were read from the adopter's own folder,
all working files stayed in the git-ignored workspace, and only redacted counts, findings,
and output hashes appear below. Company names, founder names, emails, and financial values
are deliberately omitted.

## What was run

Two reporting periods of Dal Innovates' real CRM exports were taken through the shipped
tool with no hand edits to any generated file:

| Period | Source rows |
| --- | --- |
| 2026-03-26 | 228 company rows |
| 2026-05-18 | 303 company rows |

Sequence: `init` → `access grant` (helper) → `parse` + `apply-mapping` (period 1) →
`compare` (establish baseline) → `parse` + `apply-mapping` (period 2) → `compare` →
`export`. A mapping was authored for the adopter's columns (identity: the adopter's stable
`startupID`). Contacts, updates, and funding were left unmapped for this run (see findings).

## Result

- **167 companies** exported into the BAI template v5 workbook (Companies sheet),
  deduplicated on the stable source identifier.
- **Period comparison (period 2 vs period 1):** 49 changed, 31 new, 0 absent, 0 unmatched,
  146 rows missing a required field. Matching was on the source identifier only; no name
  similarity was used.
- **Reporting profile:** 3 of 29 fields populated from the company-only mapping; the other
  26 are listed in `gaps.md`, each left blank rather than inferred (year incorporated, year
  of first sale, company type, stage of growth, all demographics, all employee counts, all
  revenue and funding, patents, NPS).
- **Provenance:** 599 exported values, each traceable to its source file, column, and row.

## Determinism

Two independent exports of period 2 produced a byte-identical four-file set:

| File | sha1 |
| --- | --- |
| profile.json | 17a8a723b8942e03f723235fdedf501f81f2f0c7 |
| bai-v5.xlsx | 8af113a107d8b24c5d666c1d52fd8bc1892d88c4 |
| gaps.md | 425e35fbf43538ae683e855f3c2e5ae936cf455a |
| provenance.json | 0ae81ac6607a27056f95c3e58453176985e5ca77 |

## Real data findings (the tool surfaced these, and refused to guess)

1. **The same contact identifier appears on two company rows** (one person is the primary
   contact for two startups). The tool refused to ingest contacts rather than silently merge
   two companies' people, so contacts are a gap until a de-duplicated contacts export is used.
2. **146 companies have a blank required legal name** (an operating name is present). These
   are reported as missing-required, not filled from the operating name.
3. **Some companies submitted more than one periodic update in the period**, and the update
   export carries pre-aggregated "Latest …" columns. Because an update is identified by
   company and date, ingesting metrics needs a per-update identifier or a de-duplicate-to-
   latest step; the tool refused rather than drop or merge updates.

Each finding is a data-shape issue in the source, surfaced honestly instead of guessed
around. None is a defect in the tool.

## Definition-of-done status

| Clause | Status |
| --- | --- |
| Two consecutive periods from real exports, no hand edits | Met |
| Second run reports differences | Met (49 changed / 31 new / 146 missing-required) |
| Reporting profile + BAI v5 export produced, every unfilled field explained | Met (3/29 populated, 26 gaps named) |
| Identical outputs on re-export (no hand edits) | Met (byte-identical four-file set) |
| Same inputs and mappings produce the same output in a second harness | **Met** — Cursor (2026-09-17) replayed period `2026-05-18` from the same sources and company-only mapping; all four sha1s matched the table above |

Cross-harness leg closed in Cursor. Determinism (same inputs and confirmed mappings → identical bytes) is proven in two harnesses.
